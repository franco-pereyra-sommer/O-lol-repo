"""
Modelo de costos de ejecución.

Separa el precio TEÓRICO de una operación del precio EFECTIVO y de los costos:

    señal en t ──> entrada teórica Open[t+1] ──> precio efectivo ──> comisión ──> neto
                   salida teórica (TP/SL/tiempo) ──> precio efectivo ──> comisión

Tres componentes independientes e intercambiables:

  FeeModel       comisión según exchange / mercado / tipo de orden (maker o taker)
  SpreadModel    medio spread que se paga al cruzar el libro con una orden de mercado
  SlippageModel  diferencia adicional entre el precio de referencia y el ejecutado

Tipo de orden de cada tramo (configurable):
  entrada         orden de mercado en la apertura   -> taker + medio spread + slippage
  salida por TP   orden límite ya colocada (maker)  -> maker, sin spread ni slippage
                  (o de mercado si TP_ORDER_TYPE = "taker")
  salida por SL   stop de mercado                   -> taker + medio spread + slippage
                  (además, si la vela abre con gap más allá del SL, se ejecuta en
                   la apertura: eso ya lo resuelve outcome_evaluator)
  salida por tiempo orden de mercado al cierre       -> taker + medio spread + slippage

IMPORTANTE: con datos OHLC no se puede observar el spread ni el slippage
históricos. Los valores de los escenarios son ESTIMACIONES, no datos
observados. La interfaz permite reemplazarlos más adelante por modelos con
bid/ask u order book histórico sin tocar el resto del sistema.

Los costos sólo cambian el resultado económico de una operación. Nunca
intervienen en decidir si hubo señal (no pueden introducir look-ahead).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

# Tipos de salida
EXIT_TP, EXIT_SL, EXIT_TIME = 0, 1, 2

# --------------------------------------------------------------------------- #
# Comisiones publicadas (fracción por lado). Fuente: binance.com/en/fee/trading,
# usuario regular (VIP 0), consultado 2026-10-04. Verificar antes de usar en serio.
# --------------------------------------------------------------------------- #
FEE_SCHEDULES: dict[str, dict[str, float]] = {
    "binance_spot": {"maker": 0.0010, "taker": 0.0010},
    "binance_spot_bnb": {"maker": 0.00075, "taker": 0.00075},   # pagando la comisión con BNB
}


class FeeModel(ABC):
    @abstractmethod
    def rate(self, order_type: str, notional: float | None = None) -> float:
        """Comisión (fracción del nocional) para 'maker' o 'taker'."""


@dataclass(frozen=True)
class ExchangeFeeModel(FeeModel):
    schedule: str = "binance_spot"

    def rate(self, order_type: str, notional: float | None = None) -> float:
        return FEE_SCHEDULES[self.schedule][order_type]


@dataclass(frozen=True)
class FlatFeeModel(FeeModel):
    """La misma comisión para maker y taker (modelo simple anterior)."""
    value: float

    def rate(self, order_type: str, notional: float | None = None) -> float:
        return self.value


class SpreadModel(ABC):
    @abstractmethod
    def half_spread(self, bar_idx: np.ndarray, ctx: "MarketContext") -> np.ndarray:
        """Medio spread relativo al precio medio al ejecutar en la vela bar_idx."""


@dataclass(frozen=True)
class FixedSpread(SpreadModel):
    full_spread: float   # spread completo (ask-bid)/mid

    def half_spread(self, bar_idx, ctx):
        return np.full(len(bar_idx), self.full_spread / 2.0)


class SlippageModel(ABC):
    @abstractmethod
    def slippage(self, bar_idx: np.ndarray, ctx: "MarketContext",
                 notional: float | None = None) -> np.ndarray:
        """Desplazamiento adverso adicional (fracción) al ejecutar en la vela bar_idx."""


@dataclass(frozen=True)
class FixedSlippage(SlippageModel):
    rate: float

    def slippage(self, bar_idx, ctx, notional=None):
        return np.full(len(bar_idx), self.rate)


@dataclass(frozen=True)
class VolatilitySlippage(SlippageModel):
    """
    slippage = base + k * (ATR(period)/Close) de la vela ANTERIOR a la ejecución
    (información disponible en el momento de ejecutar). Más volatilidad, más slippage.
    """
    base: float
    k: float
    period: int = 14
    # ATR/Close que se asume mientras el ATR no está definido (primeras `period`+1 velas de los
    # datos). Es una constante fija a propósito: usar la mediana de la muestra (como se hacía
    # antes, EXP-006) mira el futuro. 1 % es holgadamente conservador para BTC en 1h (mediana ~0,4 %).
    warmup_atr_pct: float = 0.01

    def slippage(self, bar_idx, ctx, notional=None):
        atr_pct = ctx.atr_pct_prev(self.period)
        v = atr_pct[np.clip(bar_idx, 0, len(atr_pct) - 1)]
        v = np.where(np.isfinite(v), v, self.warmup_atr_pct)
        return self.base + self.k * v


class MarketContext:
    """Datos de mercado que pueden necesitar los modelos de costos (calculado una vez)."""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self._atr: dict[int, np.ndarray] = {}

    def atr_pct_prev(self, period: int) -> np.ndarray:
        """ATR(period)/Close de la vela i-1, indexado por i (causal)."""
        if period not in self._atr:
            from .indicators import atr
            a = atr(self.df, period)["value"].to_numpy() / self.df["Close"].to_numpy()
            prev = np.full_like(a, np.nan)
            prev[1:] = a[:-1]
            self._atr[period] = prev
        return self._atr[period]


@dataclass(frozen=True)
class ExecutionCostModel:
    name: str
    fees: FeeModel
    spread: SpreadModel
    slippage: SlippageModel
    tp_order_type: str = "maker"        # "maker" (límite) o "taker" (mercado)
    position_size_usd: float | None = None   # reservado para modelos dependientes del tamaño
    is_estimate: bool = True

    def net_return(self, side: str, entry_price: np.ndarray, exit_price: np.ndarray,
                   exit_kind: np.ndarray, entry_idx: np.ndarray, exit_idx: np.ndarray,
                   ctx: MarketContext) -> np.ndarray:
        """
        Retorno neto de cada operación.
          LONG : compra a P_e = P(1+hs+sl) pagando f_e ; vende a P_x = X(1-hs-sl) pagando f_x
                 neto = P_x(1-f_x) / (P_e(1+f_e)) - 1
          SHORT: vende a P_e = P(1-hs-sl) cobrando menos f_e ; recompra a P_x = X(1+hs+sl) + f_x
                 neto = [P_e(1-f_e) - P_x(1+f_x)] / P_e
        Para la salida por TP con orden límite (maker) no hay spread ni slippage.
        """
        s = 1.0 if side == "LONG" else -1.0
        n = self.position_size_usd
        adv_e = self.spread.half_spread(entry_idx, ctx) + self.slippage.slippage(entry_idx, ctx, n)
        adv_x = self.spread.half_spread(exit_idx, ctx) + self.slippage.slippage(exit_idx, ctx, n)
        passive_tp = (exit_kind == EXIT_TP) & (self.tp_order_type == "maker")
        adv_x = np.where(passive_tp, 0.0, adv_x)
        f_e = self.fees.rate("taker", n)
        f_x = np.where(passive_tp, self.fees.rate("maker", n), self.fees.rate("taker", n))
        p_e = entry_price * (1.0 + s * adv_e)
        p_x = exit_price * (1.0 - s * adv_x)
        if side == "LONG":
            return p_x * (1.0 - f_x) / (p_e * (1.0 + f_e)) - 1.0
        return (p_e * (1.0 - f_e) - p_x * (1.0 + f_x)) / p_e

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "fees": repr(self.fees), "spread": repr(self.spread),
                "slippage": repr(self.slippage), "tp_order_type": self.tp_order_type,
                "is_estimate": self.is_estimate}


def build_cost_model(scenario: str, cfg) -> ExecutionCostModel:
    """
    Escenarios (spread y slippage son ESTIMACIONES para BTCUSDT spot y órdenes chicas):

      optimistic   comisión con BNB (0,075 %), spread 0,002 %, slippage 0,005 %
      typical      comisión estándar (0,10 %), spread 0,01 %,  slippage 0,02 %
      conservative comisión estándar (0,10 %), spread 0,05 %,
                   slippage 0,03 % + 0,05 × ATR(14)/Close (crece con la volatilidad)
      custom       el modelo anterior: COMMISSION_RATE / SPREAD_RATE / SLIPPAGE_RATE
                   de la configuración, todo como orden de mercado (taker)

    Los valores se pueden cambiar en COST_SCENARIO_PARAMS de la configuración.
    """
    p = dict(cfg.COST_SCENARIO_PARAMS.get(scenario, {}))
    if scenario == "custom":
        return ExecutionCostModel("custom", FlatFeeModel(cfg.COMMISSION_RATE),
                                  FixedSpread(cfg.SPREAD_RATE), FixedSlippage(cfg.SLIPPAGE_RATE),
                                  tp_order_type="taker", position_size_usd=cfg.POSITION_SIZE_USD)
    if not p:
        raise ValueError(f"Escenario de costos desconocido: {scenario}")
    if "slippage_vol_k" in p:
        slip: SlippageModel = VolatilitySlippage(p["slippage"], p["slippage_vol_k"],
                                                 int(p.get("slippage_vol_period", 14)))
    else:
        slip = FixedSlippage(p["slippage"])
    return ExecutionCostModel(scenario, ExchangeFeeModel(p["fee_schedule"]),
                              FixedSpread(p["spread"]), slip,
                              tp_order_type=cfg.TP_ORDER_TYPE,
                              position_size_usd=cfg.POSITION_SIZE_USD)
