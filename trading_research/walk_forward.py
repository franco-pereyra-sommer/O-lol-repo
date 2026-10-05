"""
Walk-forward: repetir la búsqueda en varias ventanas sucesivas.

    pasado ---------------------------------------------------------> futuro
    [ TRAIN 1        ][VAL 1]
          [ TRAIN 2        ][VAL 2]
                [ TRAIN 3        ][VAL 3]          ...        [ HOLDOUT ]

En cada fold se corre la búsqueda COMPLETA sobre su TRAIN (generación con
umbrales de ese TRAIN, etapas 1 y 2, filtros) y se evalúan las condiciones
seleccionadas en el período inmediatamente posterior (VAL), que no participó
en la búsqueda de ese fold. Lo que se valida así es el PROCEDIMIENTO: "si
busco condiciones en el pasado con estas reglas, ¿funcionan en el período
siguiente?". Hacerlo en varios períodos (alcistas, bajistas, laterales)
evita conclusiones que dependen de un único régimen de mercado.

El HOLDOUT final no se usa en ningún fold. Si se pide (--run-test), se
evalúan en él las condiciones que sobrevivieron al ÚLTIMO fold.

Métricas fuera de muestra (OOS) por fold y agregadas:
  - selected : condiciones que pasaron el filtro en TRAIN (lo que uno
               operaría confiando sólo en el pasado)
  - pooled   : todas las entradas OOS de las seleccionadas juntas
  - baseline : entrar en todas las velas del mismo VAL
Un procedimiento útil debería mostrar retorno OOS > línea base de forma
consistente en la mayoría de los folds, no sólo en promedio.
"""
from __future__ import annotations

import dataclasses
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import ResearchConfig
from .entry_detector import Segment
from .features import FeatureStore
from .multiple_testing import newey_west_t, procedure_series
from .outcome_evaluator import OutcomeTable, build_outcome_table
from .search import ResearchPipeline, SearchResult, _json_default, save_results

log = logging.getLogger(__name__)


def make_folds(n_bars: int, cfg: ResearchConfig) -> tuple[list[dict[str, Segment]], Segment | None]:
    """Devuelve (folds, holdout). Cada fold es {"TRAIN": Segment, "VALIDATION": Segment}."""
    n_hold = int(round(n_bars * cfg.WF_HOLDOUT_FRACTION))
    n_dev = n_bars - n_hold
    if cfg.WF_TRAIN_BARS is not None:
        val_bars, train_bars = cfg.WF_VAL_BARS, cfg.WF_TRAIN_BARS
        k = (n_dev - train_bars) // val_bars
        if k < 1:
            raise ValueError("Datos insuficientes para WF_TRAIN_BARS + WF_VAL_BARS.")
    else:
        k, r = cfg.WF_N_FOLDS, cfg.WF_TRAIN_VAL_RATIO
        val_bars = int(n_dev // (r + k))
        train_bars = int(round(r * val_bars))
    if val_bars < 2 * cfg.MAX_HOLDING_BARS:
        raise ValueError(
            f"Cada VALIDATION tendría {val_bars} velas, muy poco para un horizonte de "
            f"{cfg.MAX_HOLDING_BARS}. Usar menos folds, más datos o un horizonte menor.")
    # Alinear el final del último VAL con el final del período de desarrollo.
    offset = n_dev - (train_bars + k * val_bars)
    folds = []
    for i in range(k):
        v0 = offset + train_bars + i * val_bars
        t0 = 0 if cfg.WF_ANCHORED else v0 - train_bars
        folds.append({"TRAIN": Segment("TRAIN", t0, v0),
                      "VALIDATION": Segment("VALIDATION", v0, v0 + val_bars)})
    holdout = Segment("TEST", n_dev, n_bars) if n_hold > 0 else None
    return folds, holdout


@dataclass
class WalkForwardResult:
    cfg: ResearchConfig
    folds: list[SearchResult]
    summary: pd.DataFrame
    aggregate: dict[str, Any]
    holdout: dict[str, Any] | None = None
    fold_dirs: list[Path] = field(default_factory=list)
    oos_series: dict[str, np.ndarray] | None = None   # arrays de largo n (ver oos_series_arrays)


def _pooled(df: pd.DataFrame, col: str) -> float:
    if not len(df) or df["n_entries"].sum() == 0:
        return float("nan")
    w = df["n_entries"].to_numpy(float)
    x = df[col].to_numpy(float)
    ok = np.isfinite(x)
    return float((w[ok] * x[ok]).sum() / w[ok].sum()) if ok.any() else float("nan")


def pooled_t(df: pd.DataFrame, col: str = "mean_net_return") -> float:
    """t de la media de todas las entradas OOS juntas, a partir de media, desvío y N de cada condición.

    Las entradas de condiciones distintas pueden coincidir en la misma vela, así que
    el t está inflado (no son independientes). Es una cota optimista, no una prueba."""
    if not len(df) or df["n_entries"].sum() < 2:
        return float("nan")
    n = df["n_entries"].to_numpy(float)
    m = df[col].to_numpy(float)
    s = df["std_net_return"].to_numpy(float)
    ok = np.isfinite(m) & np.isfinite(s) & (n > 0)
    n, m, s = n[ok], m[ok], s[ok]
    N = n.sum()
    mu = (n * m).sum() / N
    var = (((n - 1) * s ** 2).sum() + (n * (m - mu) ** 2).sum()) / (N - 1)
    return float(mu / np.sqrt(var / N)) if var > 0 else float("nan")


def oos_series_arrays(entry_lists: list[np.ndarray], table: OutcomeTable, n: int) -> dict[str, np.ndarray]:
    """Serie OOS por vela de UN fold, a partir de las entradas de todas las condiciones
    seleccionadas en su TRAIN y evaluadas en su VALIDATION. Para cada vela de entrada:
      cnt        cantidad de operaciones abiertas en esa vela (todas las condiciones)
      sum_<sc>   suma de sus retornos netos con el escenario de costos <sc>
    El retorno de la vela es sum/cnt (promedio simple entre operaciones) y 0 si cnt = 0
    (efectivo). Ver EXP-004 / EXP-005."""
    e = np.concatenate(entry_lists) if entry_lists else np.zeros(0, dtype=np.int64)
    out = {"cnt": np.bincount(e, minlength=n).astype(float)}
    for sc, arr in table.net_by_scenario.items():
        out[f"sum_{sc}"] = np.bincount(e, weights=arr[e], minlength=n)
    return out


def fold_level_t(summary: pd.DataFrame, col: str = "oos_pooled_mean_net") -> float:
    """t de la media de `col` ENTRE folds (cada fold con el mismo peso; los folds con
    entradas OOS = los que tienen valor). Es un error estándar agrupado por fold: las
    VALIDATION son períodos disjuntos, así que esas medias son mucho más cercanas a
    independientes que las entradas (que se solapan en el tiempo y entre condiciones).
    Con K folds, comparar con una t de Student de K-1 grados de libertad."""
    x = summary[col].to_numpy(float)
    x = x[np.isfinite(x)]
    if len(x) < 2 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def fold_summary(i: int, res: SearchResult, df_index: pd.DatetimeIndex, seg: dict[str, Segment]) -> dict:
    val = res.results["VALIDATION"]
    base = res.baselines["VALIDATION"]
    tr, va = seg["TRAIN"], seg["VALIDATION"]
    row = {
        "fold": i,
        "train_start": df_index[tr.start], "train_end": df_index[tr.end - 1],
        "val_start": df_index[va.start], "val_end": df_index[va.end - 1],
        "val_price_change": None,
        "n_evaluated": res.meta["n_conditions_evaluated_total"],
        "n_attempts": res.meta.get("generation", {}).get("attempts"),
        "n_discarded_duplicate": res.meta.get("generation", {}).get("discarded_duplicate"),
        "selected_in_train": res.meta["n_passed_train"],
        "passed_val": res.meta["n_passed_validation"],
        "base_val_P_TP": base["P_TP_FIRST"],
        "base_val_mean_net": base["mean_net_return"],
        "oos_entries": int(val["n_entries"].sum()) if len(val) else 0,
        "oos_pooled_P_TP": _pooled(val, "P_TP_FIRST"),
        "oos_pooled_mean_net": _pooled(val, "mean_net_return"),
        "oos_median_cond_mean_net": float(val["mean_net_return"].median()) if len(val) else float("nan"),
        "oos_frac_cond_net_gt0": float((val["mean_net_return"] > 0).mean()) if len(val) else float("nan"),
        "oos_frac_cond_beat_base": (float((val["lift_mean_net_return"] > 0).mean())
                                    if len(val) else float("nan")),
    }
    row["oos_pooled_lift_net"] = row["oos_pooled_mean_net"] - row["base_val_mean_net"]
    # Mismo retorno OOS bajo cada escenario de costos (robustez a los costos)
    for col in [c for c in val.columns if c.startswith("mean_net_return_")
                and c != "mean_net_return_excl_ambiguous"]:
        sc = col[len("mean_net_return_"):]
        row[f"oos_pooled_mean_net_{sc}"] = _pooled(val, col)
        row[f"base_val_mean_net_{sc}"] = base.get(col, float("nan"))
    return row


def run_walk_forward(cfg: ResearchConfig, df: pd.DataFrame,
                     store: FeatureStore | None = None) -> WalkForwardResult:
    cfg.validate()
    store = store if store is not None and store.df is df else FeatureStore(df)
    table = build_outcome_table(df, cfg)
    folds, holdout = make_folds(len(df), cfg)
    close = df["Close"].to_numpy()
    results, rows = [], []
    n_bars = len(df)
    series = {"covered": np.zeros(n_bars, dtype=bool), "cnt": np.zeros(n_bars)}
    for sc in table.net_by_scenario:
        series[f"sum_{sc}"] = np.zeros(n_bars)
        series[f"base_{sc}"] = np.full(n_bars, np.nan)
    for i, seg in enumerate(folds, 1):
        last = i == len(folds)
        fcfg = dataclasses.replace(
            cfg, RUN_TEST_EVALUATION=bool(last and cfg.RUN_TEST_EVALUATION and holdout is not None))
        segs = dict(seg)
        if fcfg.RUN_TEST_EVALUATION:
            segs["TEST"] = holdout
        log.info("Fold %d/%d: TRAIN %s → %s | VAL %s → %s", i, len(folds),
                 df.index[seg["TRAIN"].start].date(), df.index[seg["TRAIN"].end - 1].date(),
                 df.index[seg["VALIDATION"].start].date(), df.index[seg["VALIDATION"].end - 1].date())
        pipe = ResearchPipeline(fcfg, df=df, store=store, segments=segs, table=table)
        res = pipe.run()
        va = seg["VALIDATION"]
        part = oos_series_arrays(pipe.oos_entries, table, n_bars)
        for k, v in part.items():
            series[k][va.slice] += v[va.slice]
        series["covered"][va.slice] = True
        for sc in table.net_by_scenario:
            series[f"base_{sc}"][va.slice] = res.baselines["VALIDATION"].get(f"mean_net_return_{sc}", np.nan)
        results.append(res)
        r = fold_summary(i, res, df.index, seg)
        va = seg["VALIDATION"]
        r["val_price_change"] = close[va.end - 1] / close[va.start] - 1
        rows.append(r)

    summary = pd.DataFrame(rows)
    allval = pd.concat([r.results["VALIDATION"] for r in results if len(r.results["VALIDATION"])],
                       ignore_index=True) if any(len(r.results["VALIDATION"]) for r in results) else pd.DataFrame()
    valid = summary.dropna(subset=["oos_pooled_mean_net"])
    agg = {
        "n_folds": len(folds),
        "folds_with_selected": int((summary["selected_in_train"] > 0).sum()),
        "oos_pooled_mean_net_all_folds": _pooled(allval, "mean_net_return"),
        "base_val_mean_net_avg": float(summary["base_val_mean_net"].mean()),
        "folds_oos_net_gt0": int((valid["oos_pooled_mean_net"] > 0).sum()),
        "folds_oos_beat_base": int((valid["oos_pooled_lift_net"] > 0).sum()),
        "oos_pooled_t_all_folds": pooled_t(allval),
        "oos_fold_level_t": fold_level_t(summary),
        # t HAC (Newey-West, 3H rezagos) de la serie OOS por vela del procedimiento (EXP-007)
        "oos_hac_t_3H": newey_west_t(
            procedure_series(series, cfg.COST_SCENARIO)[series["covered"]], 3 * cfg.MAX_HOLDING_BARS)
        if cfg.COST_SCENARIO in table.net_by_scenario else float("nan"),
        "oos_total_entries": int(allval["n_entries"].sum()) if len(allval) else 0,
        "total_conditions_evaluated": int(summary["n_evaluated"].sum()),
        "cost_scenario": cfg.COST_SCENARIO,
    }
    for col in [c for c in summary.columns if c.startswith("oos_pooled_mean_net_")]:
        sc = col[len("oos_pooled_mean_net_"):]
        agg[f"oos_pooled_mean_net_all_folds_{sc}"] = _pooled(allval, f"mean_net_return_{sc}")
        agg[f"folds_oos_net_gt0_{sc}"] = int((summary[col] > 0).sum())
    hold = None
    if cfg.RUN_TEST_EVALUATION and holdout is not None:
        t = results[-1].results.get("TEST", pd.DataFrame())
        b = results[-1].baselines.get("TEST", {})
        hold = {"start": str(df.index[holdout.start]), "end": str(df.index[holdout.end - 1]),
                "evaluated": int(len(t)), "passed": int(t["passed"].sum()) if len(t) else 0,
                "pooled_mean_net": _pooled(t, "mean_net_return"),
                "base_mean_net": b.get("mean_net_return")}
    return WalkForwardResult(cfg, results, summary, agg, hold, oos_series=series)


def save_walk_forward(wf: WalkForwardResult, output_dir: str | Path) -> Path:
    c = wf.cfg
    stamp = pd.Timestamp.now(tz="UTC").strftime("%Y%m%d_%H%M%S")
    out = Path(output_dir) / (f"wf_{c.ASSET}_{c.TIMEFRAME}_{c.POSITION_TYPE}_seed{c.RANDOM_SEED}"
                              f"_tp{c.TP_PERCENT:g}_sl{c.SL_PERCENT:g}_h{c.MAX_HOLDING_BARS}_{stamp}")
    out.mkdir(parents=True, exist_ok=True)
    for i, res in enumerate(wf.folds, 1):
        d = save_results(res, str(out / f"fold_{i}"))
        wf.fold_dirs.append(d)
    wf.summary.to_csv(out / "wf_summary.csv", index=False)
    if wf.oos_series is not None:
        np.savez_compressed(out / "oos_series.npz", **wf.oos_series)
    (out / "wf_aggregate.json").write_text(json.dumps(
        {"aggregate": wf.aggregate, "holdout": wf.holdout, "config": c.to_dict()},
        indent=2, default=_json_default))
    log.info("Walk-forward guardado en %s", out)
    return out
