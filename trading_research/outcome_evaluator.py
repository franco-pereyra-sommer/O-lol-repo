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

Costos (por operación completa; a = slippage + spread/2, c = comisión):
  LONG : compra a P(1+a), vende a X(1-a)
         neto = X(1-a)(1-c) / (P(1+a)(1+c)) - 1
  SHORT: vende a P(1-a), recompra a X(1+a)
         neto = [P(1-a)(1-c) - X(1+a)(1+c)] / (P(1-a))

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
    side = side or cfg.POSITION_TYPE
    a = cfg.SLIPPAGE_RATE + cfg.SPREAD_RATE / 2.0
    c = cfg.COMMISSION_RATE
    if side == PositionSide.SHORT.value:
        ent = entry * (1.0 - a)
        return (ent * (1.0 - c) - exit_ * (1.0 + a) * (1.0 + c)) / ent
    return exit_ * (1.0 - a) * (1.0 - c) / (entry * (1.0 + a) * (1.0 + c)) - 1.0


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

    tp = P * (1 - cfg.TP_PERCENT) if short else P * (1 + cfg.TP_PERCENT)
    sl = P * (1 + cfg.SL_PERCENT) if short else P * (1 - cfg.SL_PERCENT)
    k_tp, k_sl = _first_true(fav_hit(cfg.TP_PERCENT)), _first_true(adv_hit(cfg.SL_PERCENT))

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

    gross = ret(exit_price)
    net = apply_costs(P, exit_price, cfg, side)
    if is_amb.any():
        g_tp, g_sl = ret(tp), ret(sl_fill)
        n_tp, n_sl = apply_costs(P, tp, cfg, side), apply_costs(P, sl_fill, cfg, side)
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
