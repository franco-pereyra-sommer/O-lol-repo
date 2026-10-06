"""
Qué ocurrió después de cada entrada.

Clave de eficiencia: el resultado de una operación depende SÓLO de la vela de
entrada e (y de TP, SL, H, costos), no de qué condición la generó. Por eso se
calcula una única vez una `OutcomeTable` con el resultado hipotético de entrar
en CADA vela, y cada condición simplemente indexa esa tabla.

Definiciones, con P = Open[e] y ventana k = 0..H-1 (velas e..e+H-1).
LONG gana si el precio sube; SHORT gana si baja. Todo es simétrico:

                 LONG                              SHORT
  TP nivel       P(1+p_TP), tocado si High >= TP   P(1-p_TP), tocado si Low  <= TP
  SL nivel       P(1-p_SL), tocado si Low  <= SL   P(1+p_SL), tocado si High >= SL
  SL con gap     min(SL, Open)                     max(SL, Open)
  retorno bruto  X/P - 1                           1 - X/P        (X = precio de salida)
  MFE            max High/P - 1                    1 - min Low/P
  MAE            min Low/P - 1                     1 - max High/P

Abajo se detalla LONG; SHORT es el espejo.


  TP = P(1+p_TP)     SL = P(1-p_SL)
  k_TP = primera k con High[e+k] >= TP     k_SL = primera k con Low[e+k] <= SL
  TP_FIRST  : k_TP <  k_SL
  SL_FIRST  : k_SL <  k_TP
  AMBIGUOUS : k_TP == k_SL  (ambos en la misma vela; con OHLC no se sabe el orden)
  NONE      : ninguno se alcanza en H velas

  Precio de salida (para el retorno):
    TP_FIRST  -> TP (sin asumir mejora por gap a favor: conservador)
    SL_FIRST  -> min(SL, Open[e+k_SL])  (si la vela abre con gap por debajo
                 del SL, la orden se llena en la apertura, no en el SL)
    NONE      -> Close[e+H-1]  (salida por tiempo)
    AMBIGUOUS -> según AMBIGUOUS_RETURN_POLICY (la clasificación NO cambia)

  MFE = max_k High[e+k]/P - 1     MAE = min_k Low[e+k]/P - 1
  (sobre TODO el horizonte H, independientemente de si TP/SL cerraron antes:
   describen el camino del precio, no la operación).

Costos: los calcula el modelo de ejecución de costs.py según el tipo de
salida (TP con orden límite, SL con stop de mercado, tiempo con orden de
mercado). Se calcula un retorno neto por cada escenario de costos:
  net_return            -> escenario principal (COST_SCENARIO)
  net_by_scenario[name] -> cada escenario de COST_SCENARIOS_REPORT

Resultados favorables generales: siempre se miden desde el punto de vista de
la POSICIÓN. Para SHORT, "reach p" = el precio bajó p; "down_then_up" =
primero la posición pierde p1 y después gana p2 (el precio sube y luego baja).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from .config import PositionSide, ResearchConfig
from .costs import EXIT_SL, EXIT_TIME, EXIT_TP, MarketContext, build_cost_model
from .features import atr_values

log = logging.getLogger(__name__)

TP_FIRST, SL_FIRST, NONE, AMBIGUOUS = 0, 1, 2, 3
OUTCOME_NAMES = np.array(["TP_FIRST", "SL_FIRST", "NONE", "AMBIGUOUS"])


@dataclass
class OutcomeTable:
    """Arrays de longitud n (una posición por vela de entrada posible). NaN/-1 donde no aplica."""
    entry_price: np.ndarray
    outcome: np.ndarray            # int8 (-1 = horizonte incompleto)
    exit_offset: np.ndarray        # k de salida (0..H-1)
    exit_price: np.ndarray
    gross_return: np.ndarray
    net_return: np.ndarray
    mfe: np.ndarray
    mae: np.ndarray
    favorable: dict[str, np.ndarray] = field(default_factory=dict)  # nombre -> bool
    net_by_scenario: dict[str, np.ndarray] = field(default_factory=dict)
    cost_scenario: str = ""
    # EXP-010: distancias de TP/SL como fracción del precio de entrada (por entrada) y máscara de
    # entradas válidas (con ATR disponible). En modo "fixed" entry_valid es None (todas válidas).
    tp_frac: np.ndarray | None = None
    sl_frac: np.ndarray | None = None
    entry_valid: np.ndarray | None = None


def favorable_name(spec: dict) -> str:
    t = spec["type"]
    if t == "reach":
        return f"reach_{spec['p']:g}_in_{spec['bars']}"
    if t == "at_horizon":
        return f"ret_ge_{spec['p']:g}_at_{spec['bars']}"
    if t == "down_then_up":
        return f"down_{spec['p1']:g}_then_up_{spec['p2']:g}"
    if t == "up_then_down":
        return f"up_{spec['p1']:g}_then_down_{spec['p2']:g}"
    raise ValueError(f"Tipo de resultado favorable desconocido: {spec}")


def _first_true(mask: np.ndarray) -> np.ndarray:
    """Índice de la primera columna True por fila; H si no hay ninguna."""
    h = mask.shape[1]
    has = mask.any(axis=1)
    return np.where(has, mask.argmax(axis=1), h)


def _sequence(first_mask: np.ndarray, second_mask: np.ndarray) -> np.ndarray:
    """Existe k1 < k2 con first_mask[k1] y second_mask[k2] (estricto: distinta vela)."""
    h = first_mask.shape[1]
    k1 = _first_true(first_mask)
    # suffix_any[:, j] = any(second_mask[:, j:])
    suffix_any = np.flip(np.logical_or.accumulate(np.flip(second_mask, 1), axis=1), 1)
    suffix_any = np.concatenate([suffix_any, np.zeros((len(k1), 1), bool)], axis=1)
    nxt = np.minimum(k1 + 1, h)
    return (k1 < h) & suffix_any[np.arange(len(k1)), nxt]


def apply_costs(entry: np.ndarray, exit_: np.ndarray, cfg: ResearchConfig,
                side: str | None = None) -> np.ndarray:
    """Modelo simple (escenario "custom"): todo como orden de mercado con tasas fijas."""
    side = side or cfg.POSITION_TYPE
    a = cfg.SLIPPAGE_RATE + cfg.SPREAD_RATE / 2.0
    c = cfg.COMMISSION_RATE
    if side == PositionSide.SHORT.value:
        ent = entry * (1.0 - a)
        return (ent * (1.0 - c) - exit_ * (1.0 + a) * (1.0 + c)) / ent
    return exit_ * (1.0 - a) * (1.0 - c) / (entry * (1.0 + a) * (1.0 + c)) - 1.0


def atr_at_entry(df: pd.DataFrame, period: int) -> np.ndarray:
    """ATR conocido al abrir la vela e: el de la vela de confirmación t = e-1 (cierre de t).
    atr_at_entry[e] = ATR[e-1]; NaN en e = 0 y durante el calentamiento del indicador."""
    a = atr_values(df, period)
    out = np.full(len(a), np.nan)
    out[1:] = a[:-1]
    return out


def atr_exit_levels(df: pd.DataFrame, cfg: ResearchConfig) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Niveles de TP y SL (precios) de una operación que entra en Open[e], para TODA vela e, y si son
    válidos. Sólo usan Open[e] y ATR[e-1] (información disponible al abrir la operación):
        LONG : TP = Open[e] + k_tp*ATR[e-1] ; SL = Open[e] - k_sl*ATR[e-1]
        SHORT: TP = Open[e] - k_tp*ATR[e-1] ; SL = Open[e] + k_sl*ATR[e-1]
    Inválido (NaN / False) si el ATR no está disponible o el SL de un LONG sería <= 0."""
    o = df["Open"].to_numpy("float64")
    a = atr_at_entry(df, cfg.EXIT_ATR_PERIOD)
    if cfg.POSITION_TYPE == PositionSide.SHORT.value:
        tp, sl = o - cfg.TP_ATR_MULT * a, o + cfg.SL_ATR_MULT * a
    else:
        tp, sl = o + cfg.TP_ATR_MULT * a, o - cfg.SL_ATR_MULT * a
    valid = np.isfinite(a) & (sl > 0) & (tp > 0)
    return np.where(valid, tp, np.nan), np.where(valid, sl, np.nan), valid


def build_outcome_table(df: pd.DataFrame, cfg: ResearchConfig) -> OutcomeTable:
    side = cfg.POSITION_TYPE
    short = side == PositionSide.SHORT.value
    n, H = len(df), cfg.MAX_HOLDING_BARS
    o = df["Open"].to_numpy("float64")
    h = df["High"].to_numpy("float64")
    l = df["Low"].to_numpy("float64")
    c = df["Close"].to_numpy("float64")

    m = n - H + 1            # entradas con horizonte completo: e = 0..m-1
    def full(dtype=float, fill=np.nan):
        return np.full(n, fill, dtype=dtype)
    tbl = OutcomeTable(full(), full(np.int8, -1), full(np.int16, -1), full(), full(), full(),
                       full(), full())
    if m <= 0:
        return tbl

    Ow, Hw, Lw, Cw = (sliding_window_view(x, H)[:m] for x in (o, h, l, c))
    P = o[:m]
    rows = np.arange(m)

    # "fav" = dirección que gana la posición, "adv" = la que pierde.
    def fav_hit(p):   # máscara (m, k): el precio se movió p a favor en la vela k
        return (Lw <= (P * (1 - p))[:, None]) if short else (Hw >= (P * (1 + p))[:, None])

    def adv_hit(p):   # máscara (m, k): el precio se movió p en contra en la vela k
        return (Hw >= (P * (1 + p))[:, None]) if short else (Lw <= (P * (1 - p))[:, None])

    def ret(x):       # retorno bruto de la posición al precio x
        return 1.0 - x / P if short else x / P - 1.0

    if cfg.EXIT_MODE == "atr":
        atr_e = atr_at_entry(df, cfg.EXIT_ATR_PERIOD)[:m]
        tp_p = cfg.TP_ATR_MULT * atr_e / P          # distancia relativa por entrada (array)
        sl_p = cfg.SL_ATR_MULT * atr_e / P
        valid_m = atr_exit_levels(df, cfg)[2][:m]
    else:
        tp_p, sl_p, valid_m = cfg.TP_PERCENT, cfg.SL_PERCENT, None
    tp = P * (1 - tp_p) if short else P * (1 + tp_p)
    sl = P * (1 + sl_p) if short else P * (1 - sl_p)
    k_tp, k_sl = _first_true(fav_hit(tp_p)), _first_true(adv_hit(sl_p))

    outcome = np.full(m, NONE, np.int8)
    outcome[k_tp < k_sl] = TP_FIRST
    outcome[k_sl < k_tp] = SL_FIRST
    outcome[(k_tp == k_sl) & (k_tp < H)] = AMBIGUOUS

    open_at_sl = Ow[rows, np.minimum(k_sl, H - 1)]
    sl_fill = np.maximum(sl, open_at_sl) if short else np.minimum(sl, open_at_sl)
    exit_price = Cw[:, H - 1].copy()
    exit_off = np.full(m, H - 1, np.int16)

    is_tp, is_sl, is_amb = outcome == TP_FIRST, outcome == SL_FIRST, outcome == AMBIGUOUS
    exit_price[is_tp] = tp[is_tp]
    exit_off[is_tp] = k_tp[is_tp]
    exit_price[is_sl] = sl_fill[is_sl]
    exit_off[is_sl] = k_sl[is_sl]
    exit_off[is_amb] = k_tp[is_amb]

    exit_kind = np.full(m, EXIT_TIME, np.int8)
    exit_kind[is_tp] = EXIT_TP
    exit_kind[is_sl] = EXIT_SL
    entry_idx = rows                      # vela de entrada e
    exit_idx = rows + exit_off            # vela en la que se ejecuta la salida
    ctx = MarketContext(df)
    pol = cfg.AMBIGUOUS_RETURN_POLICY

    gross = ret(exit_price)
    if is_amb.any():
        g_tp, g_sl = ret(tp), ret(sl_fill)
        g = {"worst": g_sl, "best": g_tp, "midpoint": (g_tp + g_sl) / 2}[pol]
        px = {"worst": sl_fill, "best": tp, "midpoint": (tp + sl_fill) / 2}[pol]
        gross[is_amb], exit_price[is_amb] = g[is_amb], px[is_amb]

    def net_for(scenario: str) -> np.ndarray:
        model = build_cost_model(scenario, cfg)
        net = model.net_return(side, P, exit_price, exit_kind, entry_idx, exit_idx, ctx)
        if is_amb.any():
            k_tp_kind = np.full(m, EXIT_TP, np.int8)
            k_sl_kind = np.full(m, EXIT_SL, np.int8)
            n_tp = model.net_return(side, P, tp, k_tp_kind, entry_idx, exit_idx, ctx)
            n_sl = model.net_return(side, P, sl_fill, k_sl_kind, entry_idx, exit_idx, ctx)
            nn = {"worst": n_sl, "best": n_tp, "midpoint": (n_tp + n_sl) / 2}[pol]
            net[is_amb] = nn[is_amb]
        return net

    scenarios = list(dict.fromkeys([cfg.COST_SCENARIO, *cfg.COST_SCENARIOS_REPORT]))
    nets = {sc: net_for(sc) for sc in scenarios}
    net = nets[cfg.COST_SCENARIO]
    if valid_m is not None:                 # sin ATR no hay operación: NaN, nunca un valor "plausible"
        net = np.where(valid_m, net, np.nan)
        gross = np.where(valid_m, gross, np.nan)
        outcome = np.where(valid_m, outcome, -1).astype(np.int8)
    for sc, arr in nets.items():
        full_arr = np.full(n, np.nan)
        full_arr[:m] = arr if valid_m is None else np.where(valid_m, arr, np.nan)
        tbl.net_by_scenario[sc] = full_arr
    tbl.cost_scenario = cfg.COST_SCENARIO

    tbl.tp_frac, tbl.sl_frac = full(), full()
    tbl.tp_frac[:m], tbl.sl_frac[:m] = tp_p, sl_p
    if valid_m is not None:
        tbl.entry_valid = np.zeros(n, bool)
        tbl.entry_valid[:m] = valid_m
    tbl.entry_price[:m] = P
    tbl.outcome[:m] = outcome
    tbl.exit_offset[:m] = exit_off
    tbl.exit_price[:m] = exit_price
    tbl.gross_return[:m] = gross
    tbl.net_return[:m] = net
    if short:
        tbl.mfe[:m] = 1.0 - Lw.min(axis=1) / P
        tbl.mae[:m] = 1.0 - Hw.max(axis=1) / P
    else:
        tbl.mfe[:m] = Hw.max(axis=1) / P - 1.0
        tbl.mae[:m] = Lw.min(axis=1) / P - 1.0

    # Resultados favorables generales (sección 20), desde el punto de vista de la posición
    for spec in cfg.FAVORABLE_OUTCOMES:
        name = favorable_name(spec)
        if spec.get("bars", 0) > H:
            log.warning("Se omite el resultado favorable %s: bars > MAX_HOLDING_BARS (%d).", name, H)
            continue
        t = spec["type"]
        arr = np.zeros(n, bool)
        if t == "reach":
            res = fav_hit(spec["p"])[:, :spec["bars"]].any(axis=1)
        elif t == "at_horizon":
            # retorno al cierre de la vela e+bars-1: `bars` velas después de la entrada
            res = ret(Cw[:, spec["bars"] - 1]) >= spec["p"]
        elif t == "down_then_up":
            res = _sequence(adv_hit(spec["p1"]), fav_hit(spec["p2"]))
        else:  # up_then_down
            res = _sequence(fav_hit(spec["p1"]), adv_hit(spec["p2"]))
        arr[:m] = res
        tbl.favorable[name] = arr
    return tbl
