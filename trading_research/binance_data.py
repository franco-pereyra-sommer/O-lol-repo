"""
Descarga de historia larga desde los archivos públicos de Binance
(https://data.binance.vision), sin API key ni cuenta.

Binance publica las velas de cada par en un .zip por MES (meses cerrados) y
un .zip por DÍA (días cerrados del mes en curso). Este módulo baja ambos,
los guarda en una carpeta caché (para no volver a bajarlos) y arma un CSV con
el mismo formato que usa el resto del proyecto:

    Date,Open,High,Low,Close,Volume        (Date en UTC, apertura de la vela)

Detalles del formato de Binance que se manejan acá:
  - Los CSV no traen encabezado (algunos más nuevos sí): se detecta.
  - Desde 2025-01-01 los timestamps de SPOT vienen en MICROsegundos; antes
    en milisegundos. Se detecta por magnitud.
  - BTCUSDT spot empieza el 2017-08-17.

Uso (en tu máquina, dentro del entorno de Pixi):
    python -m trading_research.binance_data --symbol BTCUSDT --interval 1h \
        --out "C:\\O lol\\Guardado de datos\\BTCUSDT_binance_1h.csv"
"""
from __future__ import annotations

import argparse
import io
import logging
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

BASE_URL = "https://data.binance.vision/data/spot"
KLINE_COLUMNS = ["open_time", "Open", "High", "Low", "Close", "Volume", "close_time",
                 "quote_volume", "n_trades", "taker_buy_base", "taker_buy_quote", "ignore"]
FIRST_MONTH = {"BTCUSDT": "2017-08", "ETHUSDT": "2017-08"}


def monthly_url(symbol: str, interval: str, month: str) -> str:
    return f"{BASE_URL}/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{month}.zip"


def daily_url(symbol: str, interval: str, day: str) -> str:
    return f"{BASE_URL}/daily/klines/{symbol}/{interval}/{symbol}-{interval}-{day}.zip"


def _download(url: str, dest: Path, retries: int = 3) -> bool:
    """Baja `url` a `dest`. Devuelve False si el archivo no existe (404)."""
    if dest.exists() and dest.stat().st_size > 0:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                data = r.read()
            tmp = dest.with_suffix(".part")
            tmp.write_bytes(data)
            tmp.replace(dest)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False
            log.warning("HTTP %s en %s (intento %d/%d)", e.code, url, attempt, retries)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            log.warning("Error de red en %s: %s (intento %d/%d)", url, e, attempt, retries)
        time.sleep(2 * attempt)
    raise RuntimeError(f"No se pudo descargar {url}")


def parse_kline_zip(data: bytes) -> pd.DataFrame:
    """Convierte un .zip de klines de Binance en un DataFrame OHLCV indexado en UTC."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv"))
        raw = z.read(name)
    first = raw.split(b"\n", 1)[0]
    has_header = not first[:1].isdigit()
    df = pd.read_csv(io.BytesIO(raw), header=0 if has_header else None)
    df = df.iloc[:, :len(KLINE_COLUMNS)]
    df.columns = KLINE_COLUMNS[:df.shape[1]]
    t = pd.to_numeric(df["open_time"])
    # ms ~ 1.5e12 ; µs ~ 1.5e15
    unit = "us" if t.max() > 1e14 else "ms"
    idx = pd.to_datetime(t, unit=unit, utc=True)
    out = df[["Open", "High", "Low", "Close", "Volume"]].astype("float64")
    out.index = idx
    out.index.name = "Date"
    return out


def _months(start: str, end: pd.Timestamp) -> list[str]:
    """Meses cerrados desde `start` (YYYY-MM) hasta el mes anterior a `end`."""
    first = pd.Period(start, freq="M")
    last = pd.Period(end, freq="M") - 1
    return [str(p) for p in pd.period_range(first, last, freq="M")] if last >= first else []


def download_history(symbol: str = "BTCUSDT", interval: str = "1h",
                     start_month: str | None = None, cache_dir: str | Path = "binance_cache",
                     include_current_month: bool = True) -> pd.DataFrame:
    now = pd.Timestamp.now(tz="UTC")
    start_month = start_month or FIRST_MONTH.get(symbol, "2017-08")
    cache = Path(cache_dir) / symbol / interval
    frames: list[pd.DataFrame] = []

    months = _months(start_month, now)
    log.info("Bajando %d meses de %s %s (caché: %s)…", len(months), symbol, interval, cache)
    for i, m in enumerate(months, 1):
        dest = cache / f"{symbol}-{interval}-{m}.zip"
        if _download(monthly_url(symbol, interval, m), dest):
            frames.append(parse_kline_zip(dest.read_bytes()))
        else:
            log.info("  %s: no existe (antes del inicio del par o aún no publicado)", m)
        if i % 12 == 0:
            log.info("  %d/%d meses", i, len(months))

    if include_current_month:
        # El mensual del mes anterior puede no estar publicado los primeros días:
        # se completa con diarios desde el último dato obtenido.
        last = max((f.index.max() for f in frames), default=pd.Timestamp(start_month + "-01", tz="UTC"))
        day = (last + pd.Timedelta(days=1)).normalize() if frames else last.normalize()
        while day < now.normalize():
            d = day.strftime("%Y-%m-%d")
            dest = cache / "daily" / f"{symbol}-{interval}-{d}.zip"
            if _download(daily_url(symbol, interval, d), dest):
                frames.append(parse_kline_zip(dest.read_bytes()))
            day += pd.Timedelta(days=1)

    if not frames:
        raise RuntimeError("No se descargó ningún dato.")
    df = pd.concat(frames).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    log.info("Total: %d velas, %s → %s", len(df), df.index[0], df.index[-1])
    return df


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Descarga velas históricas de Binance (data.binance.vision).")
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--interval", default="1h", help="1m, 5m, 15m, 1h, 4h, 1d, …")
    p.add_argument("--start", default=None, help="Primer mes YYYY-MM (por defecto, el inicio del par).")
    p.add_argument("--out", required=True, help="CSV de salida.")
    p.add_argument("--cache", default="binance_cache", help="Carpeta donde guardar los .zip.")
    a = p.parse_args()

    df = download_history(a.symbol, a.interval, a.start, a.cache)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index_label="Date")
    print(f"Guardado: {out}  ({len(df)} velas, {df.index[0]} → {df.index[-1]})")


if __name__ == "__main__":
    main()
