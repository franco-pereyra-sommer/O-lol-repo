"""
EXP-014: confirmación de R2 (tendencia de 100 días, comprado/efectivo) tal cual en otros activos, con las mismas
ventanas de calendario que EXP-013 (las VALIDATION de B0 en BTC) y el holdout recortado por la fecha del de BTC.
Pre-especificación completa en RESEARCH_LOG.md (entrada EXP-014). No se ajusta nada.

    pixi run python run_exposure_confirm.py --btc-csv "D:\\O lol\\Guardado de datos\\BTCUSDT_binance_1h.csv" ^
        --asset ETHUSDT="D:\\O lol\\Guardado de datos\\ETHUSDT_binance_1h.csv" --asset XRPUSDT=... --asset BNBUSDT=... ^
        --output results/exp014
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from run_exposure import causality_check
from trading_research.config import ResearchConfig
from trading_research.costs import build_cost_model
from trading_research.data import load_data
from trading_research.exposure import (EXP013_RULES, calendar_segments, daily_positions, evaluate_rule,
                                       pool_mean, summarize)
from trading_research.multiple_testing import bonferroni_t_threshold, newey_west_t, reality_check
from trading_research.walk_forward import fold_level_t, make_folds

R2 = next(r for r in EXP013_RULES if r.name == "R2_tendencia_100d")
K_BEFORE, K_AFTER = 33, 36
HYP_BEFORE = 13_831_770
HAC_LAGS, N_BLOCKS, MIN_ENTRIES = 720, 5, 30
SCENARIOS = ("typical", "conservative", "optimistic")
BTC_EXP013 = Path("results/exp013/windows_R2_tendencia_100d.csv")


def btc_calendar(btc_csv: str):
    """Bordes de fecha de las 90 VALIDATION de B0 en BTC y fecha de inicio del holdout de BTC."""
    cfg = ResearchConfig(DATA_SOURCE="csv", CSV_PATH=btc_csv, WF_TRAIN_BARS=2500, WF_VAL_BARS=720,
                         WF_HOLDOUT_FRACTION=0.15)
    idx = load_data(cfg).index
    folds, hold = make_folds(len(idx), cfg)
    v = [f["VALIDATION"] for f in folds]
    assert len(v) == 90 and v[-1].end == hold.start
    return [(idx[s.start], idx[s.end]) for s in v], idx[hold.start]


def main() -> None:
    logging.disable(logging.CRITICAL)
    ap = argparse.ArgumentParser()
    ap.add_argument("--btc-csv", required=True)
    ap.add_argument("--asset", action="append", required=True, help="NOMBRE=ruta.csv (repetible)")
    ap.add_argument("--output", default="results/exp014")
    ap.add_argument("--n-checks", type=int, default=200)
    ap.add_argument("--boot", type=int, default=1000)
    a = ap.parse_args()
    out_dir = Path(a.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    bounds, cut = btc_calendar(a.btc_csv)
    nw = len(bounds)
    meta = {"experiment": "EXP-014", "rule": R2.describe(), "holdout_cut": str(cut),
            "calendar": [str(bounds[0][0]), str(bounds[-1][1])], "n_calendar_windows": nw,
            "K_before": K_BEFORE, "K_after": K_AFTER, "hac_lags": HAC_LAGS, "min_entries": MIN_ENTRIES,
            "assets": {}}
    print(f"Ventanas de calendario: {nw} ({bounds[0][0]} -> {bounds[-1][1]}); se recorta todo desde {cut}")

    thr = max(3.0, bonferroni_t_threshold(K_AFTER, nw - 1))
    meta["threshold_P1"] = thr
    per_L = {k: {} for k in SCENARIOS}
    per_G, per_hour, summaries, problems = {}, {}, {}, []
    for spec in a.asset:
        name, path = spec.split("=", 1)
        cfg = ResearchConfig(DATA_SOURCE="csv", CSV_PATH=path)
        full = load_data(cfg)
        info = {"csv": path, "first_bar": str(full.index[0]), "n_bars_file": len(full)}
        df = full[full.index < cut]                         # el holdout (por fecha) no entra en ningún cálculo
        del full
        segs = calendar_segments(df.index, bounds)
        op = R2.operand.compute(df)
        inc = [w for w, s in enumerate(segs) if s.n_bars > 0 and np.isfinite(op[s.start:s.end]).all()]
        consecutive = bool(inc) and inc == list(range(inc[0], nw))
        span = df.index[segs[inc[0]].start:segs[-1].end] if inc else df.index[:0]
        expected = int(round((span[-1] - span[0]) / pd.Timedelta("1h"))) + 1 if len(span) else 0
        info.update({"n_bars_dev": len(df), "windows_included": len(inc),
                     "first_window": inc[0] if inc else None, "windows_consecutive": consecutive,
                     "eval_bars": len(span), "eval_missing_hours": expected - len(span)})
        print(f"\n{name}: datos desde {info['first_bar']}; ventanas incluidas {len(inc)} (desde la {info['first_window']}), "
              f"consecutivas: {consecutive}; velas evaluadas {len(span)}, horas faltantes {info['eval_missing_hours']}")
        if not consecutive:
            problems.append(f"{name}: ventanas no consecutivas")
            meta["assets"][name] = info
            continue
        fails = causality_check_r2(df, segs[inc[0]].start - 1, a.n_checks)
        info["causality_failures"] = fails
        print(f"  causalidad: {len(fails)} fallas en {a.n_checks} cortes (truncar y perturbar)")
        if fails:
            problems.append(f"{name}: falla de causalidad")
            meta["assets"][name] = info
            continue
        costs = {k: build_cost_model(k, cfg) for k in SCENARIOS}
        windows = [segs[w] for w in inc]
        res = evaluate_rule(df, R2.name, daily_positions(df, R2.state(df)), windows, costs)
        s = summarize(res, threshold=thr, hac_lags=HAC_LAGS, n_blocks=N_BLOCKS, min_entries=MIN_ENTRIES)
        summaries[name] = s
        info["summary"] = s
        meta["assets"][name] = info
        for k in SCENARIOS:
            per_L[k][name] = pd.Series(res.per_window(res.net_lift(k)), index=inc)
        per_G[name] = pd.Series(res.per_window(res.gross_lift()), index=inc)
        per_hour[name] = pd.Series(res.net_lift("typical"), index=df.index[res.bars].as_unit("ns"))
        pd.DataFrame({"window": inc, "start": [str(bounds[w][0]) for w in inc],
                      "exposure": res.per_window(res.pos) / np.array([x.n_bars for x in windows]),
                      "buy_hold": res.per_window(res.r), "gross_lift": per_G[name].to_numpy(),
                      **{f"net_lift_{k}": per_L[k][name].to_numpy() for k in SCENARIOS},
                      "sides_paid": res.per_window(res.switches)}).to_csv(out_dir / f"windows_{name}.csv", index=False)

    evaluable = (not problems and len(summaries) == len(a.asset)
                 and all(s["evaluable"] for s in summaries.values()))
    if not evaluable:
        bad = [n for n, s in summaries.items() if not s["evaluable"]]
        meta.update({"scenario": "D (no concluyente)", "problems": problems, "not_evaluable": bad})
        (out_dir / "summary.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
        print(f"\nESCENARIO: D (no concluyente): {problems} {bad}")
        sys.exit(2)

    # combinado por ventana de calendario y por hora
    P = {k: pool_mean(per_L[k]) for k in SCENARIOS}
    PG = pool_mean(per_G)
    H = pool_mean(per_hour)
    tP = fold_level_t(pd.DataFrame({"x": P["typical"].to_numpy()}), "x")
    blocks = np.array_split(np.arange(nw), N_BLOCKS)
    block_sums = [float(P["typical"].reindex(b).sum()) for b in blocks]
    pooled = {
        "n_windows": int(len(P["typical"])), "mean_window_typical": float(P["typical"].mean()),
        "t_windows_typical": tP, "hac_hourly_typical": newey_west_t(H.to_numpy(), HAC_LAGS),
        "n_hours": int(len(H)),
        "sum_typical": float(P["typical"].sum()), "sum_conservative": float(P["conservative"].sum()),
        "sum_optimistic": float(P["optimistic"].sum()),
        "t_windows_conservative": fold_level_t(pd.DataFrame({"x": P["conservative"].to_numpy()}), "x"),
        "t_windows_gross": fold_level_t(pd.DataFrame({"x": PG.to_numpy()}), "x"),
        "mean_window_gross": float(PG.mean()),
        "block_sums_typical": block_sums, "blocks_positive": int(sum(x > 0 for x in block_sums)),
        "block_dates": [[str(bounds[b[0]][0]), str(bounds[b[-1]][1])] for b in blocks],
    }
    crit = {
        "P1_t_pooled_ge_threshold": bool(pooled["mean_window_typical"] > 0 and tP >= thr),
        "P2_hac_pooled_ge_2": bool(pooled["hac_hourly_typical"] >= 2.0),
        "P3_net_lift_gt0_each_asset": bool(all(s["net_lift_sum_typical"] > 0 for s in summaries.values())),
        "P4_blocks_4_of_5": bool(pooled["blocks_positive"] >= N_BLOCKS - 1),
        "P5_conservative_and_absolute": bool(pooled["sum_conservative"] > 0 and all(
            s["rule_net_sum_typical"] > 0 and s["rule_net_sum_conservative"] > 0 for s in summaries.values())),
        "P6_min_entries_each_asset": bool(all(s["n_entries"] >= MIN_ENTRIES for s in summaries.values())),
    }
    if all(crit.values()):
        scen = "Candidata"
    elif (crit["P3_net_lift_gt0_each_asset"] and crit["P4_blocks_4_of_5"] and crit["P5_conservative_and_absolute"]
          and crit["P6_min_entries_each_asset"] and pooled["mean_window_typical"] > 0 and tP >= 2.0):
        scen = "Consistente, no concluyente"
    else:
        scen = "No confirmada"

    # informativo: correlaciones de lift por ventana (entre activos y con R2 en BTC) y Reality Check en horas comunes
    Lt = pd.concat(per_L["typical"], axis=1)
    if BTC_EXP013.exists():
        Lt["BTCUSDT_EXP013"] = pd.read_csv(BTC_EXP013).set_index("window")["net_lift_typical"]
    corr = Lt.corr().round(3)
    common = pd.concat(per_hour, axis=1, sort=True).dropna()
    rc = {}
    for blk in (1200, 300):
        g = reality_check(common.to_numpy(), n_boot=a.boot, mean_block=blk, seed=0)
        rc[str(blk)] = {"p_value": g["p_value"], "best": list(common.columns)[g["best"]] if g["best"] >= 0 else None}
    hyp_new = int(sum(s["n_windows"] for s in summaries.values()))
    meta.update({"scenario": scen, "criteria": crit, "pooled": pooled, "corr_window_net_lift": corr.to_dict(),
                 "reality_check_common_hours": {"n_hours": int(len(common)), **rc},
                 "hypotheses_new": hyp_new, "hypotheses_cum": HYP_BEFORE + hyp_new})
    pd.DataFrame({"window": P["typical"].index, "pooled_net_lift_typical": P["typical"].to_numpy(),
                  "pooled_net_lift_conservative": P["conservative"].reindex(P["typical"].index).to_numpy(),
                  "pooled_gross_lift": PG.reindex(P["typical"].index).to_numpy()}).to_csv(out_dir / "pooled_windows.csv",
                                                                                            index=False)
    (out_dir / "summary.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=float), encoding="utf-8")

    print(f"\nUmbral P1 = {thr:.3f} (K = {K_AFTER}, {nw - 1} g.l.)")
    for n, s in summaries.items():
        print(f"\n{n}: ē {s['exposure']:.3f} | entradas {s['n_entries']} | episodio medio {s['mean_episode_hours']:.0f} h "
              f"| ventanas {s['n_windows']}")
        print(f"  comprar y mantener {s['buy_hold_sum']:+.3f} | benchmark {s['benchmark_sum']:+.3f} | regla neto typ "
              f"{s['rule_net_sum_typical']:+.3f} / cons {s['rule_net_sum_conservative']:+.3f}")
        print(f"  lift bruto: suma {s['gross_lift_sum']:+.4f}, t {s['t_windows_gross_lift']:+.2f}, HAC {s['hac_gross_lift']:+.2f}")
        for k in SCENARIOS:
            print(f"  lift neto {k}: suma {s['net_lift_sum_' + k]:+.4f}, t {s['t_windows_net_lift_' + k]:+.2f}, "
                  f"HAC {s['hac_net_lift_' + k]:+.2f}, ventanas > 0: {s['windows_net_lift_gt0_' + k]}/{s['n_windows']}")
        print(f"  tramos propios (lift neto typ): {', '.join(f'{x:+.3f}' for x in s['block_net_lift'])}")
        print(f"  máx. caída regla {s['max_drawdown_rule_typical']:+.3f} / benchmark {s['max_drawdown_benchmark']:+.3f} / "
              f"comprar y mantener {s['max_drawdown_buy_hold']:+.3f} | Sharpe regla {s['sharpe_rule_typical']:.2f} vs "
              f"comprar y mantener {s['sharpe_buy_hold']:.2f}")
    print(f"\nCOMBINADO ({pooled['n_windows']} ventanas, {pooled['n_hours']} h): media/ventana "
          f"{pooled['mean_window_typical']:+.5f}, t {tP:+.2f}, HAC {pooled['hac_hourly_typical']:+.2f}; "
          f"bruto t {pooled['t_windows_gross']:+.2f}; conservative suma {pooled['sum_conservative']:+.4f} "
          f"(t {pooled['t_windows_conservative']:+.2f})")
    print(f"  tramos: {', '.join(f'{x:+.3f}' for x in block_sums)} -> {pooled['blocks_positive']}/5 > 0")
    print(f"  criterios: {crit}")
    print(f"\nCorrelación del lift neto por ventana:\n{corr}")
    print(f"\nReality Check (informativo, {len(common)} horas comunes): {rc}")
    print(f"\nHipótesis nuevas {hyp_new}; acumulado {HYP_BEFORE + hyp_new}; K = {K_AFTER}")
    print(f"\nESCENARIO: {scen}")


def causality_check_r2(df: pd.DataFrame, first: int, n_checks: int) -> list[dict]:
    """La verificación de EXP-013 (truncar y perturbar), sólo para R2."""
    return causality_check(df, first, n_checks, seed=14, rules=(R2,))


if __name__ == "__main__":
    main()
