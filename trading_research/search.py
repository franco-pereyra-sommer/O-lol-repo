"""
Orquestación de la búsqueda exploratoria.

  datos → features → tabla de resultados por vela
        → Etapa 1 (simples, TRAIN) → pool informativo
        → Etapa 2 (complejas, TRAIN)
        → filtros TRAIN → re-evaluación en VALIDATION → filtros
        → (opcional, una vez) TEST
        → guardado de resultados + metadatos

Sobre multiple testing: se registra cuántas hipótesis se evaluaron en cada
etapa (`meta["n_conditions_evaluated_*"]`). Con cientos de condiciones, es
esperable que varias pasen los filtros de TRAIN por azar; por eso el criterio
de supervivencia exige pasar también en VALIDATION, y el TEST se reserva.
Aun así, que una condición sobreviva NO demuestra que sea una estrategia.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .condition_generator import ConditionGenerator
from .conditions import Condition, condition_id
from .config import ResearchConfig
from .data import load_data, quality_report
from .entry_detector import Segment, detect_entries
from .features import FeatureStore
from .outcome_evaluator import OutcomeTable, build_outcome_table
from .statistics import (add_lift, baseline_stats, compute_stats, events_frame,
                         min_cases_required, run_parameters)
from .validation import chronological_split, passes_filters

log = logging.getLogger(__name__)


@dataclass
class SearchResult:
    cfg: ResearchConfig
    results: dict[str, pd.DataFrame]          # segmento -> una fila por condición
    baselines: dict[str, dict[str, Any]]
    events: pd.DataFrame
    conditions: dict[str, Condition]          # condition_id -> árbol
    meta: dict[str, Any] = field(default_factory=dict)

    def survivors(self) -> pd.DataFrame:
        """Condiciones que pasaron TRAIN y VALIDATION (y TEST si se evaluó)."""
        seg = "TEST" if "TEST" in self.results and len(self.results["TEST"]) else "VALIDATION"
        df = self.results.get(seg, pd.DataFrame())
        return df[df["passed"]] if len(df) else df


class ResearchPipeline:
    def __init__(self, cfg: ResearchConfig, df: pd.DataFrame | None = None,
                 store: FeatureStore | None = None,
                 segments: dict[str, Segment] | None = None,
                 table: OutcomeTable | None = None):
        """
        `store` permite reutilizar indicadores/señales ya calculados entre
        corridas sobre los MISMOS datos (p. ej. una grilla de TP/SL): las
        señales de entrada no dependen de TP, SL ni horizonte.
        `segments` reemplaza la división 60/20/20 (lo usa el walk-forward);
        debe tener "TRAIN" y "VALIDATION", y "TEST" si se evalúa el TEST.
        `table` reutiliza una tabla de resultados ya calculada con la MISMA
        configuración de operación (lado, TP, SL, horizonte, costos).
        """
        cfg.validate()
        self.cfg = cfg
        self.df = df if df is not None else load_data(cfg)
        self.store = store if store is not None and store.df is self.df else FeatureStore(self.df)
        self.table: OutcomeTable = table if table is not None else build_outcome_table(self.df, cfg)
        self.segments = segments if segments is not None else chronological_split(len(self.df), cfg)
        if cfg.RUN_TEST_EVALUATION and "TEST" not in self.segments:
            raise ValueError("RUN_TEST_EVALUATION requiere un segmento TEST.")
        self.rng = np.random.default_rng(cfg.RANDOM_SEED)
        self.generator = ConditionGenerator(cfg, self.store, self.segments["TRAIN"].slice, self.rng)
        self.params = run_parameters(cfg)
        # Entradas (vela de entrada) de TODAS las condiciones evaluadas en VALIDATION, para
        # armar la serie OOS del procedimiento (walk_forward.oos_series_arrays).
        self.oos_entries: list[np.ndarray] = []

    # ------------------------------------------------------------------ #
    def evaluate(self, cond: Condition, segment: Segment, stage: str,
                 baseline: dict[str, Any], keep_events: bool = False):
        sig = cond.evaluate(self.store)
        det = detect_entries(sig, segment, self.cfg.MAX_HOLDING_BARS,
                             self.cfg.MIN_BARS_BETWEEN_SAME_CONDITION_ENTRIES,
                             self.cfg.COOLDOWN_MODE, self.table.exit_offset)
        if stage == "validation":
            self.oos_entries.append(det.entry_idx)
        cid = condition_id(cond)
        row: dict[str, Any] = {"condition_id": cid, "condition": cond.describe(),
                               "segment": segment.name, "stage": stage,
                               "depth": cond.depth, "kind": cond.kind.value,
                               "n_raw_signals": det.n_raw_signals,
                               "n_dropped_cooldown": det.n_dropped_cooldown,
                               "n_dropped_horizon": det.n_dropped_horizon}
        row.update(compute_stats(det.entry_idx, self.table, self.cfg, segment.n_bars))
        add_lift(row, baseline)
        ok, why = passes_filters(row, self.cfg, segment.n_bars)
        row["passed"], row["reject_reasons"] = ok, ";".join(why)
        row.update(self.params)
        ev = (events_frame(self.df, det, self.table, cid, cond.describe(), segment.name)
              if keep_events else None)
        return row, ev

    def _evaluate_many(self, conds: list[Condition], segment: Segment, stage: str,
                       baseline: dict[str, Any], keep_events_for: set[str] | None = None):
        rows, evs = [], []
        for c in conds:
            keep = self.cfg.SAVE_EVENTS and (keep_events_for is None or condition_id(c) in keep_events_for)
            r, e = self.evaluate(c, segment, stage, baseline, keep)
            rows.append(r)
            if e is not None and len(e):
                evs.append(e)
        return rows, evs

    def _select_pool(self, rows: list[dict[str, Any]], conds: list[Condition]) -> list[Condition]:
        """
        Pool de la etapa 2: condiciones simples con suficientes casos en TRAIN
        que mejoran la línea base en P(TP_FIRST) o en retorno medio.
        El orden (por lift de P_TP) sólo decide qué bloques se combinan; no es
        un ranking de estrategias.
        """
        need = min_cases_required(self.cfg, self.segments["TRAIN"].n_bars)
        cand = []
        for r, c in zip(rows, conds):
            if r["n_entries"] < need:
                continue
            if (r["lift_P_TP_FIRST"] > self.cfg.STAGE2_MIN_P_TP_LIFT or
                    r["lift_mean_gross_return"] > self.cfg.STAGE2_MIN_MEAN_RETURN_LIFT):
                cand.append((r["lift_P_TP_FIRST"], c))
        cand.sort(key=lambda x: -x[0])
        pool = [c for _, c in cand[: self.cfg.STAGE2_POOL_SIZE]]
        log.info("Pool etapa 2: %d de %d simples informativas.", len(pool), len(cand))
        return pool

    # ------------------------------------------------------------------ #
    def run(self) -> SearchResult:
        cfg, seg = self.cfg, self.segments
        t0 = time.time()
        baselines = {k: baseline_stats(s, self.table, cfg) for k, s in seg.items()}
        if not cfg.RUN_TEST_EVALUATION:
            baselines.pop("TEST", None)  # ni siquiera la línea base del TEST se mira

        # --- Etapa 1
        structured = cfg.SEARCH_MODE == "structured"
        if structured:
            simple = self.generator.generate_structured(cfg.N_SIMPLE_CONDITIONS)
        else:
            simple = self.generator.generate_simple(cfg.N_SIMPLE_CONDITIONS)
        gen_stats = dict(self.generator.stats)
        rows1, _ = self._evaluate_many(simple, seg["TRAIN"], "simple", baselines["TRAIN"], set())
        pool = self._select_pool(rows1, simple)

        # --- Etapa 2
        complex_ = ([] if structured else self.generator.generate_complex(
            pool, cfg.N_COMPLEX_CONDITIONS, cfg.MAX_CONDITION_DEPTH,
            exclude_keys={c.key for c in simple}))
        rows2, _ = self._evaluate_many(complex_, seg["TRAIN"], "complex", baselines["TRAIN"], set())

        all_conds = simple + complex_
        conditions = {condition_id(c): c for c in all_conds}
        train_rows = rows1 + rows2
        train_df = pd.DataFrame(train_rows)
        passed_train = [c for c, r in zip(all_conds, train_rows) if r["passed"]]
        ids_train = {condition_id(c) for c in passed_train}
        log.info("TRAIN: %d/%d condiciones pasan los filtros.", len(passed_train), len(all_conds))

        events = []
        if cfg.SAVE_EVENTS and passed_train:
            _, ev = self._evaluate_many(passed_train, seg["TRAIN"], "train_pass",
                                        baselines["TRAIN"], ids_train)
            events += ev

        # --- VALIDATION
        stage_of = dict(zip(train_df["condition_id"], train_df["stage"]))
        val_rows, ev = self._evaluate_many(passed_train, seg["VALIDATION"], "validation",
                                           baselines["VALIDATION"])
        events += ev
        val_df = pd.DataFrame(val_rows)
        if len(val_df):
            val_df["stage"] = val_df["condition_id"].map(stage_of)
        passed_val = [c for c, r in zip(passed_train, val_rows) if r["passed"]]
        log.info("VALIDATION: %d/%d sobreviven.", len(passed_val), len(passed_train))

        # --- TEST (opcional, una sola vez)
        test_df = pd.DataFrame()
        if cfg.RUN_TEST_EVALUATION:
            test_rows, ev = self._evaluate_many(passed_val, seg["TEST"], "test", baselines["TEST"])
            events += ev
            test_df = pd.DataFrame(test_rows)
            if len(test_df):
                test_df["stage"] = test_df["condition_id"].map(stage_of)
            log.info("TEST: %d/%d mantienen los filtros.",
                     int(test_df["passed"].sum()) if len(test_df) else 0, len(passed_val))

        qr = quality_report(self.df, cfg.TIMEFRAME)
        meta = {
            "created_utc": pd.Timestamp.now(tz="UTC").isoformat(),
            "elapsed_seconds": round(time.time() - t0, 2),
            "random_seed": cfg.RANDOM_SEED,
            "data": {"n_bars": qr.n_bars, "start": str(qr.start), "end": str(qr.end),
                     "n_gaps": qr.n_gaps, "max_gap": str(qr.max_gap)},
            "segments": {k: {"start": str(self.df.index[s.start]),
                             "end": str(self.df.index[s.end - 1]), "n_bars": s.n_bars,
                             "min_cases": min_cases_required(cfg, s.n_bars)}
                         for k, s in seg.items()},
            "search_mode": cfg.SEARCH_MODE,
            "generation": gen_stats,
            "n_conditions_evaluated_simple": len(simple),
            "n_conditions_evaluated_complex": len(complex_),
            "n_conditions_evaluated_total": len(all_conds),
            "stage2_pool_size": len(pool),
            "n_passed_train": len(passed_train),
            "n_passed_validation": len(passed_val),
            "n_passed_test": int(test_df["passed"].sum()) if len(test_df) else None,
            "test_evaluated": cfg.RUN_TEST_EVALUATION,
            "warning": ("Se evaluaron muchas hipótesis: condiciones que pasan los filtros "
                        "pueden hacerlo por azar. No interpretar como estrategias validadas."),
        }
        results = {"TRAIN": train_df, "VALIDATION": val_df}
        if cfg.RUN_TEST_EVALUATION:
            results["TEST"] = test_df
        ev_df = pd.concat(events, ignore_index=True) if events else pd.DataFrame()
        return SearchResult(cfg, results, baselines, ev_df, conditions, meta)


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    return str(o)


def save_results(res: SearchResult, output_dir: str | None = None) -> Path:
    base = Path(output_dir or res.cfg.OUTPUT_DIR)
    stamp = pd.Timestamp.now(tz="UTC").strftime("%Y%m%d_%H%M%S")
    c = res.cfg
    out = base / (f"run_{c.ASSET}_{c.TIMEFRAME}_{c.POSITION_TYPE}_seed{c.RANDOM_SEED}"
                  f"_tp{c.TP_PERCENT:g}_sl{c.SL_PERCENT:g}_h{c.MAX_HOLDING_BARS}_{stamp}")
    out.mkdir(parents=True, exist_ok=True)

    (out / "config.json").write_text(json.dumps(res.cfg.to_dict(), indent=2, default=_json_default))
    (out / "meta.json").write_text(json.dumps(res.meta, indent=2, default=_json_default))
    (out / "baselines.json").write_text(json.dumps(res.baselines, indent=2, default=_json_default))
    conds = {cid: {"description": c.describe(), "depth": c.depth, "kind": c.kind.value,
                   "tree": c.to_dict()} for cid, c in res.conditions.items()}
    (out / "conditions.json").write_text(json.dumps(conds, indent=1, default=_json_default))
    for name, df in res.results.items():
        df.to_csv(out / f"results_{name.lower()}.csv", index=False)
    if len(res.events):
        res.events.to_csv(out / "events.csv.gz", index=False, compression="gzip")
    log.info("Resultados guardados en %s", out)
    return out


def load_conditions(path: str | Path) -> dict[str, Condition]:
    """Reconstruye los árboles guardados en conditions.json."""
    from .conditions import condition_from_dict
    d = json.loads(Path(path).read_text())
    return {cid: condition_from_dict(v["tree"]) for cid, v in d.items()}
