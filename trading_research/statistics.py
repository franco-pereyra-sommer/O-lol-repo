"""
Estadísticas por condición y línea base.

Todas las probabilidades usan el MISMO denominador (número de entradas), así
que P(TP)+P(SL)+P(NONE)+P(AMBIGUOUS) = 1.

El retorno esperado se calcula como media de los retornos individuales,
E[R] = (1/N) Σ R_i, lo que evita inconsistencias en casos especiales
(NONE con retorno variable, AMBIGUOUS, gaps en el SL).

Se agregan, como ayuda de interpretación (NO como score):
  - intervalo de Wilson al 95 % para P(TP_FIRST);
  - error estándar y t de la media del retorno neto. Advertencia: si las
    entradas de una misma condición se solapan en el tiempo (cooldown <
    horizonte), los retornos no son independientes y el t sobreestima la
    evidencia.
  - diferencias ("lift") respecto de la línea base del mismo segmento.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from .config import ResearchConfig
from .entry_detector import EntryDetection, Segment
from .outcome_evaluator import (AMBIGUOUS, NONE, OUTCOME_NAMES, SL_FIRST, TP_FIRST,
                                OutcomeTable)

Z95 = 1.959963984540054


def wilson_interval(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (centre - half, centre + half)


def min_cases_required(cfg: ResearchConfig, n_segment_bars: int) -> int:
    return int(max(cfg.MIN_CASES_ABSOLUTE, math.ceil(cfg.MIN_CASES_FRACTION * n_segment_bars)))


def _pct(x: float) -> str:
    return "nan" if x is None or not np.isfinite(x) else f"{x:.4g}"


def compute_stats(entry_idx: np.ndarray, table: OutcomeTable, cfg: ResearchConfig,
                  n_segment_bars: int) -> dict[str, Any]:
    """Métricas a partir de las velas de entrada (independiente de la condición)."""
    n = int(len(entry_idx))
    s: dict[str, Any] = {"n_entries": n,
                         "fraction_of_dataset": n / n_segment_bars if n_segment_bars else math.nan}
    oc = table.outcome[entry_idx]
    counts = {name: int((oc == code).sum()) for code, name in
              ((TP_FIRST, "TP_FIRST"), (SL_FIRST, "SL_FIRST"), (NONE, "NONE"),
               (AMBIGUOUS, "AMBIGUOUS"))}
    for name, k in counts.items():
        s[f"{name}_count"] = k
    for name, k in counts.items():
        s[f"P_{name}"] = k / n if n else math.nan
    lo, hi = wilson_interval(counts["TP_FIRST"], n)
    s["P_TP_FIRST_ci95_low"], s["P_TP_FIRST_ci95_high"] = lo, hi

    g = table.gross_return[entry_idx]
    r = table.net_return[entry_idx]
    mfe, mae = table.mfe[entry_idx], table.mae[entry_idx]
    nan = math.nan
    s["mean_gross_return"] = float(g.mean()) if n else nan
    s["median_gross_return"] = float(np.median(g)) if n else nan
    s["mean_net_return"] = float(r.mean()) if n else nan
    s["median_net_return"] = float(np.median(r)) if n else nan
    # Alias explícitos pedidos en la especificación
    s["expected_return"] = s["mean_gross_return"]
    s["net_expected_return"] = s["mean_net_return"]
    s["std_net_return"] = float(r.std(ddof=1)) if n > 1 else nan
    s["se_mean_net_return"] = s["std_net_return"] / math.sqrt(n) if n > 1 else nan
    s["t_mean_net_return"] = (s["mean_net_return"] / s["se_mean_net_return"]
                              if n > 1 and s["se_mean_net_return"] > 0 else nan)
    non_amb = oc != AMBIGUOUS
    s["mean_net_return_excl_ambiguous"] = float(r[non_amb].mean()) if non_amb.any() else nan
    s["win_rate_net"] = float((r > 0).mean()) if n else nan
    s["mean_holding_bars"] = float(table.exit_offset[entry_idx].mean() + 1) if n else nan

    s["mean_MFE"] = float(mfe.mean()) if n else nan
    s["median_MFE"] = float(np.median(mfe)) if n else nan
    s["mean_MAE"] = float(mae.mean()) if n else nan
    s["median_MAE"] = float(np.median(mae)) if n else nan
    for q in cfg.QUANTILES:
        s[f"MFE_q{q:g}"] = float(np.quantile(mfe, q)) if n else nan
        s[f"MAE_q{q:g}"] = float(np.quantile(mae, q)) if n else nan
        s[f"net_return_q{q:g}"] = float(np.quantile(r, q)) if n else nan
    for x in cfg.MFE_THRESHOLDS:
        s[f"P_MFE_ge_{x:g}"] = float((mfe >= x).mean()) if n else nan
    for x in cfg.MAE_THRESHOLDS:
        s[f"P_MAE_le_-{x:g}"] = float((mae <= -x).mean()) if n else nan
    for name, arr in table.favorable.items():
        s[f"P_{name}"] = float(arr[entry_idx].mean()) if n else nan
    return s


def run_parameters(cfg: ResearchConfig) -> dict[str, Any]:
    """Parámetros que se adjuntan a cada fila de resultados."""
    return {"asset": cfg.ASSET, "timeframe": cfg.TIMEFRAME, "side": cfg.POSITION_TYPE,
            "TP": cfg.TP_PERCENT, "SL": cfg.SL_PERCENT, "holding_horizon": cfg.MAX_HOLDING_BARS,
            "cooldown": cfg.MIN_BARS_BETWEEN_SAME_CONDITION_ENTRIES,
            "commission": cfg.COMMISSION_RATE, "slippage": cfg.SLIPPAGE_RATE,
            "spread": cfg.SPREAD_RATE, "ambiguous_policy": cfg.AMBIGUOUS_RETURN_POLICY,
            "random_seed": cfg.RANDOM_SEED}


def baseline_stats(segment: Segment, table: OutcomeTable, cfg: ResearchConfig) -> dict[str, Any]:
    """Entrar en TODAS las velas del segmento (sin condición, sin cooldown)."""
    last_ok = segment.end - 1 - cfg.MAX_HOLDING_BARS
    t = np.arange(segment.start, last_ok + 1)
    s = compute_stats(t + 1, table, cfg, segment.n_bars)
    s["condition"] = "BASELINE (todas las velas)"
    return s


def add_lift(stats: dict[str, Any], base: dict[str, Any]) -> None:
    for k in ("P_TP_FIRST", "mean_gross_return", "mean_net_return", "mean_MFE", "mean_MAE"):
        stats[f"lift_{k}"] = stats.get(k, math.nan) - base.get(k, math.nan)


def events_frame(df: pd.DataFrame, det: EntryDetection, table: OutcomeTable,
                 cond_id: str, cond_desc: str, segment: str) -> pd.DataFrame:
    e, t = det.entry_idx, det.confirm_idx
    return pd.DataFrame({
        "segment": segment,
        "condition_id": cond_id,
        "condition_description": cond_desc,
        "confirm_timestamp": df.index[t],
        "entry_timestamp": df.index[e],
        "entry_price": table.entry_price[e],
        "outcome": OUTCOME_NAMES[table.outcome[e]],
        "exit_bar_offset": table.exit_offset[e],
        "exit_price": table.exit_price[e],
        "MFE": table.mfe[e],
        "MAE": table.mae[e],
        "return": table.gross_return[e],
        "net_return": table.net_return[e],
    })


def format_report(s: dict[str, Any]) -> str:
    """Resumen legible de una condición (similar al ejemplo de la sección 40)."""
    lines = [f"Condition:\n    {s.get('condition', '')}",
             f"Entries: {s['n_entries']}   (fracción del segmento: {_pct(s['fraction_of_dataset'])})"]
    for k in ("TP_FIRST", "SL_FIRST", "NONE", "AMBIGUOUS"):
        lines.append(f"{k:<10} {s[f'{k}_count']:>6}   P = {_pct(s[f'P_{k}'])}")
    lines += [
        f"P(TP_FIRST) IC95 Wilson: [{_pct(s['P_TP_FIRST_ci95_low'])}, {_pct(s['P_TP_FIRST_ci95_high'])}]",
        f"Mean / median MFE: {_pct(s['mean_MFE'])} / {_pct(s['median_MFE'])}",
        f"Mean / median MAE: {_pct(s['mean_MAE'])} / {_pct(s['median_MAE'])}",
        f"Mean gross return: {_pct(s['mean_gross_return'])}",
        f"Mean net return:   {_pct(s['mean_net_return'])}   (t = {_pct(s['t_mean_net_return'])})",
    ]
    return "\n".join(lines)
