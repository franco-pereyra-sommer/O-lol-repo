"""
Construcción ESTRICTA de velas de una temporalidad mayor a partir de velas base (EXP-011).

Convención (única e inequívoca):
  - Alineación UTC por época Unix: las velas de 4h abren a las 00, 04, 08, 12, 16 y 20 h UTC
    (00:00-03:59, 04:00-07:59, …). La zona horaria del índice no influye (se usa la época UTC); un índice
    sin zona se interpreta como UTC.
  - El timestamp de la vela agregada es el INICIO del intervalo, igual que el de las velas base (Binance).
    Una vela agregada con timestamp T está disponible (cerrada) recién en T + duración, es decir, cuando
    ya existe su última vela base; una condición evaluada "en t" usa sólo datos hasta ese cierre y la
    entrada es el Open de la fila siguiente (= Open de la siguiente vela agregada completa).
  - Open = Open de la primera vela base; High = máx de los High; Low = mín de los Low; Close = Close de la
    última vela base. (Volume, si existe, se suma, pero ninguna condición lo usa.)
  - Una vela agregada sólo se crea si el bloque contiene TODAS las velas base esperadas, cada una en su
    instante exacto. No se rellena nada (ni forward-fill ni OHLC inventado): los bloques incompletos se
    descartan y quedan como huecos en el tiempo. Las velas base cuyo timestamp no cae en la grilla horaria
    (en los datos de Binance hay 43 en febrero de 2018, con minutos y segundos corridos) no pueden asignarse
    a un bloque UTC sin deformarlo: se descartan y el bloque correspondiente queda incompleto.
  - Un hueco no se "puentea": la fila siguiente a un hueco es simplemente la siguiente vela agregada
    completa. Es el mismo tratamiento que el de las velas de 1h (que también tienen huecos).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _utc_ns(index: pd.DatetimeIndex) -> np.ndarray:
    idx = index
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    return idx.as_unit("ns").asi8.astype("int64")


def aggregate_ohlc_strict(df: pd.DataFrame, rule: str = "4h", base: str = "1h"
                          ) -> tuple[pd.DataFrame, dict]:
    tf_ns = int(pd.Timedelta(rule).value)
    base_ns = int(pd.Timedelta(base).value)
    if tf_ns % base_ns:
        raise ValueError(f"{rule} no es múltiplo de {base}.")
    k = tf_ns // base_ns
    ts = _utc_ns(df.index)
    if len(ts) > 1 and not (np.diff(ts) > 0).all():
        raise ValueError("El índice debe estar ordenado y sin duplicados.")
    aligned = (ts % base_ns) == 0
    t_a = ts[aligned]
    bucket = t_a // tf_ns
    u, counts = np.unique(bucket, return_counts=True)
    complete = u[counts == k]            # timestamps únicos y alineados: k filas = las k velas esperadas
    keep = np.isin(bucket, complete)
    sub = df.loc[aligned].loc[keep]
    nb = len(complete)
    if nb:
        o = sub["Open"].to_numpy("float64").reshape(nb, k)
        h = sub["High"].to_numpy("float64").reshape(nb, k)
        l = sub["Low"].to_numpy("float64").reshape(nb, k)
        c = sub["Close"].to_numpy("float64").reshape(nb, k)
        data = {"Open": o[:, 0], "High": h.max(axis=1), "Low": l.min(axis=1), "Close": c[:, -1]}
        if "Volume" in sub.columns:
            data["Volume"] = sub["Volume"].to_numpy("float64").reshape(nb, k).sum(axis=1)
    else:
        data = {x: np.array([]) for x in ("Open", "High", "Low", "Close")}
    idx = pd.DatetimeIndex(pd.to_datetime(complete * tf_ns, unit="ns", utc=True), name=df.index.name)
    if df.index.tz is None:
        idx = idx.tz_localize(None)
    out = pd.DataFrame(data, index=idx)
    first_b, last_b = (int(ts[aligned][0] // tf_ns), int(ts[aligned][-1] // tf_ns)) if aligned.any() else (0, -1)
    expected = last_b - first_b + 1
    report = {
        "n_source": int(len(df)), "n_source_misaligned": int((~aligned).sum()),
        "n_blocks_expected": int(expected), "n_blocks_complete": int(nb),
        "n_blocks_incomplete_with_data": int((counts < k).sum()),
        "n_blocks_without_data": int(expected - len(u)),
        "n_blocks_discarded": int(expected - nb),
        "pct_blocks_discarded": float((expected - nb) / expected) if expected else float("nan"),
        "n_source_rows_used": int(nb * k),
        "source_first": str(df.index[0]) if len(df) else None, "source_last": str(df.index[-1]) if len(df) else None,
        "first": str(out.index[0]) if nb else None, "last": str(out.index[-1]) if nb else None,
        "n_time_holes": int((np.diff(complete) > 1).sum()) if nb > 1 else 0,
    }
    return out, report
