"""
Pruebas de look-ahead a nivel de operandos, señales y entradas (EXP-006), inspiradas en
`lookahead-analysis` y `recursive-analysis` de Freqtrade: se calcula todo con la historia
completa y se vuelve a calcular con información modificada hacia el futuro; hasta la vela k los
resultados tienen que ser idénticos.

Modificaciones del futuro (velas > k):
  truncate : se borran.
  perturb  : se reemplazan por un camino de precios y volúmenes distinto (detecta código que
             "mira" adelante sin que el truncado cambie la forma del arreglo, p. ej. un
             z-score con la media de toda la muestra, o un rolling centrado).

Niveles:
  1. operandos (indicadores, velas, retornos…): valores en t <= k.
  2. condiciones (señal booleana, incluye cruces, Then, etc.): señal en t <= k.
  3. entradas: tras el cooldown/until_exit y la tabla de resultados, las entradas con confirmación
     t <= k - H y sus retornos netos coinciden entre datos truncados y completos.
Adicional (informativo, no es look-ahead): sensibilidad al punto de partida de los datos
("recursive-analysis"): indicadores recursivos (EMA, RSI, ATR) dependen del largo de la historia.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import ResearchConfig
from .conditions import Condition
from .entry_detector import Segment, detect_entries
from .features import FeatureStore, Operand
from .outcome_evaluator import atr_exit_levels, build_outcome_table


class RecordingStore(FeatureStore):
    """FeatureStore que recuerda qué operandos se pidieron (para auditarlos uno por uno)."""

    def __init__(self, df: pd.DataFrame, *a, **kw):
        super().__init__(df, *a, **kw)
        self.operands: dict[str, Operand] = {}

    def get(self, op: Operand) -> np.ndarray:
        self.operands[op.key] = op
        return super().get(op)


def truncate(df: pd.DataFrame, k: int) -> pd.DataFrame:
    return df.iloc[: k + 1]


def perturb_future(df: pd.DataFrame, k: int, rng: np.random.Generator) -> pd.DataFrame:
    """Mismas velas hasta k; después, precios (OHLC escalados juntos: se conserva la coherencia
    High >= Open/Close >= Low) y volumen de otro camino aleatorio."""
    out = df.copy()
    m = len(df) - (k + 1)
    if m <= 0:
        return out
    f = np.exp(np.cumsum(rng.normal(0.0, 0.05, m)))
    for col in ("Open", "High", "Low", "Close"):
        out.iloc[k + 1:, out.columns.get_loc(col)] = df[col].to_numpy()[k + 1:] * f
    if "Volume" in out.columns:
        out.iloc[k + 1:, out.columns.get_loc("Volume")] = (
            df["Volume"].to_numpy()[k + 1:] * rng.uniform(0.2, 5.0, m))
    return out


def modified(df: pd.DataFrame, k: int, mode: str, rng: np.random.Generator) -> pd.DataFrame:
    if mode == "truncate":
        return truncate(df, k)
    if mode == "perturb":
        return perturb_future(df, k, rng)
    raise ValueError(mode)


def _same(a: np.ndarray, b: np.ndarray, rtol: float = 1e-9, atol: float = 1e-12) -> bool:
    return bool(np.allclose(a, b, rtol=rtol, atol=atol, equal_nan=True))


def check_operands(df: pd.DataFrame, operands: dict[str, Operand], ks: list[int],
                   rng: np.random.Generator, modes=("truncate", "perturb")) -> dict[str, int]:
    """Por operando: cantidad de (modo, k) en los que el valor en t <= k cambió."""
    full = {key: op.compute(df) for key, op in operands.items()}
    fails = {key: 0 for key in operands}
    for mode in modes:
        for k in ks:
            d2 = modified(df, k, mode, rng)
            for key, op in operands.items():
                if not _same(full[key][: k + 1], op.compute(d2)[: k + 1]):
                    fails[key] += 1
    return fails


def check_conditions(df: pd.DataFrame, conds: list[Condition], ks: list[int],
                     rng: np.random.Generator, modes=("truncate", "perturb")) -> dict[str, int]:
    """Por condición: cantidad de (modo, k) en los que la señal en t <= k cambió."""
    store = FeatureStore(df)
    full = {c.key: c.evaluate(store) for c in conds}
    fails = {c.key: 0 for c in conds}
    for mode in modes:
        for k in ks:
            st = FeatureStore(modified(df, k, mode, rng))
            for c in conds:
                if not np.array_equal(full[c.key][: k + 1], c.evaluate(st)[: k + 1]):
                    fails[c.key] += 1
    return fails


def check_entries(df: pd.DataFrame, signals: dict, cfg: ResearchConfig,
                  ks: list[int]) -> dict[str, int]:
    """Por señal: (k) en los que difieren las entradas con confirmación t <= k-H o sus retornos
    netos, entre la corrida con datos truncados en k y la corrida con todos los datos.
    `signals`: clave -> arreglo booleano ya calculado (sólo prueba cooldown/tabla/costos) o función
    df -> arreglo booleano (prueba también el cálculo de la señal, de punta a punta)."""
    H, n = cfg.MAX_HOLDING_BARS, len(df)
    table = build_outcome_table(df, cfg)
    sig_full = {key: (s(df) if callable(s) else s) for key, s in signals.items()}
    full = {key: detect_entries(s, Segment("F", 0, n), H, cfg.MIN_BARS_BETWEEN_SAME_CONDITION_ENTRIES,
                                cfg.COOLDOWN_MODE, table.exit_offset) for key, s in sig_full.items()}
    fails = {key: 0 for key in signals}
    for k in ks:
        if k - H <= 0:
            continue
        tt = build_outcome_table(df.iloc[: k + 1], cfg)
        for key, s in signals.items():
            st = s(df.iloc[: k + 1]) if callable(s) else s[: k + 1]
            d = detect_entries(st, Segment("T", 0, k + 1), H,
                               cfg.MIN_BARS_BETWEEN_SAME_CONDITION_ENTRIES, cfg.COOLDOWN_MODE,
                               tt.exit_offset)
            f = full[key]
            want = f.confirm_idx[f.confirm_idx <= k - H]
            ok = np.array_equal(want, d.confirm_idx)
            # La purga por horizonte descarta las últimas H confirmaciones del tramo truncado, así
            # que una fuga corta (< H velas) no se vería sólo en las entradas: se compara también
            # la señal misma hasta k.
            if callable(s):
                ok &= bool(np.array_equal(st, sig_full[key][: k + 1]))
            if ok and len(want):
                e = want + 1
                for sc, arr in table.net_by_scenario.items():
                    ok &= _same(arr[e], tt.net_by_scenario[sc][e])
                ok &= _same(table.gross_return[e], tt.gross_return[e])
            fails[key] += 0 if ok else 1
    return fails


def check_exit_levels(df: pd.DataFrame, cfg: ResearchConfig, ks: list[int],
                      rng: np.random.Generator, modes=("truncate", "perturb")) -> dict[str, int]:
    """EXP-010: los niveles de TP y SL (y su validez) de toda operación que abre en e <= k no cambian
    si se borra o se reemplaza el futuro (velas > k). Sólo pueden depender de Open[e] y ATR[e-1]."""
    tp, sl, ok = atr_exit_levels(df, cfg)
    fails = {"tp": 0, "sl": 0, "valid": 0}
    for mode in modes:
        for k in ks:
            d2 = modified(df, k, mode, rng)
            tp2, sl2, ok2 = atr_exit_levels(d2, cfg)
            fails["tp"] += int(not _same(tp[: k + 1], tp2[: k + 1]))
            fails["sl"] += int(not _same(sl[: k + 1], sl2[: k + 1]))
            fails["valid"] += int(not np.array_equal(ok[: k + 1], ok2[: k + 1]))
    return fails


def startup_sensitivity(df: pd.DataFrame, operands: dict[str, Operand], starts: list[int],
                        after: int = 2000, rtol: float = 1e-6) -> dict[str, int]:
    """Informativo ("recursive-analysis"): cuántos de los `starts` hacen que el operando, calculado
    sobre df[s:], difiera del calculado sobre df completo en alguna vela >= s + after. Un valor > 0
    en un operando recursivo no es look-ahead: significa que el backtest y una ejecución que
    arranca con menos historia no ven exactamente la misma señal."""
    full = {key: op.compute(df) for key, op in operands.items()}
    out = {key: 0 for key in operands}
    for s in starts:
        sub = df.iloc[s:]
        for key, op in operands.items():
            a, b = full[key][s + after:], op.compute(sub)[after:]
            if not _same(a, b, rtol=rtol, atol=1e-9):
                out[key] += 1
    return out
