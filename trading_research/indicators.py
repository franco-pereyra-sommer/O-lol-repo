"""
Indicadores técnicos. Todos son CAUSALES: el valor en t usa sólo velas <= t.

Para agregar un indicador:
  1. escribir una función `f(df, **params) -> dict[str, pd.Series]`
  2. registrarla en `INDICATORS` con sus parámetros, salidas y "escala"
     (la escala dice con qué otros operandos tiene sentido compararlo).
  3. agregar su rango de parámetros en config y en `param_ranges`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from .config import ResearchConfig


def sma(df: pd.DataFrame, period: int) -> dict[str, pd.Series]:
    return {"value": df["Close"].rolling(period, min_periods=period).mean()}


def ema(df: pd.DataFrame, period: int) -> dict[str, pd.Series]:
    # adjust=False => recursión clásica EMA_t = a*x_t + (1-a)*EMA_{t-1}
    s = df["Close"].ewm(span=period, adjust=False, min_periods=period).mean()
    return {"value": s}


def _wilder(x: pd.Series, period: int) -> pd.Series:
    """Suavizado de Wilder (RMA): alpha = 1/period."""
    return x.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def rsi(df: pd.DataFrame, period: int) -> dict[str, pd.Series]:
    delta = df["Close"].diff()
    gain = _wilder(delta.clip(lower=0.0), period)
    loss = _wilder((-delta).clip(lower=0.0), period)
    rs = gain / loss
    out = 100.0 - 100.0 / (1.0 + rs)
    # loss == 0 -> RSI = 100 ; gain == loss == 0 -> 50
    out = out.where(loss != 0, 100.0)
    out = out.where(~((gain == 0) & (loss == 0)), 50.0)
    out[gain.isna() | loss.isna()] = np.nan
    return {"value": out}


def macd(df: pd.DataFrame, fast: int, slow: int, signal: int) -> dict[str, pd.Series]:
    c = df["Close"]
    ema_fast = c.ewm(span=fast, adjust=False, min_periods=fast).mean()
    ema_slow = c.ewm(span=slow, adjust=False, min_periods=slow).mean()
    line = ema_fast - ema_slow
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return {"line": line, "signal": sig, "hist": line - sig}


def atr(df: pd.DataFrame, period: int) -> dict[str, pd.Series]:
    prev_close = df["Close"].shift(1)
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - prev_close).abs(),
                    (df["Low"] - prev_close).abs()], axis=1).max(axis=1)
    tr.iloc[0] = df["High"].iloc[0] - df["Low"].iloc[0]
    return {"value": _wilder(tr, period)}


@dataclass(frozen=True)
class IndicatorDef:
    func: Callable[..., dict[str, pd.Series]]
    params: tuple[str, ...]
    outputs: dict[str, str]     # salida -> escala
    label: str


# Escalas: "price" (unidades de precio), "rsi" (0-100), "macd" (diferencia de
# EMAs; comparable con 0 y con otras salidas del MISMO MACD), "atr".
INDICATORS: dict[str, IndicatorDef] = {
    "SMA": IndicatorDef(sma, ("period",), {"value": "price"}, "SMA"),
    "EMA": IndicatorDef(ema, ("period",), {"value": "price"}, "EMA"),
    "RSI": IndicatorDef(rsi, ("period",), {"value": "rsi"}, "RSI"),
    "MACD": IndicatorDef(macd, ("fast", "slow", "signal"),
                         {"line": "macd", "signal": "macd", "hist": "macd"}, "MACD"),
    "ATR": IndicatorDef(atr, ("period",), {"value": "atr"}, "ATR"),
}


def param_ranges(cfg: ResearchConfig) -> dict[str, dict[str, tuple[int, int]]]:
    """Rangos de parámetros explorables, tomados de la configuración."""
    return {
        "SMA": {"period": cfg.SMA_PERIOD_RANGE},
        "EMA": {"period": cfg.EMA_PERIOD_RANGE},
        "RSI": {"period": cfg.RSI_PERIOD_RANGE},
        "ATR": {"period": cfg.ATR_PERIOD_RANGE},
        "MACD": {"fast": cfg.MACD_FAST_RANGE, "slow": cfg.MACD_SLOW_RANGE,
                 "signal": cfg.MACD_SIGNAL_RANGE},
    }
