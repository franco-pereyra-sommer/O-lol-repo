"""
Estudio de operaciones superpuestas (EXP-007): ¿qué estadístico es válido y qué cooldown conviene?

Parte A (por condición): señales aleatorias sobre un camino aleatorio (sin ventaja) -> distribución
  del t de la media de las entradas de UNA condición según el cooldown (fixed c / until_exit).
Parte B (por procedimiento): corre el walk-forward COMPLETO (búsqueda de condiciones en TRAIN, medición en
  VALIDATION) sobre series sintéticas sin costos y sin ventaja (y, aparte, con una ventaja débil) y
  compara estadísticos del resultado OOS:
    t_entradas : t entre todas las entradas OOS agrupadas (el que se usaba antes de EXP-003)
    t_folds    : t entre folds (EXP-003)
    t_hac_H    : t de Newey-West con H rezagos sobre la serie por vela (EXP-005)
    t_hac_3H   : ídem con 3H
    p_boot     : p del bootstrap estacionario (bloque 3H), una cola
  Se reporta P(t > 2), P(t > 3) y P(p_boot < 0,05) bajo la nula (ideal con t normal: 2,3 % y 0,13 %; 5 %).

    python run_overlap_study.py --reps 60
"""
from __future__ import annotations

import argparse
import json
import logging
import time

import numpy as np
import pandas as pd

from trading_research.config import ResearchConfig
from trading_research.entry_detector import Segment, detect_entries
from trading_research.multiple_testing import newey_west_t, procedure_series, reality_check
from trading_research.outcome_evaluator import build_outcome_table
from trading_research.walk_forward import run_walk_forward


def make_df(n: int, seed: int, phi: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # media -sigma^2/2: el precio (no el log) es una martingala, así la nula tiene retorno esperado 0
    # (con log-retornos de media 0 el precio tiene deriva +sigma^2/2 y las operaciones LONG ganan en promedio).
    eps = rng.normal(-0.5 * 0.01 ** 2 / (1 - phi ** 2), 0.01, n)
    r = np.empty(n)
    r[0] = eps[0]
    for t in range(1, n):
        r[t] = phi * r[t - 1] + eps[t]
    c = 100 * np.exp(np.cumsum(r))
    o = np.r_[c[0], c[:-1]] * np.exp(rng.normal(0, 0.001, n))
    h = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, 0.003, n)))
    l = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, 0.003, n)))
    idx = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c, "Volume": 1.0}, index=idx)


def zero_cost_cfg(H: int, mode: str, cd: int, **kw) -> ResearchConfig:
    return ResearchConfig(
        COST_SCENARIO="custom", COMMISSION_RATE=0.0, SLIPPAGE_RATE=0.0, SPREAD_RATE=0.0,
        TP_PERCENT=0.03, SL_PERCENT=0.03, MAX_HOLDING_BARS=H, AMBIGUOUS_RETURN_POLICY="midpoint",
        COOLDOWN_MODE=mode, MIN_BARS_BETWEEN_SAME_CONDITION_ENTRIES=cd, FILTER_MODE="both",
        MAX_CONDITION_DEPTH=1, N_SIMPLE_CONDITIONS=300, SAVE_EVENTS=False, WALK_FORWARD=True,
        WF_TRAIN_BARS=1500, WF_VAL_BARS=500, WF_HOLDOUT_FRACTION=0.0, RANDOM_SEED=1, **kw)


def part_a(H: int, reps: int, n: int = 5000) -> dict:
    cfg = ResearchConfig(MAX_HOLDING_BARS=H, TP_PERCENT=0.05, SL_PERCENT=0.05)
    modes = {"fixed_1": ("fixed", 1), "fixed_5": ("fixed", 5), "fixed_15": ("fixed", 15),
             f"fixed_{H}": ("fixed", H), f"fixed_{2 * H}": ("fixed", 2 * H), "until_exit": ("until_exit", 1)}
    ts = {k: [] for k in modes}
    nn = {k: [] for k in modes}
    seg = Segment("S", 0, n)
    for seed in range(reps):
        df = make_df(n, seed)
        tb = build_outcome_table(df, cfg)
        sig = np.random.default_rng(seed + 1000).random(n) < 0.1
        for k, (m, cd) in modes.items():
            d = detect_entries(sig, seg, H, cd, m, tb.exit_offset)
            r = tb.gross_return[d.entry_idx]
            ts[k].append(r.mean() / (r.std(ddof=1) / np.sqrt(len(r))))
            nn[k].append(len(r))
    out = {}
    for k in modes:
        t = np.array(ts[k])
        out[k] = {"entries": float(np.mean(nn[k])), "sd_t": float(t.std()),
                  "P(|t|>2)": float(np.mean(np.abs(t) > 2)), "P(t>3)": float(np.mean(t > 3))}
    return out


def procedure_stats(df: pd.DataFrame, H: int, mode: str, cd: int) -> dict:
    cfg = zero_cost_cfg(H, mode, cd)
    wf = run_walk_forward(cfg, df)
    s = wf.oos_series
    cov = s["covered"]
    x = procedure_series(s, "custom")[cov]
    ag = wf.aggregate
    return {"t_entradas": ag["oos_pooled_t_all_folds"], "t_folds": ag["oos_fold_level_t"],
            "t_hac_H": newey_west_t(x, H), "t_hac_3H": newey_west_t(x, 3 * H),
            "p_boot": reality_check(x[:, None], n_boot=300, mean_block=3 * H, seed=0)["p_value"],
            "mean_bar": float(x.mean()), "entries": ag["oos_total_entries"], "K": ag["n_folds"]}


def summarize(rows: list[dict]) -> dict:
    d = pd.DataFrame(rows)
    out = {"reps": len(d), "entries_mean": float(d["entries"].mean()), "mean_bar": float(d["mean_bar"].mean())}
    for c in ("t_entradas", "t_folds", "t_hac_H", "t_hac_3H"):
        t = d[c].dropna()
        out[c] = {"sd": float(t.std()), "P(t>2)": float((t > 2).mean()), "P(t>3)": float((t > 3).mean())}
    out["p_boot"] = {"P(p<0.05)": float((d["p_boot"] < 0.05).mean())}
    return out


def main() -> None:
    logging.disable(logging.CRITICAL)
    p = argparse.ArgumentParser()
    p.add_argument("--reps", type=int, default=60)
    p.add_argument("--reps-a", type=int, default=150)
    p.add_argument("--n", type=int, default=9000)
    p.add_argument("--H", type=int, default=50)
    p.add_argument("--phi", type=float, default=0.2, help="autocorrelación del escenario con ventaja (exagerada a propósito)")
    p.add_argument("--out", default=None)
    a = p.parse_args()
    res = {"H": a.H}

    print("== Parte A: una condición aleatoria, sin ventaja ==")
    res["A"] = part_a(a.H, a.reps_a)
    print(pd.DataFrame(res["A"]).T.to_string(float_format=lambda x: f"{x:.3f}"))

    variants = {"until_exit": ("until_exit", 1), "fixed_15": ("fixed", 15), f"fixed_{a.H}": ("fixed", a.H)}
    for scen, phi in (("nula", 0.0), ("ventaja", a.phi)):
        res[scen] = {}
        for name, (m, cd) in variants.items():
            t0 = time.time()
            rows = [procedure_stats(make_df(a.n, 5000 + r, phi), a.H, m, cd) for r in range(a.reps)]
            res[scen][name] = summarize(rows)
            print(f"\n== Parte B: procedimiento, escenario {scen} (phi={phi}), cooldown {name} "
                  f"[{time.time() - t0:.0f}s] ==")
            print(json.dumps(res[scen][name], indent=1))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1)


if __name__ == "__main__":
    main()
