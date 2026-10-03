"""
Actualización de datasets: descargar datos frescos de Yahoo Finance y
usarlos para (a) ver si cubren huecos que tiene un CSV viejo, y (b)
combinar ambos en un solo dataset con la mayor cobertura posible.

Pensado para usarse junto con `completeness.check_completeness`:

    1. Se detectan los timestamps faltantes del dataset viejo
       (`check_completeness(...).missing`).
    2. Se descarga un dataset fresco con `download_yfinance`.
    3. `check_recovered` dice cuáles de esos faltantes aparecen en el
       dataset nuevo (y cuáles siguen faltando incluso ahí).
    4. `merge_datasets` combina ambos en uno solo.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


def download_yfinance(asset: str, interval: str, period: str = "max") -> pd.DataFrame:
    """
    Descarga un dataset OHLCV de Yahoo Finance con el mismo formato que los
    CSV del proyecto: columna 'Date' (tz-aware UTC) + Open, High, Low,
    Close, Volume.

    Igual que en `data.YFinanceDataSource`: yfinance limita cuánta
    historia intradía entrega (p.ej. 1h ≈ últimos 730 días), así que
    `period="max"` en un intervalo intradía NO va a traer todo el
    histórico viejo, sólo lo máximo que Yahoo permite hoy. Por eso tiene
    sentido combinarlo con el CSV viejo en lugar de reemplazarlo.
    """
    import yfinance as yf  # import diferido: sólo se necesita si se llama a esta función

    raw = yf.download(asset, period=period, interval=interval,
                       auto_adjust=False, progress=False, threads=False,
                       multi_level_index=False)
    if raw is None or raw.empty:
        raise RuntimeError(f"Yahoo Finance no devolvió datos para {asset} {interval} (period={period}).")

    df = raw.reset_index()
    date_col = next(c for c in df.columns if c in ("Datetime", "Date"))
    df = df.rename(columns={date_col: "Date"})
    df["Date"] = pd.to_datetime(df["Date"], utc=True)

    cols = [c for c in ("Date", "Open", "High", "Low", "Close", "Volume") if c in df.columns]
    return df[cols].sort_values("Date").reset_index(drop=True)


@dataclass
class RecoveryReport:
    requested: pd.DatetimeIndex
    recovered: pd.DatetimeIndex
    still_missing: pd.DatetimeIndex

    def __str__(self) -> str:
        return (f"De {len(self.requested)} fechas faltantes, el dataset nuevo trae "
                f"{len(self.recovered)} y siguen faltando {len(self.still_missing)}.")


def check_recovered(missing: pd.DatetimeIndex, new_df: pd.DataFrame, date_col: str = "Date") -> RecoveryReport:
    """¿Cuáles de las fechas `missing` (típicamente `check_completeness(...).missing`
    de un CSV viejo) ya están presentes en `new_df`?"""
    missing = pd.DatetimeIndex(pd.to_datetime(missing, utc=True))
    new_dates = pd.DatetimeIndex(pd.to_datetime(new_df[date_col], utc=True)).unique()

    recovered = missing[missing.isin(new_dates)]
    still_missing = missing[~missing.isin(new_dates)]
    return RecoveryReport(requested=missing, recovered=recovered.sort_values(),
                           still_missing=still_missing.sort_values())


def merge_datasets(old_df: pd.DataFrame, new_df: pd.DataFrame, date_col: str = "Date",
                    prefer: str = "old") -> pd.DataFrame:
    """
    Combina dos datasets OHLCV para maximizar la cobertura temporal.

    prefer: qué dataset gana cuando una misma fecha está en los dos
    ("old" o "new"). Por defecto gana el viejo (ya revisado con
    `check_completeness`) y el nuevo sólo aporta las fechas que al viejo
    le faltaban.
    """
    if prefer not in ("old", "new"):
        raise ValueError('prefer debe ser "old" o "new".')
    first, second = (old_df, new_df) if prefer == "old" else (new_df, old_df)

    combined = pd.concat([first, second], ignore_index=True)
    combined[date_col] = pd.to_datetime(combined[date_col], utc=True)
    combined = combined.drop_duplicates(subset=date_col, keep="first")
    return combined.sort_values(date_col).reset_index(drop=True)
