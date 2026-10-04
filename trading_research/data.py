"""
Capa de adquisición de datos.

Contrato con el resto del sistema: toda fuente devuelve un DataFrame con
  - índice DatetimeIndex en UTC, estrictamente creciente y sin duplicados;
  - columnas exactamente ["Open", "High", "Low", "Close"] (float64).

Nada fuera de este módulo sabe de dónde vienen los datos. Para agregar otra
fuente (un exchange, una base de datos, otro proveedor) basta con implementar
`DataSource.fetch` y registrarla en `make_data_source`.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd

from .config import ResearchConfig

log = logging.getLogger(__name__)

OHLC_COLUMNS = ["Open", "High", "Low", "Close"]

# Duración de cada temporalidad (para detectar huecos en los datos).
TIMEFRAME_TO_TIMEDELTA = {
    "1m": pd.Timedelta(minutes=1),
    "2m": pd.Timedelta(minutes=2),
    "5m": pd.Timedelta(minutes=5),
    "15m": pd.Timedelta(minutes=15),
    "30m": pd.Timedelta(minutes=30),
    "1h": pd.Timedelta(hours=1),
    "4h": pd.Timedelta(hours=4),
    "1d": pd.Timedelta(days=1),
}


class DataSource(ABC):
    """Interfaz común de todas las fuentes de datos."""

    @abstractmethod
    def fetch(self, asset: str, timeframe: str) -> pd.DataFrame:
        """Devuelve el OHLC normalizado (ver contrato del módulo)."""


def normalize_ohlc(raw: pd.DataFrame) -> pd.DataFrame:
    """Lleva cualquier tabla OHLC al contrato del sistema. Descarta Volume."""
    df = raw.copy()
    if isinstance(df.columns, pd.MultiIndex):  # yfinance >= 0.2 a veces devuelve MultiIndex
        df.columns = df.columns.get_level_values(0)
    rename = {c: c.capitalize() for c in df.columns if c.lower() in ("open", "high", "low", "close")}
    df = df.rename(columns=rename)
    missing = [c for c in OHLC_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas OHLC: {missing}")
    df = df[OHLC_COLUMNS].astype("float64")

    idx = df.index if isinstance(df.index, pd.DatetimeIndex) else \
        pd.to_datetime(df.index.astype(str), utc=True, format="ISO8601")
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    df.index = idx
    df.index.name = "timestamp"
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.dropna(how="any")

    # Coherencia mínima de cada vela
    bad = (df["High"] < df[["Open", "Close"]].max(axis=1)) | (df["Low"] > df[["Open", "Close"]].min(axis=1))
    if bad.any():
        log.warning("Se descartan %d velas con High/Low incoherentes.", int(bad.sum()))
        df = df[~bad]
    return df


@dataclass
class DataQualityReport:
    n_bars: int
    start: pd.Timestamp
    end: pd.Timestamp
    n_gaps: int
    max_gap: pd.Timedelta | None

    def __str__(self) -> str:
        return (f"{self.n_bars} velas, {self.start} → {self.end}; "
                f"huecos: {self.n_gaps} (máx {self.max_gap})")


def quality_report(df: pd.DataFrame, timeframe: str) -> DataQualityReport:
    """
    Detecta huecos (velas faltantes). Importante: el sistema mide horizontes y
    ventanas en CANTIDAD DE VELAS, no en tiempo de reloj; un hueco hace que
    "30 velas" abarquen más de 30 horas.
    """
    step = TIMEFRAME_TO_TIMEDELTA.get(timeframe)
    n_gaps, max_gap = 0, None
    if step is not None and len(df) > 1:
        d = df.index.to_series().diff().dropna()
        gaps = d[d > step]
        n_gaps = int(len(gaps))
        max_gap = gaps.max() if n_gaps else None
    return DataQualityReport(len(df), df.index[0], df.index[-1], n_gaps, max_gap)


class YFinanceDataSource(DataSource):
    """Yahoo Finance vía `yfinance` (gratuito). Limitación: 1h ≈ últimos 730 días."""

    ASSET_TO_TICKER = {"BTC": "BTC-USD", "ETH": "ETH-USD"}
    # Período máximo que Yahoo permite para cada intervalo intradiario.
    MAX_PERIOD = {"1m": "7d", "2m": "60d", "5m": "60d", "15m": "60d", "30m": "60d",
                  "1h": "730d", "1d": "max"}

    def __init__(self, period: str = "max"):
        self.period = period

    def fetch(self, asset: str, timeframe: str) -> pd.DataFrame:
        import yfinance as yf  # import diferido: sólo si se usa esta fuente

        if timeframe == "4h":
            raise ValueError("Yahoo no ofrece 4h; usar 1h y re-muestrear (resample_ohlc).")
        ticker = self.ASSET_TO_TICKER.get(asset, asset)
        period = self.MAX_PERIOD.get(timeframe, "max") if self.period == "max" else self.period
        log.info("Descargando %s %s (period=%s) de Yahoo Finance…", ticker, timeframe, period)
        raw = yf.download(ticker, period=period, interval=timeframe,
                          auto_adjust=False, progress=False, threads=False)
        if raw is None or raw.empty:
            raise RuntimeError(f"Yahoo no devolvió datos para {ticker} {timeframe}.")
        return normalize_ohlc(raw)


class CSVDataSource(DataSource):
    """CSV con una columna de fecha (primera columna o 'Date'/'Datetime') y OHLC."""

    def __init__(self, path: str):
        self.path = path

    def fetch(self, asset: str, timeframe: str) -> pd.DataFrame:
        raw = pd.read_csv(self.path)
        date_col = next((c for c in raw.columns if c.lower() in ("date", "datetime", "timestamp")),
                        raw.columns[0])
        raw = raw.set_index(date_col)
        return normalize_ohlc(raw)


def resample_ohlc(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Re-muestrea a una temporalidad mayor (p. ej. '4h'). Sin look-ahead: agrupa velas pasadas."""
    out = df.resample(rule, label="left", closed="left").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last"})
    return out.dropna()


def make_data_source(cfg: ResearchConfig) -> DataSource:
    if cfg.DATA_SOURCE == "yfinance":
        return YFinanceDataSource(cfg.YF_PERIOD)
    if cfg.DATA_SOURCE == "csv":
        if not cfg.CSV_PATH:
            raise ValueError("DATA_SOURCE='csv' requiere CSV_PATH.")
        return CSVDataSource(cfg.CSV_PATH)
    raise ValueError(f"Fuente de datos desconocida: {cfg.DATA_SOURCE}")


def load_data(cfg: ResearchConfig) -> pd.DataFrame:
    df = make_data_source(cfg).fetch(cfg.ASSET, cfg.TIMEFRAME)
    log.info("Datos: %s", quality_report(df, cfg.TIMEFRAME))
    return df
