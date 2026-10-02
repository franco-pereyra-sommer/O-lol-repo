"""
Qué ocurrió después de cada entrada.

Clave de eficiencia: el resultado de una operación depende SÓLO de la vela de
entrada e (y de TP, SL, H, costos), no de qué condición la generó. Por eso se
calcula una única vez una `OutcomeTable` con el resultado hipotético de entrar
en CADA vela, y cada condición simplemente indexa esa tabla.

Definiciones (LONG), con P = Open[e] y ventana k = 0..H-1 (velas e..e+H-1):

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

Costos (por operación completa):
  P_ent_ef = P   (1 + slippage + spread/2)
  P_sal_ef = P_s (1 - slippage - spread/2)
  neto     = P_sal_ef (1 - comisión) / (P_ent_ef (1 + comisión)) - 1
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from .config import PositionSide, ResearchConfig

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


def apply_costs(entry: np.ndarray, exit_: np.ndarray, cfg: ResearchConfig) -> np.ndarray:
    adv = cfg.SLIPPAGE_RATE + cfg.SPREAD_RATE / 2.0
    ent = entry * (1.0 + adv)
    ex = exit_ * (1.0 - adv)
    return ex * (1.0 - cfg.COMMISSION_RATE) / (ent * (1.0 + cfg.COMMISSION_RATE)) - 1.0


def build_outcome_table(df: pd.DataFrame, cfg: ResearchConfig) -> OutcomeTable:
    if cfg.POSITION_TYPE != PositionSide.LONG.value:
        raise NotImplementedError("SHORT: invertir TP/SL, High/Low y el signo de los retornos.")

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
    tp = P * (1 + cfg.TP_PERCENT)
    sl = P * (1 - cfg.SL_PERCENT)

    hit_tp = Hw >= tp[:, None]
    hit_sl = Lw <= sl[:, None]
    k_tp, k_sl = _first_true(hit_tp), _first_true(hit_sl)

    outcome = np.full(m, NONE, np.int8)
    outcome[k_tp < k_sl] = TP_FIRST
    outcome[k_sl < k_tp] = SL_FIRST
    outcome[(k_tp == k_sl) & (k_tp < H)] = AMBIGUOUS

    rows = np.arange(m)
    sl_fill = np.minimum(sl, Ow[rows, np.minimum(k_sl, H - 1)])
    exit_price = Cw[:, H - 1].copy()
    exit_off = np.full(m, H - 1, np.int16)

    is_tp, is_sl, is_amb = outcome == TP_FIRST, outcome == SL_FIRST, outcome == AMBIGUOUS
    exit_price[is_tp] = tp[is_tp]
    exit_off[is_tp] = k_tp[is_tp]
    exit_price[is_sl] = sl_fill[is_sl]
    exit_off[is_sl] = k_sl[is_sl]
    exit_off[is_amb] = k_tp[is_amb]

    gross = exit_price / P - 1.0
    net = apply_costs(P, exit_price, cfg)
    if is_amb.any():
        g_tp, g_sl = tp / P - 1.0, sl_fill / P - 1.0
        n_tp, n_sl = apply_costs(P, tp, cfg), apply_costs(P, sl_fill, cfg)
        pol = cfg.AMBIGUOUS_RETURN_POLICY
        if pol == "worst":
            g, nn, px = g_sl, n_sl, sl_fill
        elif pol == "best":
            g, nn, px = g_tp, n_tp, tp
        else:
            g, nn, px = (g_tp + g_sl) / 2, (n_tp + n_sl) / 2, (tp + sl_fill) / 2
        gross[is_amb], net[is_amb], exit_price[is_amb] = g[is_amb], nn[is_amb], px[is_amb]

    tbl.entry_price[:m] = P
    tbl.outcome[:m] = outcome
    tbl.exit_offset[:m] = exit_off
    tbl.exit_price[:m] = exit_price
    tbl.gross_return[:m] = gross
    tbl.net_return[:m] = net
    tbl.mfe[:m] = Hw.max(axis=1) / P - 1.0
    tbl.mae[:m] = Lw.min(axis=1) / P - 1.0

    # Resultados favorables generales (sección 20)
    for spec in cfg.FAVORABLE_OUTCOMES:
        name = favorable_name(spec)
        t = spec["type"]
        arr = np.zeros(n, bool)
        if t == "reach":
            b = spec["bars"]
            res = (Hw[:, :b] >= (P * (1 + spec["p"]))[:, None]).any(axis=1)
        elif t == "at_horizon":
            # retorno medido al cierre de la vela e+bars-1, es decir, exactamente
            # `bars` velas después del instante de entrada (apertura de e).
            b = spec["bars"]
            res = Cw[:, b - 1] / P - 1.0 >= spec["p"]
        elif t == "down_then_up":
            res = _sequence(Lw <= (P * (1 - spec["p1"]))[:, None],
                            Hw >= (P * (1 + spec["p2"]))[:, None])
        else:  # up_then_down
            res = _sequence(Hw >= (P * (1 + spec["p1"]))[:, None],
                            Lw <= (P * (1 - spec["p2"]))[:, None])
        arr[:m] = res
        tbl.favorable[name] = arr
    return tbl
