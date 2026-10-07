"""
Reglas de exposición (EXP-013): estar comprado o en efectivo según un estado que se revisa una
vez por día. No son reglas de entrada con TP/SL: la "salida" es el cambio de estado.

    estado de la regla al cierre de la vela j-1 ──(primera vela del día UTC)──> posición de la vela j
    posición de la vela j: se mantiene de Open[j] a Open[j+1]

Mecánica (fijada en la pre-especificación de EXP-013, RESEARCH_LOG.md):
  - La posición sólo cambia en la primera vela de cada día UTC presente en los datos; pasa a ser el
    estado de la regla evaluado al cierre de la vela anterior. Antes del primer cambio: efectivo.
  - Cada cambio (entrada o salida) es una orden de mercado: taker + medio spread + slippage del
    escenario de costos, como fracción del capital, cargado en la vela del cambio.
  - En la última vela de cada ventana la posición se valúa a su Close (no se usan precios fuera de
    la ventana). La estrategia es continua entre ventanas contiguas: empieza en efectivo al inicio
    de la primera y se liquida al final de la última.
  - Retornos simples por vela, sumados (sin reinversión), como en el resto de la bitácora.

Benchmark: exposición constante igualada ē (exposición media de la regla en todo el período
evaluado, sin costos). Lift neto por vela: d_j = pos_j·r_j − costo_j − ē·r_j. ē sólo sirve de
vara de comparación: no interviene en la decisión de la regla.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .costs import ExecutionCostModel, MarketContext
from .entry_detector import Segment
from .features import HTFTrend, Operand, RelativeVolatility
from .walk_forward import fold_level_t
from .multiple_testing import newey_west_t

DAY_NS = 86_400 * 10 ** 9


@dataclass(frozen=True)
class ExposureRule:
    """'Comprado' al cierre de la vela si `operand <op> threshold`; valor no definido (NaN) -> efectivo."""
    name: str
    operand: Operand
    op: str            # ">" o "<"
    threshold: float

    def state(self, df: pd.DataFrame) -> np.ndarray:
        v = self.operand.compute(df)
        with np.errstate(invalid="ignore"):
            s = v > self.threshold if self.op == ">" else v < self.threshold
        return s & np.isfinite(v)

    def describe(self) -> str:
        return f"{self.operand.label} {self.op} {self.threshold:g}"


# Las tres reglas pre-especificadas de EXP-013 (no se cambian después de ver resultados).
EXP013_RULES: tuple[ExposureRule, ...] = (
    ExposureRule("R1_tendencia_20d", HTFTrend("1D", 20), ">", 0.0),
    ExposureRule("R2_tendencia_100d", HTFTrend("1D", 100), ">", 0.0),
    ExposureRule("R3_calma_24_240", RelativeVolatility(24, 240), "<", 1.0),
)


def day_starts(index: pd.DatetimeIndex) -> np.ndarray:
    """True en la primera vela de cada día UTC presente en los datos (la vela 0 nunca: no hay anterior).
    Usa la época UTC, igual que `HTFTrend`: la zona horaria del índice no influye; sin zona = UTC."""
    day = index.as_unit("ns").asi8 // DAY_NS
    out = np.zeros(len(index), dtype=bool)
    out[1:] = day[1:] != day[:-1]
    return out


def daily_positions(df: pd.DataFrame, state: np.ndarray) -> np.ndarray:
    """pos[j] (0/1) = posición mantenida durante la vela j. Sólo cambia en la primera vela de cada día
    UTC, a `state[j-1]`; depende de datos hasta j-1 y de la hora de la vela j (que se conoce de antemano)."""
    n = len(df)
    starts = day_starts(df.index)
    last = np.maximum.accumulate(np.where(starts, np.arange(n), -1))
    pos = np.zeros(n, dtype=np.int8)
    ok = last >= 1
    pos[ok] = np.asarray(state, dtype=bool)[last[ok] - 1]
    return pos


def calendar_segments(index: pd.DatetimeIndex,
                      bounds: list[tuple[pd.Timestamp, pd.Timestamp]]) -> list[Segment]:
    """Ventanas por fecha (EXP-014): las velas de `index` con fecha en [inicio, fin). Con bordes contiguos
    (el fin de una ventana = el inicio de la siguiente) los segmentos también son contiguos."""
    ns = index.as_unit("ns").asi8
    out = []
    for a, b in bounds:
        i0 = int(np.searchsorted(ns, pd.Timestamp(a).as_unit("ns").value, side="left"))
        i1 = int(np.searchsorted(ns, pd.Timestamp(b).as_unit("ns").value, side="left"))
        out.append(Segment("VALIDATION", i0, i1))
    return out


def pool_mean(series: dict[str, pd.Series]) -> pd.Series:
    """Promedio entre activos alineado por índice (ventana u hora): sólo entre los activos con dato."""
    return pd.concat(series, axis=1, sort=True).mean(axis=1, skipna=True)


def segment_bar_returns(df: pd.DataFrame, seg: Segment) -> np.ndarray:
    """r[j] para j en [start, end): Open[j+1]/Open[j] − 1; en la última vela Close/Open − 1, para no usar
    ningún precio fuera del segmento."""
    o = df["Open"].to_numpy(dtype="float64")[seg.start:seg.end]
    last_close = float(df["Close"].iloc[seg.end - 1])
    return np.r_[o[1:], last_close] / o - 1.0


def side_cost(cm: ExecutionCostModel, ctx: MarketContext, idx: np.ndarray) -> np.ndarray:
    """Costo de un lado ejecutado con orden de mercado en la vela idx, como fracción del capital."""
    n = cm.position_size_usd
    return (cm.fees.rate("taker", n) + cm.spread.half_spread(idx, ctx)
            + cm.slippage.slippage(idx, ctx, n))


def max_drawdown(x: np.ndarray) -> float:
    """Máxima caída de la curva de retornos acumulados (suma simple, desde 0)."""
    eq = np.r_[0.0, np.cumsum(x)]
    return float((eq - np.maximum.accumulate(eq)).min())


@dataclass
class ExposureResult:
    rule: str
    bars: np.ndarray                    # índices de vela evaluados (todas las ventanas, en orden)
    window_id: np.ndarray               # ventana de cada vela evaluada
    pos: np.ndarray                     # posición (0/1) en cada vela evaluada
    r: np.ndarray                       # retorno de BTC en cada vela evaluada
    switches: np.ndarray                # 1 si en la vela se paga un lado (cambio o liquidación final)
    cost: dict[str, np.ndarray]         # costo por vela según escenario
    exposure: float                     # ē

    def gross_lift(self) -> np.ndarray:
        return (self.pos - self.exposure) * self.r

    def net(self, scenario: str) -> np.ndarray:
        return self.pos * self.r - self.cost[scenario]

    def net_lift(self, scenario: str) -> np.ndarray:
        return self.net(scenario) - self.exposure * self.r

    def per_window(self, x: np.ndarray) -> np.ndarray:
        return np.bincount(self.window_id, weights=x, minlength=int(self.window_id.max()) + 1)

    @property
    def n_entries(self) -> int:
        prev = np.r_[0, self.pos[:-1]]
        return int(((self.pos == 1) & (prev == 0)).sum())


def evaluate_rule(df: pd.DataFrame, rule_name: str, pos: np.ndarray, windows: list[Segment],
                  cost_models: dict[str, ExecutionCostModel]) -> ExposureResult:
    """Evalúa una serie de posiciones sobre ventanas CONTIGUAS (las VALIDATION del walk-forward)."""
    for a, b in zip(windows[:-1], windows[1:]):
        if a.end != b.start:
            raise ValueError("Las ventanas deben ser contiguas (estrategia continua entre ventanas).")
    bars = np.concatenate([np.arange(w.start, w.end) for w in windows])
    wid = np.concatenate([np.full(w.n_bars, i) for i, w in enumerate(windows)])
    r = np.concatenate([segment_bar_returns(df, w) for w in windows])
    p = np.asarray(pos, dtype=float)[bars]
    sw = np.abs(p - np.r_[0.0, p[:-1]])            # empieza en efectivo
    sw[-1] += p[-1]                                # liquidación al final de la última ventana
    ctx = MarketContext(df)
    cost = {k: sw * side_cost(cm, ctx, bars) for k, cm in cost_models.items()}
    return ExposureResult(rule_name, bars, wid, p, r, sw, cost, float(p.mean()))


def summarize(res: ExposureResult, decide: str = "typical", robust: str = "conservative",
              threshold: float = 3.0, hac_lags: int = 720, n_blocks: int = 5,
              min_entries: int = 30) -> dict:
    """Métricas y criterio de candidato C1-C6 de EXP-013 para una regla."""
    nw = int(res.window_id.max()) + 1
    L = {k: res.per_window(res.net_lift(k)) for k in res.cost}
    G = res.per_window(res.gross_lift())
    tw = lambda x: fold_level_t(pd.DataFrame({"x": x}), "x")
    blocks = np.array_split(np.arange(nw), n_blocks)
    block_L = [float(L[decide][b].sum()) for b in blocks]
    hours_in = float(res.pos.sum())
    ent = res.n_entries
    out = {
        "rule": res.rule,
        "n_windows": nw, "n_bars": int(len(res.bars)),
        "exposure": res.exposure, "n_entries": ent,
        "mean_episode_hours": hours_in / ent if ent else float("nan"),
        "n_sides_paid": int(res.switches.sum()),
        "buy_hold_sum": float(res.r.sum()),
        "benchmark_sum": float(res.exposure * res.r.sum()),
        "rule_gross_sum": float((res.pos * res.r).sum()),
        "gross_lift_sum": float(G.sum()),
        "gross_lift_mean_window": float(G.mean()),
        "t_windows_gross_lift": tw(G),
        "hac_gross_lift": newey_west_t(res.gross_lift(), hac_lags),
        "block_net_lift": block_L,
        "blocks_positive": int(sum(x > 0 for x in block_L)),
    }
    for k in res.cost:
        net = res.net(k)
        out[f"cost_sum_{k}"] = float(res.cost[k].sum())
        out[f"rule_net_sum_{k}"] = float(net.sum())
        out[f"net_lift_sum_{k}"] = float(L[k].sum())
        out[f"net_lift_mean_window_{k}"] = float(L[k].mean())
        out[f"t_windows_net_lift_{k}"] = tw(L[k])
        out[f"hac_net_lift_{k}"] = newey_west_t(res.net_lift(k), hac_lags)
        out[f"windows_net_lift_gt0_{k}"] = int((L[k] > 0).sum())
        out[f"max_drawdown_rule_{k}"] = max_drawdown(net)
    out["max_drawdown_benchmark"] = max_drawdown(res.exposure * res.r)
    out["max_drawdown_buy_hold"] = max_drawdown(res.r)
    ann = np.sqrt(24 * 365)
    sh = lambda x: float(x.mean() / x.std(ddof=1) * ann) if x.std(ddof=1) > 0 else float("nan")
    out["sharpe_rule_" + decide] = sh(res.net(decide))
    out["sharpe_buy_hold"] = sh(res.r)
    crit = {
        "C1_t_windows_net_lift": bool(out[f"net_lift_mean_window_{decide}"] > 0
                                      and out[f"t_windows_net_lift_{decide}"] >= threshold),
        "C2_hac_net_lift_ge_2": bool(out[f"hac_net_lift_{decide}"] >= 2.0),
        "C3_blocks_4_of_5": bool(out["blocks_positive"] >= n_blocks - 1),
        "C4_net_lift_conservative_gt0": bool(out[f"net_lift_sum_{robust}"] > 0),
        "C5_rule_net_gt0_typical_and_conservative": bool(out[f"rule_net_sum_{decide}"] > 0
                                                         and out[f"rule_net_sum_{robust}"] > 0),
        "C6_min_entries": bool(ent >= min_entries),
    }
    out["criteria"] = crit
    out["candidate"] = bool(all(crit.values()))
    out["evaluable"] = bool(ent >= min_entries and 0.0 < res.exposure < 1.0)
    out["threshold_C1"] = threshold
    return out
