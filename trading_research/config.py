"""
Configuración centralizada del proyecto.

TODOS los parámetros que afectan los resultados viven acá. Ningún otro módulo
define números "mágicos": los reciben a través de un objeto `ResearchConfig`.

La configuración completa se guarda junto con los resultados de cada corrida
(ver `search.save_results`), de modo que una búsqueda pueda reproducirse.
"""
from __future__ import annotations

import warnings

import dataclasses
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PositionSide(str, Enum):
    """Lado de la posición."""
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class ResearchConfig:
    # ------------------------------------------------------------------ #
    # Activo / temporalidad / fuente de datos
    # ------------------------------------------------------------------ #
    ASSET: str = "BTC"
    TIMEFRAME: str = "1h"
    # Si el CSV está en otra temporalidad (más fina) que TIMEFRAME, se agrega a TIMEFRAME con
    # `resample.aggregate_ohlc_strict` (EXP-011): p. ej. TIMEFRAME="4h", CSV_TIMEFRAME="1h".
    # Vacío = el CSV ya está en TIMEFRAME (comportamiento de siempre).
    CSV_TIMEFRAME: str = ""
    POSITION_TYPE: str = PositionSide.LONG.value
    DATA_SOURCE: str = "yfinance"          # "yfinance" | "csv"
    CSV_PATH: str | None = None            # usado si DATA_SOURCE == "csv"
    # yfinance sólo entrega ~730 días de velas de 1h. "max" se traduce al
    # máximo permitido por la temporalidad dentro de data.YFinanceDataSource.
    YF_PERIOD: str = "max"

    # ------------------------------------------------------------------ #
    # División cronológica TRAIN → VALIDATION → TEST
    # ------------------------------------------------------------------ #
    TRAIN_FRACTION: float = 0.30
    VALIDATION_FRACTION: float = 0.35
    TEST_FRACTION: float = 0.35
    # El TEST sólo se evalúa si se pide explícitamente (una sola vez, al final).
    RUN_TEST_EVALUATION: bool = False

    # ------------------------------------------------------------------ #
    # Walk-forward (alternativa a la división única TRAIN/VALIDATION/TEST)
    # ------------------------------------------------------------------ #
    # Se reserva el último WF_HOLDOUT_FRACTION como TEST final. El resto se
    # recorre en WF_N_FOLDS folds; en cada uno se hace la búsqueda completa en
    # su TRAIN y se evalúa en el período siguiente (su VALIDATION, fuera de
    # muestra). Cada VALIDATION mide WF_TRAIN_VAL_RATIO veces menos que su TRAIN.
    #   rolling (WF_ANCHORED=False): el TRAIN es una ventana de largo fijo que avanza
    #   anchored (WF_ANCHORED=True): el TRAIN empieza siempre al principio y crece
    # En modo walk-forward se ignoran TRAIN_FRACTION/VALIDATION_FRACTION/TEST_FRACTION.
    WALK_FORWARD: bool = False
    WF_N_FOLDS: int = 10
    WF_TRAIN_VAL_RATIO: float = 3.0
    WF_ANCHORED: bool = False
    WF_HOLDOUT_FRACTION: float = 0.15
    # Ventanas cortas (idea A): si se fijan ambos, se ignoran WF_N_FOLDS y
    # WF_TRAIN_VAL_RATIO. El TRAIN dura WF_TRAIN_BARS velas, la VALIDATION
    # (= "situación real", fuera de muestra) WF_VAL_BARS, y la ventana avanza de a
    # WF_VAL_BARS: las VALIDATION son contiguas y no se solapan.
    WF_TRAIN_BARS: int | None = None
    WF_VAL_BARS: int | None = None

    # ------------------------------------------------------------------ #
    # Indicadores: rangos de parámetros que el generador puede explorar
    # (límites inclusivos)
    # ------------------------------------------------------------------ #
    SMA_PERIOD_RANGE: tuple[int, int] = (5, 200)
    EMA_PERIOD_RANGE: tuple[int, int] = (5, 200)
    RSI_PERIOD_RANGE: tuple[int, int] = (5, 30)
    ATR_PERIOD_RANGE: tuple[int, int] = (5, 30)
    MACD_FAST_RANGE: tuple[int, int] = (5, 20)
    MACD_SLOW_RANGE: tuple[int, int] = (21, 50)
    MACD_SIGNAL_RANGE: tuple[int, int] = (5, 15)
    # Períodos n para R_n(t) = Close(t)/Close(t-n) - 1
    RETURN_PERIODS: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 50)

    # ------------------------------------------------------------------ #
    # Generación de condiciones
    # ------------------------------------------------------------------ #
    RANDOM_SEED: int = 42
    N_SIMPLE_CONDITIONS: int = 7500
    N_COMPLEX_CONDITIONS: int = 10000
    MAX_CONDITION_DEPTH: int = 1
    # Cuántas condiciones simples "informativas" de la etapa 1 se usan como
    # bloques para la etapa 2.
    # Con pools chicos las combinaciones de la etapa 2 se repiten mucho.
    STAGE2_POOL_SIZE: int = 5000
    # Una condición simple es "informativa" si supera el filtro de cantidad de
    # casos Y mejora la línea base (todas las velas como entrada) en al menos
    # alguna de estas diferencias absolutas:
    STAGE2_MIN_P_TP_LIFT: float = 0.0
    STAGE2_MIN_MEAN_RETURN_LIFT: float = 0.0
    # Los umbrales numéricos de las condiciones se sortean entre estos
    # cuantiles de la distribución del operando en TRAIN (nunca VALID/TEST).
    THRESHOLD_QUANTILE_RANGE: tuple[float, float] = (0.05, 0.95)

    # Features de régimen/contexto (EXP-008). Apagadas por defecto: con REGIME_FEATURES=False el
    # generador hace exactamente las mismas llamadas al azar que antes (misma semilla -> mismas
    # condiciones). Encendidas, se suman tres familias de operandos: tendencia 4h, tendencia diaria
    # y volatilidad relativa ATR(corto)/ATR(largo).
    REGIME_FEATURES: bool = False
    HTF_TREND_PERIOD_RANGE_4H: tuple[int, int] = (6, 60)     # n velas de 4h (1 a 10 días)
    HTF_TREND_PERIOD_RANGE_1D: tuple[int, int] = (5, 100)    # n velas diarias
    RELVOL_SHORT_RANGE: tuple[int, int] = (5, 30)
    RELVOL_LONG_RANGE: tuple[int, int] = (60, 300)
    # Búsqueda estructurada "contexto + disparador" (EXP-009). SEARCH_MODE="random" (por defecto) usa
    # el generador aleatorio de siempre; "structured" genera sólo ContextTrigger coherentes con la
    # dirección (POSITION_TYPE): LONG = contexto alcista + disparador "long"; SHORT = lo opuesto.
    SEARCH_MODE: str = "random"
    # Profundidad máxima del contexto y del disparador; además profundidad total <= MAX_CONDITION_DEPTH.
    STRUCT_CONTEXT_MAX_DEPTH: int = 2
    STRUCT_TRIGGER_MAX_DEPTH: int = 2
    # Cuantiles del operando de tendencia (TRAIN) entre los que se sortea el umbral del contexto:
    # LONG usa "tendencia > umbral" con q en la mitad alta; SHORT, "tendencia < umbral" con q en la baja.
    STRUCT_TREND_QUANTILE_RANGE_LONG: tuple[float, float] = (0.50, 0.95)
    STRUCT_TREND_QUANTILE_RANGE_SHORT: tuple[float, float] = (0.05, 0.50)
    # Familias de contexto (hojas) y sus pesos; el contexto tiene 1 o 2 hojas distintas unidas por AND.
    STRUCT_CONTEXT_WEIGHTS: dict[str, float] = field(default_factory=lambda: {
        "htf4": 1.0, "htf1d": 1.0, "relvol": 1.0})
    # Familias de disparador (eventos) y sus pesos. Todas se expresan con el árbol existente.
    #   rsi_cross      RSI(p) cruza X (LONG: por encima, SHORT: por debajo)
    #   macd_cross     línea MACD cruza su señal
    #   ret_cross      return(N) cruza X
    #   rsi_recovery   RSI estuvo en la zona extrema (< X_bajo, LONG) en las N velas previas Y cruza X_alto
    STRUCT_TRIGGER_WEIGHTS: dict[str, float] = field(default_factory=lambda: {
        "rsi_cross": 1.0, "macd_cross": 1.0, "ret_cross": 1.0, "rsi_recovery": 1.0})
    # Cifras significativas al redondear umbrales (legibilidad).
    THRESHOLD_SIGNIFICANT_DIGITS: int = 3
    # Probabilidades relativas de cada tipo de condición simple.
    SIMPLE_KIND_WEIGHTS: dict[str, float] = field(default_factory=lambda: {
        "compare_const": 0.15,
        "compare_operand": 0.15,
        "cross_const": 0.40,
        "cross_operand": 0.30,
    })
    # Probabilidades relativas de cada operador en la etapa 2.
    COMPLEX_OPERATOR_WEIGHTS: dict[str, float] = field(default_factory=lambda: {
        "AND": 0.15,
        "OR": 0.15,
        "NOT": 0.10,
        "THEN": 0.20,
        "WITHIN_AND": 0.40,
    })
    # Ventana N (velas) para "A THEN B within N" y "A occurred within N".
    TEMPORAL_WINDOW_RANGE: tuple[int, int] = (2, 25)

    # ------------------------------------------------------------------ #
    # Entradas
    # ------------------------------------------------------------------ #
    # Cooldown entre entradas de la MISMA condición (en velas). Una señal en t
    # se acepta sólo si la última entrada aceptada de esa condición fue en una
    # vela <= t - MIN_BARS_BETWEEN_SAME_CONDITION_ENTRIES.
    MIN_BARS_BETWEEN_SAME_CONDITION_ENTRIES: int = 15
    # Regla de re-entrada para la MISMA condición:
    #   "fixed"      -> cooldown fijo de MIN_BARS_BETWEEN_SAME_CONDITION_ENTRIES
    #                   velas (las operaciones pueden superponerse si el
    #                   cooldown es menor que el horizonte).
    #   "until_exit" -> no se vuelve a entrar mientras la operación anterior de
    #                   esa condición siga abierta (hasta que toque TP, SL o se
    #                   agote el horizonte). Operaciones nunca superpuestas.
    #                   En este modo el cooldown fijo se ignora.
    COOLDOWN_MODE: str = "until_exit" #"fixed"

    # ------------------------------------------------------------------ #
    # Evaluación posterior a la entrada
    # ------------------------------------------------------------------ #
    MAX_HOLDING_BARS: int = 30
    # Geometría de la salida (EXP-010). "fixed" (por defecto, el comportamiento de siempre): TP_PERCENT y
    # SL_PERCENT como fracción del precio de entrada. "atr": TP = entrada ± TP_ATR_MULT * ATR[t] y
    # SL = entrada ∓ SL_ATR_MULT * ATR[t], con el ATR (Wilder, EXIT_ATR_PERIOD) medido al cierre de la
    # vela de confirmación t y fijado para toda la operación (entrada = Open[t+1]).
    EXIT_MODE: str = "fixed"
    TP_ATR_MULT: float = 2.0
    SL_ATR_MULT: float = 1.0
    EXIT_ATR_PERIOD: int = 14
    TP_PERCENT: float = 0.05
    SL_PERCENT: float = 0.02
    # Qué retorno asignar a un caso AMBIGUOUS (TP y SL en la misma vela):
    #   "worst"   -> se asume SL (conservador)
    #   "best"    -> se asume TP (optimista, sólo para análisis de sensibilidad)
    #   "midpoint"-> promedio de ambos
    # La CLASIFICACIÓN siempre queda como AMBIGUOUS; esto sólo afecta el retorno.
    AMBIGUOUS_RETURN_POLICY: str = "worst"

    # Umbrales para P(MFE >= x) y P(MAE <= -x)
    MFE_THRESHOLDS: tuple[float, ...] = (0.01, 0.02, 0.05, 0.10)
    MAE_THRESHOLDS: tuple[float, ...] = (0.01, 0.02, 0.05)
    QUANTILES: tuple[float, ...] = (0.10, 0.25, 0.50, 0.75, 0.90)

    # Condiciones favorables generales (sección 20). Cada dict:
    #   {"type": "reach",      "p": 0.03, "bars": 10}
    #   {"type": "at_horizon", "p": 0.02, "bars": 10}
    #   {"type": "down_then_up", "p1": 0.01, "p2": 0.03}
    #   {"type": "up_then_down", "p1": 0.02, "p2": 0.02}
    # "bars" debe ser <= MAX_HOLDING_BARS; las secuencias usan todo el horizonte.
    FAVORABLE_OUTCOMES: tuple[dict[str, Any], ...] = (
        {"type": "reach", "p": 0.02, "bars": 10},
        {"type": "reach", "p": 0.05, "bars": 30},
        {"type": "at_horizon", "p": 0.0, "bars": 10},
        {"type": "at_horizon", "p": 0.02, "bars": 30},
        # Las que tengan "bars" > MAX_HOLDING_BARS se omiten (con aviso).
        {"type": "down_then_up", "p1": 0.01, "p2": 0.03},
        {"type": "up_then_down", "p1": 0.02, "p2": 0.02},
    )

    # ------------------------------------------------------------------ #
    # Costos de ejecución (ver trading_research/costs.py)
    # ------------------------------------------------------------------ #
    # COST_SCENARIO: escenario que se usa para los filtros y el retorno neto
    #   principal ("net_return", "mean_net_return").
    # COST_SCENARIOS_REPORT: escenarios que se calculan además, como
    #   mean_net_return_<escenario>, para ver si un resultado depende de
    #   suponer costos optimistas.
    # Spread y slippage son ESTIMACIONES (con OHLC no se pueden observar).
    COST_SCENARIO: str = "typical"
    COST_SCENARIOS_REPORT: tuple[str, ...] = ("optimistic", "typical", "conservative")
    COST_SCENARIO_PARAMS: dict[str, dict[str, Any]] = field(default_factory=lambda: {
        "optimistic": {"fee_schedule": "binance_spot_bnb", "spread": 0.00002, "slippage": 0.00005},
        "typical": {"fee_schedule": "binance_spot", "spread": 0.0001, "slippage": 0.0002},
        "conservative": {"fee_schedule": "binance_spot", "spread": 0.0005, "slippage": 0.0003,
                         "slippage_vol_k": 0.05, "slippage_vol_period": 14},
    })
    # Salida por TP con orden límite ya colocada ("maker") o de mercado ("taker").
    TP_ORDER_TYPE: str = "maker"
    # Tamaño de cada operación en USD. Los modelos actuales no dependen de él;
    # queda en la interfaz para modelos de slippage por profundidad del libro.
    POSITION_SIZE_USD: float = 1000.0

    # Escenario "custom" (el modelo simple anterior, todo como orden de mercado):
    # COMMISSION_RATE: comisión por lado. SLIPPAGE_RATE: slippage por lado.
    # SPREAD_RATE: spread completo (se paga la mitad al entrar y la mitad al salir).
    COMMISSION_RATE: float = 0.001
    SLIPPAGE_RATE: float = 0.0005
    SPREAD_RATE: float = 0.0002

    # ------------------------------------------------------------------ #
    # Filtros
    # ------------------------------------------------------------------ #
    MIN_CASES_FRACTION: float = 0.01   # filtro de frecuencia, NO de significancia
    MIN_CASES_ABSOLUTE: int = 30
    # Referencia: con TP=5 %, SL=2 % y 30 velas, la línea base de BTC 1h
    # (todas las velas como entrada, 2024-2025) dio P(TP_FIRST) ≈ 0.10 en TRAIN.
    # Comparar siempre contra la línea base que imprime cada corrida.
    MIN_P_TP_FIRST: float = 0.15
    # "net" o "gross": qué retorno medio debe ser > MIN_EXPECTED_RETURN
    EXPECTED_RETURN_BASIS: str = "net"
    MIN_EXPECTED_RETURN: float = 0.0

    # Qué criterio usar (además del mínimo de casos, que siempre se exige):
    #   "absolute" -> P(TP_FIRST) >= MIN_P_TP_FIRST y retorno medio > MIN_EXPECTED_RETURN
    #   "lift"     -> mejora respecto de la línea base DEL MISMO SEGMENTO
    #                 (entrar en todas las velas):
    #                   P(TP_FIRST) - P_base  >= MIN_LIFT_P_TP_FIRST
    #                   retorno     - ret_base > MIN_LIFT_EXPECTED_RETURN
    #                 Responde "¿la condición agrega información?", no
    #                 "¿gana plata?": en un período bajista puede pasar con
    #                 retorno absoluto negativo.
    #   "both"     -> exige los dos criterios (información Y rentabilidad).
    FILTER_MODE: str = "absolute"
    MIN_LIFT_P_TP_FIRST: float = 0.03
    MIN_LIFT_EXPECTED_RETURN: float = 0.0

    # ------------------------------------------------------------------ #
    # Salida
    # ------------------------------------------------------------------ #
    OUTPUT_DIR: str = "results"
    SAVE_EVENTS: bool = True

    # ------------------------------------------------------------------ #
    @property
    def bar_hours(self) -> float:
        """Duración en horas de una barra de TIMEFRAME."""
        import pandas as pd
        return pd.Timedelta(self.TIMEFRAME).total_seconds() / 3600.0

    @property
    def horizon_hours(self) -> float:
        """Duración máxima de una operación en horas (MAX_HOLDING_BARS barras de TIMEFRAME)."""
        return self.MAX_HOLDING_BARS * self.bar_hours

    def validate(self) -> None:
        if self.EXIT_MODE not in ("fixed", "atr"):
            raise ValueError("EXIT_MODE debe ser 'fixed' o 'atr'.")
        if self.EXIT_MODE == "atr" and (self.TP_ATR_MULT <= 0 or self.SL_ATR_MULT <= 0
                                        or self.EXIT_ATR_PERIOD < 2):
            raise ValueError("TP_ATR_MULT, SL_ATR_MULT > 0 y EXIT_ATR_PERIOD >= 2.")
        if self.SEARCH_MODE not in ("random", "structured"):
            raise ValueError("SEARCH_MODE debe ser 'random' o 'structured'.")
        if (self.COOLDOWN_MODE == "fixed"
                and self.MIN_BARS_BETWEEN_SAME_CONDITION_ENTRIES < self.MAX_HOLDING_BARS):
            warnings.warn(
                "COOLDOWN_MODE='fixed' con cooldown < horizonte: las operaciones de una condición se "
                "solapan y el t entre entradas queda inflado (EXP-007). Preferir 'until_exit'.",
                stacklevel=2)
        total = self.TRAIN_FRACTION + self.VALIDATION_FRACTION + self.TEST_FRACTION
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"TRAIN+VALIDATION+TEST debe sumar 1 (suma {total}).")
        if self.POSITION_TYPE not in (PositionSide.LONG.value, PositionSide.SHORT.value):
            raise ValueError("POSITION_TYPE debe ser 'LONG' o 'SHORT'.")
        if self.MAX_CONDITION_DEPTH < 1:
            raise ValueError("MAX_CONDITION_DEPTH debe ser >= 1.")
        if self.AMBIGUOUS_RETURN_POLICY not in ("worst", "best", "midpoint"):
            raise ValueError("AMBIGUOUS_RETURN_POLICY inválida.")
        if self.EXPECTED_RETURN_BASIS not in ("net", "gross"):
            raise ValueError("EXPECTED_RETURN_BASIS debe ser 'net' o 'gross'.")
        if self.FILTER_MODE not in ("absolute", "lift", "both"):
            raise ValueError("FILTER_MODE debe ser 'absolute', 'lift' o 'both'.")
        if self.COOLDOWN_MODE not in ("fixed", "until_exit"):
            raise ValueError("COOLDOWN_MODE debe ser 'fixed' o 'until_exit'.")
        if self.WF_N_FOLDS < 1 or self.WF_TRAIN_VAL_RATIO <= 0:
            raise ValueError("WF_N_FOLDS >= 1 y WF_TRAIN_VAL_RATIO > 0.")
        if (self.WF_TRAIN_BARS is None) != (self.WF_VAL_BARS is None):
            raise ValueError("WF_TRAIN_BARS y WF_VAL_BARS se fijan juntos.")
        if not 0 <= self.WF_HOLDOUT_FRACTION < 1:
            raise ValueError("WF_HOLDOUT_FRACTION debe estar en [0, 1).")
        known = set(self.COST_SCENARIO_PARAMS) | {"custom"}
        for sc in (self.COST_SCENARIO, *self.COST_SCENARIOS_REPORT):
            if sc not in known:
                raise ValueError(f"Escenario de costos desconocido: {sc} (opciones: {sorted(known)}).")
        if self.TP_ORDER_TYPE not in ("maker", "taker"):
            raise ValueError("TP_ORDER_TYPE debe ser 'maker' o 'taker'.")
        if self.MAX_HOLDING_BARS < 1:
            raise ValueError("MAX_HOLDING_BARS debe ser >= 1.")
        if not (self.TP_PERCENT > 0 and 0 < self.SL_PERCENT < 1):
            raise ValueError("TP_PERCENT debe ser > 0 y SL_PERCENT entre 0 y 1.")
        if self.MIN_BARS_BETWEEN_SAME_CONDITION_ENTRIES < 0:
            raise ValueError("El cooldown no puede ser negativo.")

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(dataclasses.asdict(self), default=list))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ResearchConfig":
        names = {f.name: f for f in dataclasses.fields(cls)}
        kwargs = {}
        for k, v in d.items():
            if k not in names:
                continue
            if isinstance(v, list) and k != "FAVORABLE_OUTCOMES":
                v = tuple(v)
            elif k == "FAVORABLE_OUTCOMES":
                v = tuple(v)
            kwargs[k] = v
        return cls(**kwargs)
