"""
EXP-013: reglas de exposición "comprado o en efectivo" (revisión diaria) contra exposición constante igualada.
Pre-especificación completa en RESEARCH_LOG.md (entrada EXP-013). No se ajusta nada: las tres reglas son fijas.

Orden: (1) ventanas = VALIDATION de B0; el holdout no se carga en ningún cálculo; (2) verificación de
causalidad sobre los datos reales (truncar y perturbar) ANTES de calcular cualquier retorno: si falla, se
aborta (escenario D); (3) métricas, criterio C1-C6, Reality Check informativo y escenario A/B/C.

    pixi run python run_exposure.py --csv "D:\\O lol\\Guardado de datos\\BTCUSDT_binance_1h.csv" --output results/exp013
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from trading_research.config import ResearchConfig
from trading_research.costs import MarketContext, build_cost_model
from trading_research.data import load_data
from trading_research.exposure import (EXP013_RULES, daily_positions, day_starts, evaluate_rule,
                                       side_cost, summarize)
from trading_research.lookahead import perturb_future, truncate
from trading_research.multiple_testing import bonferroni_t_threshold, reality_check
from trading_research.walk_forward import make_folds

K_BEFORE, K_AFTER = 30, 33
HYP_BEFORE, N_RULES = 13_831_500, 3
HAC_LAGS, N_BLOCKS, MIN_ENTRIES = 720, 5, 30
SCENARIOS = ("typical", "conservative", "optimistic")


def causality_check(df: pd.DataFrame, first: int, n_checks: int, seed: int,
                    rules=EXP013_RULES) -> list[dict]:
    """Posiciones invariantes al truncar en k (velas 0..k) y al perturbar después de k (velas 0..k+1).
    La mitad de los cortes, en la vela anterior a un cambio de día (donde se decide la posición)."""
    rng = np.random.default_rng(seed)
    n = len(df)
    starts = np.flatnonzero(day_starts(df.index))
    pre = starts[(starts - 1 >= first) & (starts < n - 2)] - 1
    ks = np.r_[rng.choice(pre, n_checks // 2, replace=False),
               rng.integers(first, n - 2, n_checks - n_checks // 2)]
    fails = []
    for rule in rules:
        full = daily_positions(df, rule.state(df))
        for k in ks:
            k = int(k)
            tr = truncate(df, k)
            if not np.array_equal(full[:k + 1], daily_positions(tr, rule.state(tr))):
                fails.append({"rule": rule.name, "k": k, "mode": "truncate"})
            pt = perturb_future(df, k, rng)
            if not np.array_equal(full[:k + 2], daily_positions(pt, rule.state(pt))[:k + 2]):
                fails.append({"rule": rule.name, "k": k, "mode": "perturb"})
    return fails


def main() -> None:
    logging.disable(logging.CRITICAL)
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--output", default="results/exp013")
    ap.add_argument("--n-checks", type=int, default=200)
    ap.add_argument("--boot", type=int, default=1000)
    a = ap.parse_args()
    out_dir = Path(a.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = ResearchConfig(DATA_SOURCE="csv", CSV_PATH=a.csv, WF_TRAIN_BARS=2500, WF_VAL_BARS=720,
                         WF_HOLDOUT_FRACTION=0.15)
    df_all = load_data(cfg)
    folds, hold = make_folds(len(df_all), cfg)
    windows = [f["VALIDATION"] for f in folds]
    assert len(windows) == 90 and windows[-1].end == hold.start, "ventanas distintas de las de B0"
    holdout_start = str(df_all.index[hold.start])
    df = df_all.iloc[:hold.start]          # el holdout no entra en ningún cálculo
    del df_all
    idx = df.index
    meta = {"experiment": "EXP-013", "csv": a.csv, "n_bars_dev": len(df),
            "holdout_start": f"{holdout_start} (vela {hold.start})", "n_windows": len(windows), "eval_first_bar": windows[0].start, "eval_last_bar": windows[-1].end - 1,
            "eval_start": str(idx[windows[0].start]), "eval_end": str(idx[windows[-1].end - 1]),
            "rules": {r.name: r.describe() for r in EXP013_RULES},
            "K_before": K_BEFORE, "K_after": K_AFTER, "hypotheses_new": N_RULES * len(windows),
            "hypotheses_cum": HYP_BEFORE + N_RULES * len(windows), "hac_lags": HAC_LAGS,
            "n_blocks": N_BLOCKS, "min_entries": MIN_ENTRIES}
    print(f"Período evaluado: {meta['eval_start']} -> {meta['eval_end']} ({windows[-1].end - windows[0].start} h, "
          f"{len(windows)} ventanas); holdout desde {meta['holdout_start']} (no se usa)")

    # (2) causalidad sobre datos reales, antes de cualquier retorno
    fails = causality_check(df, windows[0].start - 1, a.n_checks, seed=13)
    meta["causality_checks"] = {"cuts": a.n_checks, "rules": len(EXP013_RULES), "failures": fails}
    if fails:
        meta["scenario"] = "D"
        (out_dir / "summary.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"FALLA DE CAUSALIDAD ({len(fails)}): escenario D, no se calcula nada más.")
        sys.exit(2)
    print(f"Causalidad: 0 fallas en {a.n_checks} cortes x {len(EXP013_RULES)} reglas (truncar y perturbar)")

    # (3) métricas
    thr = max(3.0, bonferroni_t_threshold(K_AFTER, len(windows) - 1))
    meta["threshold_C1"] = thr
    costs = {k: build_cost_model(k, cfg) for k in SCENARIOS}
    meta["one_side_cost_typical"] = float(side_cost(costs["typical"], MarketContext(df), np.array([windows[0].start]))[0])
    results, summaries = {}, {}
    eval_bars = np.arange(windows[0].start, windows[-1].end)
    for rule in EXP013_RULES:
        st = rule.state(df)
        pos = daily_positions(df, st)
        res = evaluate_rule(df, rule.name, pos, windows, costs)
        s = summarize(res, threshold=thr, hac_lags=HAC_LAGS, n_blocks=N_BLOCKS, min_entries=MIN_ENTRIES)
        s["n_nan_state_eval"] = int((~np.isfinite(rule.operand.compute(df)[eval_bars])).sum())
        results[rule.name], summaries[rule.name] = res, s
        wdf = pd.DataFrame({
            "window": np.arange(len(windows)),
            "start": [str(idx[w.start]) for w in windows], "end": [str(idx[w.end - 1]) for w in windows],
            "exposure": res.per_window(res.pos) / np.array([w.n_bars for w in windows]),
            "buy_hold": res.per_window(res.r),
            "gross_lift": res.per_window(res.gross_lift()),
            **{f"net_lift_{k}": res.per_window(res.net_lift(k)) for k in SCENARIOS},
            "rule_net_typical": res.per_window(res.net("typical")),
            "sides_paid": res.per_window(res.switches),
        })
        wdf.to_csv(out_dir / f"windows_{rule.name}.csv", index=False)

    # Reality Check informativo sobre las tres series de lift neto (typical)
    F = np.column_stack([results[r.name].net_lift("typical") for r in EXP013_RULES])
    rc = {}
    for blk in (1200, 300):
        g = reality_check(F, n_boot=a.boot, mean_block=blk, seed=0)
        ind = {r.name: reality_check(F[:, [j]], n_boot=a.boot, mean_block=blk, seed=0)["p_value"]
               for j, r in enumerate(EXP013_RULES)}
        rc[str(blk)] = {"p_value": g["p_value"], "best": EXP013_RULES[g["best"]].name if g["best"] >= 0 else None,
                        "individual_p": ind}
    meta["reality_check_informative"] = rc

    # escenario (fijado antes de correr)
    cand = [n for n, s in summaries.items() if s["candidate"]]
    nominal = [n for n, s in summaries.items()
               if s["t_windows_net_lift_typical"] >= 2 or s["t_windows_gross_lift"] >= 2]
    evaluable = all(s["evaluable"] for s in summaries.values())
    if cand:
        scen = "C"
    elif nominal:
        scen = "B"
    else:
        scen = "A informativo" if evaluable else "A (con reglas no evaluables)"
    meta.update({"scenario": scen, "candidates": cand, "nominal_t_ge_2": nominal, "all_evaluable": evaluable,
                 "rules_summary": summaries})
    (out_dir / "summary.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=float),
                                          encoding="utf-8")

    print(f"Umbral C1 = {thr:.3f} (K = {K_AFTER}, {len(windows) - 1} g.l.); costo por lado typical = "
          f"{meta['one_side_cost_typical']:.4%}")
    for n, s in summaries.items():
        print(f"\n{n}: {meta['rules'][n]}")
        print(f"  exposición ē {s['exposure']:.3f} | entradas {s['n_entries']} | episodio medio {s['mean_episode_hours']:.0f} h"
              f" | lados pagados {s['n_sides_paid']} | NaN {s['n_nan_state_eval']}")
        print(f"  comprar y mantener {s['buy_hold_sum']:+.3f} | benchmark ē {s['benchmark_sum']:+.3f} | regla bruto "
              f"{s['rule_gross_sum']:+.3f} | regla neto typ {s['rule_net_sum_typical']:+.3f} / cons "
              f"{s['rule_net_sum_conservative']:+.3f}")
        print(f"  lift bruto: suma {s['gross_lift_sum']:+.4f}, media/ventana {s['gross_lift_mean_window']:+.5f}, "
              f"t {s['t_windows_gross_lift']:+.2f}, HAC {s['hac_gross_lift']:+.2f}")
        for k in SCENARIOS:
            print(f"  lift neto {k}: suma {s['net_lift_sum_' + k]:+.4f}, media/ventana {s['net_lift_mean_window_' + k]:+.5f}, "
                  f"t {s['t_windows_net_lift_' + k]:+.2f}, HAC {s['hac_net_lift_' + k]:+.2f}, ventanas > 0: "
                  f"{s['windows_net_lift_gt0_' + k]}/{s['n_windows']}")
        print(f"  tramos (lift neto typ): {', '.join(f'{x:+.3f}' for x in s['block_net_lift'])} -> {s['blocks_positive']}/5 > 0")
        print(f"  máx. caída: regla {s['max_drawdown_rule_typical']:+.3f}, benchmark {s['max_drawdown_benchmark']:+.3f}, "
              f"comprar y mantener {s['max_drawdown_buy_hold']:+.3f} | Sharpe regla {s['sharpe_rule_typical']:.2f}, "
              f"comprar y mantener {s['sharpe_buy_hold']:.2f}")
        print(f"  criterios: {s['criteria']} -> candidata: {s['candidate']}; evaluable: {s['evaluable']}")
    for blk, v in rc.items():
        print(f"\nReality Check (informativo, bloque {blk} h): p = {v['p_value']:.3f}, mejor {v['best']}, "
              f"individuales {v['individual_p']}")
    print(f"\nESCENARIO: {scen}  (candidatas {cand}; t >= 2: {nominal})")


if __name__ == "__main__":
    main()
