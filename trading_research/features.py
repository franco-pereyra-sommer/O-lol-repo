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
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any
import weakref

import numpy as np
import pandas as pd

from .indicators import INDICATORS

# Memoria de cálculos intermedios compartidos entre operandos (sólo velocidad, nunca resultados):
# el ATR de un período dado y la geometría de las velas superiores se repiten en miles de operandos
# distintos sobre el MISMO DataFrame. Se guarda por objeto DataFrame y se libera cuando éste se
# destruye; los DataFrames recortados/perturbados de las pruebas de look-ahead son objetos nuevos.
_DF_CACHES: dict[int, dict] = {}


def _cache_for(df: pd.DataFrame) -> dict:
    k = id(df)
    c = _DF_CACHES.get(k)
    if c is None:
        c = _DF_CACHES[k] = {}
        weakref.finalize(df, _DF_CACHES.pop, k, None)
    return c


def _atr(df: pd.DataFrame, period: int) -> np.ndarray:
    c = _cache_for(df)
    key = ("atr", period)
    if key not in c:
        c[key] = Indicator("ATR", (period,)).compute(df)
    return c[key]


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
        a = _atr(df, self.period)
        return a / df["Close"].to_numpy(dtype="float64")

    def to_dict(self): return {"type": "atr_pct", "period": self.period}


@dataclass(frozen=True, repr=False)
class HTFTrend(Operand):
    """
    Tendencia en una temporalidad mayor (EXP-008): Close de la última vela superior COMPLETA dividido
    por la media de sus últimos n cierres (también de velas completas), menos 1. Positivo = por
    encima de su tendencia.

    Causalidad: la vela superior que contiene la vela i (de `base_min` minutos, abierta en ts_i) se
    considera completa al cierre de i sólo si ts_i + base cae exactamente en el borde de la vela
    superior; si no, se usa la vela superior anterior. Nunca se mira una vela superior abierta ni
    ninguna vela posterior a i. Las velas superiores se alinean al reloj UTC (época Unix):
    4h = 00,04,08…, 1D = 00:00 UTC (igual que Binance); la zona horaria del índice no influye
    (se usa la época UTC) y un índice sin zona se interpreta como UTC.
    """
    tf: str          # "4h" o "1D"
    n: int
    base_min: int = 60

    @property
    def key(self): return f"htf:{self.tf}:{self.n}:{self.base_min}"
    @property
    def label(self): return f"HTFTrend({self.tf},{self.n})"
    @property
    def scale(self): return f"htftrend_{self.tf}"

    def compute(self, df):
        c = _cache_for(df)
        gkey = ("htf", self.tf, self.base_min)
        if gkey not in c:
            ts = df.index.as_unit("ns").asi8.astype("int64")   # ns UTC (tz-aware: ya es UTC; la unidad puede ser s, ms, us)
            tf_ns = int(pd.Timedelta(self.tf).value)
            base_ns = int(self.base_min) * 60 * 10 ** 9
            bucket = ts // tf_ns
            new_run = np.r_[True, bucket[1:] != bucket[:-1]]
            rid = np.cumsum(new_run) - 1                   # índice de vela superior (por tramo)
            last = np.flatnonzero(np.r_[new_run[1:], True])   # última vela base de cada tramo
            final = ((ts + base_ns) % tf_ns) == 0          # esta vela cierra su vela superior
            c[gkey] = (rid, final, df["Close"].to_numpy(dtype="float64")[last])
        rid, final, hclose = c[gkey]
        sma = np.full(len(hclose), np.nan)
        if len(hclose) >= self.n:
            cs = np.cumsum(np.r_[0.0, hclose])
            sma[self.n - 1:] = (cs[self.n:] - cs[:-self.n]) / self.n
        trend = hclose / sma - 1.0
        k = np.where(final, rid, rid - 1)
        out = np.full(len(df), np.nan)
        ok = k >= 0
        out[ok] = trend[k[ok]]
        return out

    def to_dict(self): return {"type": "htf_trend", "tf": self.tf, "n": self.n, "base_min": self.base_min}


@dataclass(frozen=True, repr=False)
class RelativeVolatility(Operand):
    """Volatilidad relativa (EXP-008): ATR(corto) / ATR(largo). > 1 = la volatilidad reciente supera a su nivel de largo plazo."""
    short: int
    long: int

    @property
    def key(self): return f"relvol:{self.short}:{self.long}"
    @property
    def label(self): return f"ATR({self.short})/ATR({self.long})"
    @property
    def scale(self): return "relvol"

    def compute(self, df):
        a = _atr(df, self.short)
        b = _atr(df, self.long)
        with np.errstate(invalid="ignore", divide="ignore"):
            return a / b

    def to_dict(self): return {"type": "rel_vol", "short": self.short, "long": self.long}


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
    if t == "htf_trend":
        return HTFTrend(d["tf"], int(d["n"]), int(d.get("base_min", 60)))
    if t == "rel_vol":
        return RelativeVolatility(int(d["short"]), int(d["long"]))
    raise ValueError(f"Operando desconocido: {d}")


class FeatureStore:
    """
    Caché de series calculadas sobre un DataFrame OHLC.

    Ambas cachés tienen un tope de memoria (en MB). Al superarlo se descartan
    las entradas más viejas (FIFO); si se vuelven a pedir, se recalculan. Esto
    sólo afecta la velocidad, nunca los resultados.
    """

    def __init__(self, df: pd.DataFrame, max_feature_mb: float = 700.0,
                 max_signal_mb: float = 300.0):
        self.df = df
        self.n = len(df)
        self._cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self._bool_cache: OrderedDict[str, tuple] = OrderedDict()
        self._feature_bytes = 0
        self._signal_bytes = 0
        self.max_feature_bytes = int(max_feature_mb * 1e6)
        self.max_signal_bytes = int(max_signal_mb * 1e6)

    def get(self, op: Operand) -> np.ndarray:
        k = op.key
        arr = self._cache.get(k)
        if arr is None:
            arr = op.compute(self.df)
            self._cache[k] = arr
            self._feature_bytes += arr.nbytes
            while self._feature_bytes > self.max_feature_bytes and len(self._cache) > 1:
                _, old = self._cache.popitem(last=False)
                self._feature_bytes -= old.nbytes
        return arr

    # Caché de señales booleanas por condición (clave canónica).
    def get_bool(self, key: str):
        return self._bool_cache.get(key)

    def put_bool(self, key: str, pair) -> None:
        if key in self._bool_cache:
            return
        size = sum(a.nbytes for a in pair)
        self._bool_cache[key] = pair
        self._signal_bytes += size
        while self._signal_bytes > self.max_signal_bytes and len(self._bool_cache) > 1:
            _, old = self._bool_cache.popitem(last=False)
            self._signal_bytes -= sum(a.nbytes for a in old)
