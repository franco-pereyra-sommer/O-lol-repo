"""
Verificación de completitud temporal de series OHLCV.

Dos tipos de mercado:

  - "continuous": el activo cotiza sin interrupción (cripto, forex). Se
    espera exactamente una vela en cada paso de `freq`, desde el primer
    hasta el último timestamp del dataset, sin importar el día de la
    semana.

  - "session": el activo sólo cotiza dentro de una sesión diaria con hora
    de apertura y cierre (acciones), en días hábiles (se excluyen fines
    de semana y, opcionalmente, feriados). `session_start`/`session_end`
    se dan en la hora LOCAL del mercado (`market_tz`), no en la zona
    horaria del dataset: así el horario esperado se corre automáticamente
    con el cambio de horario de verano (DST), igual que hace el mercado
    real. Por ejemplo NYSE abre 9:30 y cierra 16:00 hora de Nueva York
    todo el año, aunque eso sea 14:30-21:00 UTC en invierno y 13:30-20:00
    UTC en verano.

El feriado (`holidays`) es opcional: sin lista de feriados sólo se exigen
días hábiles (lunes a viernes por defecto vía `weekmask`), y los feriados
van a aparecer como "faltantes" (lo cual es razonable si no se los puede
distinguir de un hueco real). Para feriados bursátiles exactos de EE.UU.
se puede instalar `pandas_market_calendars` y pasar su calendario:

    import pandas_market_calendars as mcal
    nyse = mcal.get_calendar("NYSE")
    sched = nyse.schedule(start_date="2024-01-01", end_date="2024-12-31")
    holidays = nyse.holidays().holidays  # lista de fechas feriado

Uso típico:
    from trading_research.completeness import check_completeness

    df = pd.read_csv("BTC-USD_int1h.csv")
    rep = check_completeness(df, date_col="Date", freq="1h", market="continuous")
    print(rep)
    print(rep.missing)  # DatetimeIndex con los timestamps faltantes

    rep = check_completeness(
        df, date_col="Date", freq="1h", market="session",
        session_start="09:30", session_end="16:00", market_tz="America/New_York",
    )
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

import pandas as pd


@dataclass
class CompletenessReport:
    freq: str
    market: str
    start: pd.Timestamp
    end: pd.Timestamp
    expected_count: int
    actual_count: int
    missing: pd.DatetimeIndex
    duplicated: pd.DatetimeIndex
    unexpected: pd.DatetimeIndex
    nat_rows: int = 0

    @property
    def is_complete(self) -> bool:
        return (len(self.missing) == 0 and len(self.duplicated) == 0
                and len(self.unexpected) == 0 and self.nat_rows == 0)

    def __str__(self) -> str:
        return (
            f"[{self.market}, freq={self.freq}] {self.start} → {self.end}\n"
            f"  esperadas: {self.expected_count}  |  presentes: {self.actual_count}\n"
            f"  faltantes: {len(self.missing)}  |  duplicadas: {len(self.duplicated)}  |  "
            f"fuera de grilla: {len(self.unexpected)}  |  filas con fecha inválida: {self.nat_rows}\n"
            f"  completo: {self.is_complete}"
        )


def _extract_index(df: pd.DataFrame, date_col: str | None, tz: str | None) -> tuple[pd.DatetimeIndex, int]:
    """Devuelve el DatetimeIndex (ordenado, con duplicados conservados para
    poder reportarlos) y la cantidad de fechas que no se pudieron parsear."""
    raw = df[date_col] if date_col is not None else df.index.to_series(index=range(len(df)))
    parsed = pd.to_datetime(raw, utc=False, errors="coerce")
    nat_rows = int(parsed.isna().sum())
    parsed = parsed.dropna()

    idx = pd.DatetimeIndex(parsed)
    if idx.tz is None:
        idx = idx.tz_localize(tz) if tz else idx.tz_localize("UTC")
    elif tz:
        idx = idx.tz_convert(tz)
    return idx.sort_values(), nat_rows


def _expected_continuous(idx: pd.DatetimeIndex, freq: str) -> pd.DatetimeIndex:
    return pd.date_range(start=idx.min(), end=idx.max(), freq=freq)


def _expected_session(
    idx: pd.DatetimeIndex,
    freq: str,
    session_start: str,
    session_end: str,
    market_tz: str,
    weekmask: str,
    holidays,
    bar_label: str,
) -> pd.DatetimeIndex:
    bday = pd.tseries.offsets.CustomBusinessDay(
        weekmask=weekmask, holidays=holidays if holidays is not None else [])
    trading_days = pd.date_range(idx.min().normalize(), idx.max().normalize(), freq=bday)

    data_tz = idx.tz
    pieces = []
    for day in trading_days:
        day_start = pd.Timestamp(f"{day.date()} {session_start}", tz=market_tz)
        day_end = pd.Timestamp(f"{day.date()} {session_end}", tz=market_tz)
        inclusive = "left" if bar_label == "start" else "right"
        day_range = pd.date_range(day_start, day_end, freq=freq, inclusive=inclusive)
        pieces.append(day_range.tz_convert(data_tz))

    if not pieces:
        return pd.DatetimeIndex([], tz=data_tz)
    expected = pieces[0]
    for p in pieces[1:]:
        expected = expected.union(p)
    # Recortar al rango real de datos (la última/primera sesión puede estar
    # incompleta en el propio dataset, eso ya lo refleja "missing").
    return expected[(expected >= idx.min()) & (expected <= idx.max())]


def check_completeness(
    df: pd.DataFrame,
    date_col: str | None = None,
    freq: str = "1h",
    market: str = "continuous",
    session_start: str | None = None,
    session_end: str | None = None,
    market_tz: str = "America/New_York",
    weekmask: str = "Mon Tue Wed Thu Fri",
    holidays=None,
    bar_label: str = "start",
    tz: str | None = None,
) -> CompletenessReport:
    """
    Verifica si `df` tiene una vela en cada timestamp esperado según `freq`
    y el tipo de mercado.

    df: DataFrame con una columna de fecha (`date_col`) o un índice de fecha.
    date_col: nombre de la columna de fecha/hora. None => usar el índice.
    freq: cualquier alias de frecuencia de pandas ("1h", "5min", "1D", "1W",
        "1ME" para fin de mes, etc.).
    market: "continuous" (cripto, forex, 24/7) o "session" (acciones, con
        horario de apertura/cierre).
    session_start/session_end: sólo para market="session". Hora LOCAL del
        mercado, ej. "09:30"/"16:00". Se combinan con `market_tz` para
        ajustar automáticamente por horario de verano.
    market_tz: zona horaria del mercado (ej. "America/New_York" para NYSE/
        NASDAQ, "America/Buenos_Aires" para BYMA). No es la zona horaria del
        dataset, sino la de la bolsa.
    weekmask: días hábiles, formato de `numpy.busdaycalendar` (por defecto
        lunes a viernes).
    holidays: lista opcional de fechas feriado (se excluyen de la sesión).
        Sin esta lista, un feriado real va a listarse como "missing".
    bar_label: "start" si el timestamp de la vela es el inicio del intervalo
        (vela de 14:30 cubre 14:30-15:30; no se espera una vela en
        session_end) o "end" si es el cierre (no se espera una vela en
        session_start).
    tz: forzar esta zona horaria para interpretar/convertir las fechas del
        dataset. None => se detecta de los datos (o se asume UTC si vienen
        sin zona horaria).

    Devuelve un CompletenessReport con los timestamps faltantes
    (`.missing`), duplicados (`.duplicated`) y los que están fuera de la
    grilla esperada (`.unexpected`, p.ej. velas fuera de horario de sesión).
    """
    idx, nat_rows = _extract_index(df, date_col, tz)
    if len(idx) == 0:
        raise ValueError("No hay fechas válidas para analizar.")

    if market == "continuous":
        expected = _expected_continuous(idx, freq)
    elif market == "session":
        if not session_start or not session_end:
            raise ValueError('market="session" requiere session_start y session_end (ej. "09:30", "16:00").')
        expected = _expected_session(idx, freq, session_start, session_end, market_tz,
                                      weekmask, holidays, bar_label)
    else:
        raise ValueError('market debe ser "continuous" o "session".')

    actual_unique = idx.unique()
    missing = expected.difference(actual_unique)
    unexpected = actual_unique.difference(expected)
    duplicated = idx[idx.duplicated(keep=False)].unique()

    return CompletenessReport(
        freq=freq, market=market, start=idx.min(), end=idx.max(),
        expected_count=len(expected), actual_count=len(actual_unique),
        missing=missing.sort_values(), duplicated=duplicated.sort_values(),
        unexpected=unexpected.sort_values(), nat_rows=nat_rows,
    )


# --------------------------------------------------------------------------- #
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verifica la completitud temporal de un CSV OHLCV.")
    p.add_argument("csv", help="Ruta al archivo CSV.")
    p.add_argument("--date-col", default=None, help="Columna de fecha (default: autodetectar 'Date').")
    p.add_argument("--freq", default="1h", help='Frecuencia esperada, ej. "1h", "5min", "1D".')
    p.add_argument("--market", choices=["continuous", "session"], default="continuous")
    p.add_argument("--session-start", default=None, help='Ej. "09:30" (sólo market=session).')
    p.add_argument("--session-end", default=None, help='Ej. "16:00" (sólo market=session).')
    p.add_argument("--market-tz", default="America/New_York")
    p.add_argument("--bar-label", choices=["start", "end"], default="start")
    p.add_argument("--show", type=int, default=20, help="Cuántos timestamps faltantes listar.")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    df = pd.read_csv(args.csv)
    date_col = args.date_col or next(
        (c for c in df.columns if c.lower() in ("date", "datetime", "timestamp", "fecha")), None)
    if date_col is None:
        raise SystemExit(
            f"No se encontró una columna de fecha en {args.csv} (columnas: {list(df.columns)}). "
            "Indicala con --date-col, o revisá si el CSV se guardó sin el índice de fechas "
            "(pandas: to_csv(..., index=True) o resetear el índice antes de guardar)."
        )

    rep = check_completeness(
        df, date_col=date_col, freq=args.freq, market=args.market,
        session_start=args.session_start, session_end=args.session_end,
        market_tz=args.market_tz, bar_label=args.bar_label,
    )
    print(rep)
    if len(rep.missing):
        print(f"\nPrimeras {min(args.show, len(rep.missing))} fechas faltantes:")
        for ts in rep.missing[:args.show]:
            print(f"  {ts}")
    if len(rep.duplicated):
        print(f"\nFechas duplicadas ({len(rep.duplicated)}):")
        for ts in rep.duplicated[:args.show]:
            print(f"  {ts}")
    if len(rep.unexpected):
        print(f"\nFechas fuera de la grilla esperada ({len(rep.unexpected)}):")
        for ts in rep.unexpected[:args.show]:
            print(f"  {ts}")


if __name__ == "__main__":
    main()
