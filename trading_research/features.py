"""
Operandos: todo lo que puede aparecer a un lado de una comparación.

  PriceField("Close")            -> Close[t]
  Indicator("EMA", (50,))        -> EMA(50)[t]
  Indicator("MACD", (12,26,9), "signal")
  CandleFeature("body_ratio")    -> body/range de la vela t
  ReturnFeature(5)               -> Close[t]/Close[t-5] - 1
  ATRPercent(14)                 -> ATR(14)[t]/Close[t]
  Constant(30.0)

Cada operando tiene:
  - key   : identificador canónico único (para caché y deduplicación)
  - label : texto legible
  - scale : familia de unidades; sólo se comparan operandos de la misma escala
  - compute(df) -> np.ndarray (float64, NaN donde no hay datos suficientes)

`FeatureStore` calcula cada operando UNA vez y lo reutiliza en todas las
condiciones. Todo cálculo es causal (sólo usa velas <= t).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .indicators import INDICATORS


class Operand(ABC):
    @property
    @abstractmethod
    def key(self) -> str: ...

    @property
    @abstractmethod
    def label(self) -> str: ...

    @property
    @abstractmethod
    def scale(self) -> str: ...

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> np.ndarray: ...

    @abstractmethod
    def to_dict(self) -> dict[str, Any]: ...

    def __repr__(self) -> str:
        return self.label


@dataclass(frozen=True, repr=False)
class PriceField(Operand):
    field: str  # Open | High | Low | Close

    @property
    def key(self): return f"price:{self.field}"
    @property
    def label(self): return self.field
    @property
    def scale(self): return "price"
    def compute(self, df): return df[self.field].to_numpy(dtype="float64")
    def to_dict(self): return {"type": "price", "field": self.field}


@dataclass(frozen=True, repr=False)
class Indicator(Operand):
    name: str
    params: tuple[int, ...]
    output: str = "value"

    @property
    def key(self): return f"ind:{self.name}{self.params}:{self.output}"

    @property
    def label(self):
        p = ",".join(map(str, self.params))
        if self.name == "MACD":
            f, s, g = self.params
            return {"line": f"MACD({f},{s})", "signal": f"Signal({f},{s},{g})",
                    "hist": f"MACDHist({f},{s},{g})"}[self.output]
        return f"{INDICATORS[self.name].label}({p})"

    @property
    def scale(self):
        sc = INDICATORS[self.name].outputs[self.output]
        # Las salidas de MACD sólo son comparables dentro del mismo (fast, slow)
        return f"macd{self.params[:2]}" if sc == "macd" else sc

    def compute(self, df):
        d = INDICATORS[self.name]
        kwargs = dict(zip(d.params, self.params))
        return d.func(df, **kwargs)[self.output].to_numpy(dtype="float64")

    def to_dict(self):
        return {"type": "indicator", "name": self.name, "params": list(self.params),
                "output": self.output}


CANDLE_FEATURES = ("body", "range", "upper_wick", "lower_wick",
                   "body_ratio", "upper_wick_ratio", "lower_wick_ratio")


@dataclass(frozen=True, repr=False)
class CandleFeature(Operand):
    name: str

    @property
    def key(self): return f"candle:{self.name}"

    @property
    def label(self):
        return {"body_ratio": "body/range", "upper_wick_ratio": "upper_wick/range",
                "lower_wick_ratio": "lower_wick/range"}.get(self.name, self.name)

    @property
    def scale(self):
        # body, range y wicks están en unidades de precio absolutas: no son
        # comparables con un umbral fijo a lo largo de años de datos. Se los
        # expone, pero el generador sólo usa los ratios (adimensionales).
        return "candle_ratio" if self.name.endswith("_ratio") else "candle_abs"

    def compute(self, df):
        o, h, l, c = (df[k].to_numpy(dtype="float64") for k in ("Open", "High", "Low", "Close"))
        body = np.abs(c - o)
        rng = h - l
        upper = h - np.maximum(o, c)
        lower = np.minimum(o, c) - l
        with np.errstate(divide="ignore", invalid="ignore"):
            safe = np.where(rng > 0, rng, np.nan)   # vela sin rango -> ratio NaN
            vals = {"body": body, "range": rng, "upper_wick": upper, "lower_wick": lower,
                    "body_ratio": body / safe, "upper_wick_ratio": upper / safe,
                    "lower_wick_ratio": lower / safe}
        return vals[self.name]

    def to_dict(self): return {"type": "candle", "name": self.name}


@dataclass(frozen=True, repr=False)
class ReturnFeature(Operand):
    n: int

    @property
    def key(self): return f"ret:{self.n}"
    @property
    def label(self): return f"return(Close,{self.n})"
    @property
    def scale(self): return "return"

    def compute(self, df):
        c = df["Close"].to_numpy(dtype="float64")
        out = np.full_like(c, np.nan)
        out[self.n:] = c[self.n:] / c[:-self.n] - 1.0
        return out

    def to_dict(self): return {"type": "return", "n": self.n}


@dataclass(frozen=True, repr=False)
class ATRPercent(Operand):
    """ATR normalizado por el precio: permite umbrales fijos de volatilidad."""
    period: int

    @property
    def key(self): return f"atrpct:{self.period}"
    @property
    def label(self): return f"ATR({self.period})/Close"
    @property
    def scale(self): return "atr_pct"

    def compute(self, df):
        a = Indicator("ATR", (self.period,)).compute(df)
        return a / df["Close"].to_numpy(dtype="float64")

    def to_dict(self): return {"type": "atr_pct", "period": self.period}


@dataclass(frozen=True, repr=False)
class Constant(Operand):
    value: float

    @property
    def key(self): return f"const:{self.value!r}"
    @property
    def label(self): return f"{self.value:g}"
    @property
    def scale(self): return "constant"
    def compute(self, df): return np.full(len(df), self.value, dtype="float64")
    def to_dict(self): return {"type": "const", "value": self.value}


def operand_from_dict(d: dict[str, Any]) -> Operand:
    t = d["type"]
    if t == "price":
        return PriceField(d["field"])
    if t == "indicator":
        return Indicator(d["name"], tuple(d["params"]), d.get("output", "value"))
    if t == "candle":
        return CandleFeature(d["name"])
    if t == "return":
        return ReturnFeature(int(d["n"]))
    if t == "atr_pct":
        return ATRPercent(int(d["period"]))
    if t == "const":
        return Constant(float(d["value"]))
    raise ValueError(f"Operando desconocido: {d}")


class FeatureStore:
    """Caché de series calculadas sobre un DataFrame OHLC."""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.n = len(df)
        self._cache: dict[str, np.ndarray] = {}
        self._bool_cache: dict[str, np.ndarray] = {}
        self.max_bool_cache = 4000

    def get(self, op: Operand) -> np.ndarray:
        k = op.key
        if k not in self._cache:
            self._cache[k] = op.compute(self.df)
        return self._cache[k]

    # Caché opcional de señales booleanas por condición (clave canónica).
    def get_bool(self, key: str):
        return self._bool_cache.get(key)

    def put_bool(self, key: str, arr: np.ndarray) -> None:
        # Límite de memoria: cada entrada son 2 arrays bool de len(df).
        if len(self._bool_cache) < self.max_bool_cache:
            self._bool_cache[key] = arr
