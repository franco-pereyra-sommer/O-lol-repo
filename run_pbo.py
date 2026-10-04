"""
Diagnóstico PBO (CSCV) del PROCESO de selección: genera N condiciones simples con el mismo
generador de la búsqueda, las evalúa en S bloques temporales del período de desarrollo
(el holdout final queda afuera) y calcula la Probability of Backtest Overfitting.

    python run_pbo.py --csv "D:\\O lol\\Guardado de datos\\BTCUSDT_binance_1h.csv" --side LONG SHORT

Aviso: los umbrales de las condiciones se calibran con TODO el período de desarrollo (a diferencia
del walk-forward), así que esto mide el sobreajuste de la elección "la mejor IN-sample entre N
condiciones", no el desempeño de un procedimiento fuera de muestra. No es un experimento de
rentabilidad.
"""
from __future__ import annotations

import argparse
import json
import logging

import numpy as np

from trading_research.condition_generator import ConditionGenerator
from trading_research.config import ResearchConfig
from trading_research.data import load_data
from trading_research.entry_detector import Segment
from trading_research.features import FeatureStore
from trading_research.multiple_testing import condition_block_stats, cscv_pbo
from trading_research.outcome_evaluator import build_outcome_table


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--side", nargs="+", default=["LONG"], choices=("LONG", "SHORT"))
    p.add_argument("--tp", type=float, default=0.05)
    p.add_argument("--sl", type=float, default=0.03)
    p.add_argument("--horizon", type=int, default=100)
    p.add_argument("--n-conditions", type=int, default=7500)
    p.add_argument("--blocks", type=int, default=16)
    p.add_argument("--holdout", type=float, default=0.15)
    p.add_argument("--min-trades", type=int, default=30)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default=None, help="JSON de salida.")
    a = p.parse_args()

    results = {}
    for side in a.side:
        cfg = ResearchConfig(DATA_SOURCE="csv", CSV_PATH=a.csv, POSITION_TYPE=side,
                             TP_PERCENT=a.tp, SL_PERCENT=a.sl, MAX_HOLDING_BARS=a.horizon,
                             COOLDOWN_MODE="until_exit", RANDOM_SEED=a.seed,
                             N_SIMPLE_CONDITIONS=a.n_conditions, MAX_CONDITION_DEPTH=1)
        df = load_data(cfg)
        n_dev = int(round(len(df) * (1 - a.holdout)))
        edges = np.linspace(0, n_dev, a.blocks + 1).astype(int)
        blocks = [Segment(f"B{i}", int(edges[i]), int(edges[i + 1])) for i in range(a.blocks)]
        store = FeatureStore(df)
        table = build_outcome_table(df, cfg)
        gen = ConditionGenerator(cfg, store, slice(0, n_dev), np.random.default_rng(a.seed))
        conds = gen.generate_simple(a.n_conditions)
        sums = np.zeros((a.blocks, len(conds)))
        cnts = np.zeros_like(sums)
        for j, c in enumerate(conds):
            sums[:, j], cnts[:, j] = condition_block_stats(
                c.evaluate(store), table.net_return, table.exit_offset, blocks, a.horizon,
                cfg.MIN_BARS_BETWEEN_SAME_CONDITION_ENTRIES, cfg.COOLDOWN_MODE)
        tot_n = cnts.sum(0)
        with np.errstate(invalid="ignore", divide="ignore"):
            all_mean = np.where(tot_n >= a.min_trades, sums.sum(0) / tot_n, np.nan)
        out = cscv_pbo(sums, cnts, min_trades=a.min_trades)
        lam = out.pop("lambda")
        out.update({"side": side, "n_conditions": len(conds), "n_blocks": a.blocks,
                    "n_with_min_trades_all_dev": int(np.isfinite(all_mean).sum()),
                    "frac_all_dev_mean_gt0": float(np.nanmean(all_mean > 0)),
                    "median_all_dev_mean": float(np.nanmedian(all_mean)),
                    "best_all_dev_mean": float(np.nanmax(all_mean)),
                    "lambda_median": float(np.median(lam))})
        results[side] = out
        print(f"\n{side}  N={len(conds)}  S={a.blocks}  combinaciones={out['n_combinations']}")
        for k in ("pbo", "mean_is_best", "mean_oos_best", "prob_oos_loss", "slope_oos_on_is",
                  "frac_all_dev_mean_gt0", "median_all_dev_mean", "best_all_dev_mean"):
            print(f"  {k:<24} {out[k]:.4f}")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
