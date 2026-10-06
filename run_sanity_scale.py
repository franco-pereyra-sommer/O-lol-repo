"""
Comprobaciones descriptivas ANTES del walk-forward de EXP-012 (no modifican el protocolo): folds por variante
(TRAIN/VALIDATION escalados por k), fracción útil tras la purga por horizonte, holdout intacto, cobertura
calendario común, línea base sin condición por geometría y operaciones máximas posibles por TRAIN.

    python run_sanity_scale.py --csv "D:\O lol\Guardado de datos\BTCUSDT_binance_1h.csv" --out results/exp012/sanity.json
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import logging

import numpy as np

from trading_research.config import ResearchConfig
from trading_research.data import load_data
from trading_research.entry_detector import Segment, detect_entries
from trading_research.multiple_testing import bonferroni_t_threshold as bt
from trading_research.outcome_evaluator import build_outcome_table
from trading_research.statistics import baseline_stats
from trading_research.walk_forward import make_folds

VARIANTS = (("B0", .05, .03, 100, 1), ("V1", .10, .06, 200, 2), ("V2", .15, .09, 300, 3), ("V3", .20, .12, 400, 4))


def main() -> None:
    logging.disable(logging.CRITICAL)
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    base = ResearchConfig(DATA_SOURCE="csv", CSV_PATH=a.csv, COOLDOWN_MODE="until_exit", WF_HOLDOUT_FRACTION=0.15)
    df = load_data(base)
    n, idx = len(df), df.index
    out: dict = {"n_bars": n}
    cov = {}
    print(f"Velas 1h: {n}  ({idx[0]} -> {idx[-1]})")
    for name, tp, sl, H, k in VARIANTS:
        cfg = dataclasses.replace(base, TP_PERCENT=tp, SL_PERCENT=sl, MAX_HOLDING_BARS=H,
                                  WF_TRAIN_BARS=2500 * k, WF_VAL_BARS=720 * k)
        f, h = make_folds(n, cfg)
        v, t = [x["VALIDATION"] for x in f], [x["TRAIN"] for x in f]
        m = np.zeros(n, bool)
        for s in v:
            m[s.start:s.end] = True
        cov[name] = m
        dfree = len(f) - 1
        out[name] = {"k": k, "folds": len(f), "train_bars": 2500 * k, "val_bars": 720 * k, "H": H,
                     "val_usable_pct": (720 * k - H) / (720 * k), "train_usable_pct": (2500 * k - H) / (2500 * k),
                     "first_val": [str(idx[v[0].start]), str(idx[v[0].end - 1])],
                     "last_val": [str(idx[v[-1].start]), str(idx[v[-1].end - 1])],
                     "holdout_start": str(idx[h.start]), "last_val_ends_at_holdout_start": bool(v[-1].end == h.start),
                     "df": dfree, "bonferroni_K24": bt(24, dfree), "bonferroni_6": bt(6, dfree)}
        print(f"{name}: k={k} TRAIN {2500 * k} h / VAL {720 * k} h / H {H} h -> {len(f)} folds; usable VAL {(720 * k - H) / (720 * k):.1%}, "
              f"TRAIN {(2500 * k - H) / (2500 * k):.1%}; 1ª VAL {idx[v[0].start]} -> {idx[v[0].end - 1]}; última VAL {idx[v[-1].start]} -> "
              f"{idx[v[-1].end - 1]}; holdout desde {idx[h.start]} (la última VAL termina en el inicio del holdout: {v[-1].end == h.start}); "
              f"g.l. {dfree}: Bonferroni(K=24) {bt(24, dfree):.2f}, Bonferroni(6) {bt(6, dfree):.2f}")
    allc = cov["B0"] & cov["V1"] & cov["V2"] & cov["V3"]
    out["common_hours_all"] = int(allc.sum())
    print(f"Horas de VALIDATION comunes a las 4 variantes: {allc.sum()} ({allc.sum() / 720:.0f} ventanas de 30 días); "
          + ", ".join(f"B0∩{x}: {int((cov['B0'] & cov[x]).sum())} h" for x in ("V1", "V2", "V3")))
    print("\nLínea base sin condición (entrar en todas las barras del tramo), costos typical; y máximo de operaciones por TRAIN "
          "(condición que reentra apenas sale):")
    rng = np.random.default_rng(0)
    for name, tp, sl, H, k in VARIANTS:
        for side in ("LONG", "SHORT"):
            cfg = dataclasses.replace(base, TP_PERCENT=tp, SL_PERCENT=sl, MAX_HOLDING_BARS=H, POSITION_TYPE=side)
            tb = build_outcome_table(df, cfg)
            b = baseline_stats(Segment("ALL", 0, int(n * 0.85)), tb, cfg)
            sig = np.ones(n, bool)
            c = [len(detect_entries(sig, Segment("T", int(s0), int(s0) + 2500 * k), H, 1, "until_exit", tb.exit_offset).entry_idx)
                 for s0 in rng.integers(0, int(n * 0.85) - 2500 * k, 40)]
            r = {x: float(b[x]) for x in ("P_TP_FIRST", "P_SL_FIRST", "P_NONE", "P_AMBIGUOUS", "mean_gross_return",
                                          "mean_net_return", "mean_holding_bars")}
            r["tp_share_of_resolved"] = r["P_TP_FIRST"] / (r["P_TP_FIRST"] + r["P_SL_FIRST"])
            r.update({"max_trades_per_train_mean": float(np.mean(c)), "max_trades_per_train_min": int(min(c)),
                      "share_train_with_max_ge_30": float(np.mean(np.array(c) >= 30))})
            out.setdefault("baseline_all_bars", {})[f"{name}|{side}"] = r
            print(f"  {name} {side}: TP {r['P_TP_FIRST'] * 100:.1f}% SL {r['P_SL_FIRST'] * 100:.1f}% NONE {r['P_NONE'] * 100:.1f}% "
                  f"AMB {r['P_AMBIGUOUS'] * 100:.2f}% | TP/(TP+SL) {r['tp_share_of_resolved'] * 100:.1f}% (ref. 37,5%) | bruto {r['mean_gross_return'] * 100:+.3f}% "
                  f"neto {r['mean_net_return'] * 100:+.3f}% | duración {r['mean_holding_bars']:.0f} h | máx. operaciones/TRAIN: media "
                  f"{r['max_trades_per_train_mean']:.0f}, mín {r['max_trades_per_train_min']}, TRAIN con máx>=30: {r['share_train_with_max_ge_30']:.0%}")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, default=float)


if __name__ == "__main__":
    main()
