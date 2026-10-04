"""
Generación aleatoria (reproducible) de condiciones.

Etapa 1: condiciones simples (Compare / Cross) con operandos y parámetros
         sorteados dentro de los rangos de la configuración.
Etapa 2: combinaciones (AND, OR, NOT, THEN, "X occurred within n AND Y")
         de un subconjunto de condiciones simples, respetando
         MAX_CONDITION_DEPTH.

Umbrales numéricos: en vez de rangos fijos por indicador (números mágicos),
se sortea un cuantil q ~ U(THRESHOLD_QUANTILE_RANGE) y se usa el valor de ese
cuantil de la distribución del operando calculada SÓLO sobre TRAIN. Así el
mismo mecanismo sirve para RSI, retornos, ratios de vela o cualquier operando
nuevo, sin filtrar información de VALIDATION/TEST.

Toda la aleatoriedad sale de un único `numpy.random.Generator` creado con
RANDOM_SEED, por lo que misma configuración + mismo seed => mismas condiciones.
"""
from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd

from .conditions import And, Compare, Condition, Cross, Not, OccurredWithin, Or, Then
from .config import ResearchConfig
from .features import (ATRPercent, CandleFeature, Constant, FeatureStore, HTFTrend, Indicator,
                       Operand, PriceField, RelativeVolatility, ReturnFeature)
from .indicators import param_ranges

log = logging.getLogger(__name__)

COMPARE_OPS = (">", ">=", "<", "<=")


def _round_sig(x: float, digits: int) -> float:
    if x == 0 or not math.isfinite(x):
        return 0.0
    return round(x, -int(math.floor(math.log10(abs(x)))) + (digits - 1))


class ConditionGenerator:
    def __init__(self, cfg: ResearchConfig, store: FeatureStore, train_slice: slice,
                 rng: np.random.Generator):
        self.cfg = cfg
        self.store = store
        self.train_slice = train_slice
        self.rng = rng
        self.ranges = param_ranges(cfg)
        self.base_min = max(1, int(round(pd.Timedelta(cfg.TIMEFRAME).total_seconds() / 60)))

    # ------------------------------------------------------------------ #
    # Operandos
    # ------------------------------------------------------------------ #
    def _randint(self, lo_hi: tuple[int, int]) -> int:
        lo, hi = lo_hi
        return int(self.rng.integers(lo, hi + 1))

    def _indicator(self, name: str, output: str = "value") -> Indicator:
        r = self.ranges[name]
        if name == "MACD":
            fast = self._randint(r["fast"])
            slow = self._randint(r["slow"])
            if slow <= fast:
                slow = fast + 1
            return Indicator("MACD", (fast, slow, self._randint(r["signal"])), output)
        return Indicator(name, (self._randint(r["period"]),), output)

    def _choice(self, seq):
        return seq[int(self.rng.integers(len(seq)))]

    def _price_like(self) -> Operand:
        """Operando en unidades de precio: OHLC o media móvil."""
        u = self.rng.random()
        if u < 0.35:
            return PriceField(self._choice(("Open", "High", "Low", "Close")) if u < 0.1 else "Close")
        return self._indicator(self._choice(("SMA", "EMA")))

    def _regime_operand(self, kind: str) -> Operand:
        c = self.cfg
        if kind == "htf4":
            return HTFTrend("4h", self._randint(c.HTF_TREND_PERIOD_RANGE_4H), self.base_min)
        if kind == "htf1d":
            return HTFTrend("1D", self._randint(c.HTF_TREND_PERIOD_RANGE_1D), self.base_min)
        return RelativeVolatility(self._randint(c.RELVOL_SHORT_RANGE), self._randint(c.RELVOL_LONG_RANGE))

    def _threshold_operand(self) -> Operand:
        """Operandos con escala estable en el tiempo (aptos para umbral fijo)."""
        kinds = ("rsi", "return", "candle", "atr_pct", "macd_zero")
        if self.cfg.REGIME_FEATURES:
            kinds += ("htf4", "htf1d", "relvol")
        kind = self._choice(kinds)
        if kind in ("htf4", "htf1d", "relvol"):
            return self._regime_operand(kind)
        if kind == "rsi":
            return self._indicator("RSI")
        if kind == "return":
            return ReturnFeature(int(self._choice(self.cfg.RETURN_PERIODS)))
        if kind == "candle":
            return CandleFeature(self._choice(("body_ratio", "upper_wick_ratio", "lower_wick_ratio")))
        if kind == "atr_pct":
            r = self.ranges["ATR"]["period"]
            return ATRPercent(self._randint(r))
        return self._indicator("MACD", self._choice(("line", "hist")))

    def _threshold_for(self, op: Operand) -> Constant:
        # Las salidas de MACD están en unidades de precio (no estacionarias):
        # el único umbral fijo con sentido es 0.
        if isinstance(op, Indicator) and op.name == "MACD":
            return Constant(0.0)
        vals = self.store.get(op)[self.train_slice]
        vals = vals[np.isfinite(vals)]
        if len(vals) == 0:
            return Constant(0.0)
        lo, hi = self.cfg.THRESHOLD_QUANTILE_RANGE
        q = float(self.rng.uniform(lo, hi))
        return Constant(_round_sig(float(np.quantile(vals, q)), self.cfg.THRESHOLD_SIGNIFICANT_DIGITS))

    def _operand_pair(self) -> tuple[Operand, Operand]:
        """Dos operandos de la MISMA escala y distintos entre sí."""
        fams = ("price", "price", "rsi", "macd", "atr_pct", "return", "candle")
        if self.cfg.REGIME_FEATURES:
            fams += ("htf4", "htf1d", "relvol")
        fam = self._choice(fams)
        for _ in range(20):
            if fam in ("htf4", "htf1d", "relvol"):
                a, b = self._regime_operand(fam), self._regime_operand(fam)
            elif fam == "price":
                a, b = self._price_like(), self._price_like()
            elif fam == "rsi":
                a, b = self._indicator("RSI"), self._indicator("RSI")
            elif fam == "macd":
                a = self._indicator("MACD", "line")
                b = Indicator("MACD", a.params, "signal")
            elif fam == "atr_pct":
                r = self.ranges["ATR"]["period"]
                a, b = ATRPercent(self._randint(r)), ATRPercent(self._randint(r))
            elif fam == "return":
                a = ReturnFeature(int(self._choice(self.cfg.RETURN_PERIODS)))
                b = ReturnFeature(int(self._choice(self.cfg.RETURN_PERIODS)))
            else:
                names = ["body_ratio", "upper_wick_ratio", "lower_wick_ratio"]
                a, b = CandleFeature(self._choice(names)), CandleFeature(self._choice(names))
            if a.key != b.key and a.scale == b.scale:
                return a, b
        return PriceField("Close"), PriceField("Open")

    # ------------------------------------------------------------------ #
    # Etapa 1
    # ------------------------------------------------------------------ #
    def random_simple(self) -> Condition:
        kinds = list(self.cfg.SIMPLE_KIND_WEIGHTS)
        w = np.array([self.cfg.SIMPLE_KIND_WEIGHTS[k] for k in kinds], dtype=float)
        kind = kinds[int(self.rng.choice(len(kinds), p=w / w.sum()))]
        if kind == "compare_const":
            a = self._threshold_operand()
            return Compare(a, self._choice(COMPARE_OPS), self._threshold_for(a))
        if kind == "compare_operand":
            a, b = self._operand_pair()
            return Compare(a, self._choice(COMPARE_OPS), b)
        direction = self._choice(("above", "below"))
        if kind == "cross_const":
            a = self._threshold_operand()
            return Cross(a, self._threshold_for(a), direction)
        a, b = self._operand_pair()
        return Cross(a, b, direction)

    def generate_simple(self, n: int) -> list[Condition]:
        out, seen = [], set()
        attempts = 0
        while len(out) < n and attempts < n * 50:
            attempts += 1
            c = self.random_simple()
            if c.key in seen:
                continue
            seen.add(c.key)
            out.append(c)
        log.info("Etapa 1: %d condiciones simples generadas (%d intentos).", len(out), attempts)
        return out

    # ------------------------------------------------------------------ #
    # Etapa 2
    # ------------------------------------------------------------------ #
    def _window(self) -> int:
        return self._randint(self.cfg.TEMPORAL_WINDOW_RANGE)

    def _build(self, pool: list[Condition], budget: int) -> Condition:
        """Árbol aleatorio con profundidad <= budget (budget >= 1)."""
        if budget <= 1:
            return self._choice(pool)
        ops = list(self.cfg.COMPLEX_OPERATOR_WEIGHTS)
        w = np.array([self.cfg.COMPLEX_OPERATOR_WEIGHTS[k] for k in ops], dtype=float)
        op = ops[int(self.rng.choice(len(ops), p=w / w.sum()))]

        def child() -> Condition:
            # hijos de profundidad aleatoria entre 1 y budget-1
            return self._build(pool, int(self.rng.integers(1, budget)))

        if op == "NOT":
            c = child()
            return c.a if isinstance(c, Not) else Not(c)
        a, b = child(), child()
        if op == "AND":
            return And(a, b)
        if op == "OR":
            return Or(a, b)
        if op == "THEN":
            return Then(a, b, self._window())
        return And(OccurredWithin(a, self._window()), b)  # WITHIN_AND

    def generate_complex(self, pool: list[Condition], n: int, max_depth: int,
                         exclude_keys: set[str] | None = None) -> list[Condition]:
        if max_depth < 2 or not pool:
            log.info("Etapa 2 omitida (MAX_CONDITION_DEPTH=%d, pool=%d).", max_depth, len(pool))
            return []
        seen = set(exclude_keys or ())
        out: list[Condition] = []
        attempts = 0
        while len(out) < n and attempts < n * 50:
            attempts += 1
            c = self._build(pool, max_depth)
            if c.depth < 2 or c.depth > max_depth or c.key in seen:
                continue
            # descartar combinaciones triviales A op A
            lk = [l.key for l in c.leaves()]
            if len(set(lk)) < len(lk):
                continue
            seen.add(c.key)
            out.append(c)
        log.info("Etapa 2: %d condiciones complejas generadas (%d intentos).", len(out), attempts)
        return out
