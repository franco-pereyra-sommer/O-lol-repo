"""
Comparación pareada baseline (A) vs regime-aware (B) con la MISMA metodología (EXP-008).

    python run_regime_comparison.py --a results/exp005/exp002 --b results/exp008/regime \
        --exp001 results/exp005/exp001 --out results/exp008/comparison.json

Cada carpeta contiene `grid_*/wf_*_{LONG,SHORT}_*` con `wf_summary.csv`, `wf_aggregate.json` y
`oos_series.npz`. Todo sale de resúmenes y series ya guardadas.
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

from trading_research.multiple_testing import (bonferroni_t_threshold, newey_west_t,
                                               procedure_series, reality_check)
from trading_research.walk_forward import fold_level_t

H = 100


def find(base: str, side: str) -> Path:
    c = sorted(glob.glob(f"{base}/*/wf_*_{side}_*"))
    if len(c) != 1:
        raise SystemExit(f"Se esperaba una carpeta {side} en {base}, hay {len(c)}: {c}")
    return Path(c[0])


def load(path: Path):
    s = pd.read_csv(path / "wf_summary.csv")
    ag = json.loads((path / "wf_aggregate.json").read_text())["aggregate"]
    z = np.load(path / "oos_series.npz")
    return s, ag, {k: z[k] for k in z.files}


def side_metrics(s: pd.DataFrame, ag: dict, z: dict, scenario: str = "typical", h: int = H) -> dict:
    cov = z["covered"]
    x = procedure_series(z, scenario)[cov]
    xl = procedure_series(z, scenario, "lift")[cov]
    net = s["oos_pooled_mean_net"].dropna()
    lift = s["oos_pooled_lift_net"].dropna()
    cons = s["oos_pooled_mean_net_conservative"].dropna()
    return {
        "folds": int(len(s)), "folds_with_trades": int(len(net)),
        "oos_pooled_mean_net": ag["oos_pooled_mean_net_all_folds"],
        "oos_pooled_mean_net_conservative": ag.get("oos_pooled_mean_net_all_folds_conservative"),
        "mean_fold_net": float(net.mean()), "mean_fold_lift": float(lift.mean()),
        "t_folds_net": fold_level_t(s, "oos_pooled_mean_net"),
        "t_folds_lift": fold_level_t(s, "oos_pooled_lift_net"),
        "hac_t_3H_net": newey_west_t(x, 3 * h), "hac_t_3H_lift": newey_west_t(xl, 3 * h),
        "folds_net_gt0": int((net > 0).sum()), "folds_beat_base": int((lift > 0).sum()),
        "folds_net_gt0_conservative": int((cons > 0).sum()),
        "oos_entries": int(s["oos_entries"].sum()),
        "selected_in_train_total": int(s["selected_in_train"].sum()),
        "passed_val_total": int(s["passed_val"].sum()),
        "mean_frac_cond_net_gt0": float(s["oos_frac_cond_net_gt0"].mean()),
        "mean_frac_cond_beat_base": float(s["oos_frac_cond_beat_base"].mean()),
    }


def paired(sa: pd.DataFrame, sb: pd.DataFrame, za: dict, zb: dict, col: str) -> dict:
    assert (sa["val_start"] == sb["val_start"]).all(), "los folds no coinciden"
    d = (sb[col] - sa[col]).dropna()
    t = float(d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))) if len(d) > 2 and d.std() > 0 else float("nan")
    return {"n_folds": int(len(d)), "mean_diff": float(d.mean()), "t_paired_folds": t}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--exp001", default=None)
    p.add_argument("--out", default=None)
    p.add_argument("--boot", type=int, default=1000)
    a = p.parse_args()
    out: dict = {}
    data = {}
    for side in ("LONG", "SHORT"):
        data[("A", side)] = load(find(a.a, side))
        data[("B", side)] = load(find(a.b, side))

    print("=" * 78)
    print("Métricas por variante (costos typical; conservative donde se indica)")
    rows = {}
    for side in ("LONG", "SHORT"):
        for arm in ("A", "B"):
            s, ag, z = data[(arm, side)]
            rows[f"{arm}_{side}"] = side_metrics(s, ag, z)
    df = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(df.to_string(float_format=lambda v: f"{v:.5f}"))
    out["metrics"] = rows

    df_ = bonferroni_t_threshold(2, 89)
    print(f"\nUmbral Bonferroni para 2 comparaciones, 89 g.l.: {df_:.2f}; para K=6: "
          f"{bonferroni_t_threshold(6, 89):.2f}")
    print("\nR1 — comparación pareada B - A (mismos folds):")
    out["paired"] = {}
    for side in ("LONG", "SHORT"):
        sa, _, za = data[("A", side)]
        sb, _, zb = data[("B", side)]
        cov = za["covered"] & zb["covered"]
        diff = (procedure_series(zb, "typical")[cov] - procedure_series(za, "typical")[cov])
        diff_l = (procedure_series(zb, "typical", "lift")[cov] - procedure_series(za, "typical", "lift")[cov])
        r = {"net": paired(sa, sb, za, zb, "oos_pooled_mean_net"),
             "lift": paired(sa, sb, za, zb, "oos_pooled_lift_net"),
             "hac_t_3H_diff_net": newey_west_t(diff, 3 * H),
             "hac_t_3H_diff_lift": newey_west_t(diff_l, 3 * H),
             "mean_diff_per_bar": float(diff.mean()),
             "boot_p_B_gt_A": reality_check(diff[:, None], n_boot=a.boot, mean_block=3 * H, seed=0)["p_value"]}
        r1 = r["net"]["t_paired_folds"] >= 2.5 and r["hac_t_3H_diff_net"] >= 2.0
        r["R1_cumple"] = bool(r1)
        out["paired"][side] = r
        print(f"  {side}: dif. media por fold neto {r['net']['mean_diff']:+.5f} "
              f"(t pareado {r['net']['t_paired_folds']:.2f}, n={r['net']['n_folds']}); lift "
              f"t pareado {r['lift']['t_paired_folds']:.2f}; HAC(3H) dif. {r['hac_t_3H_diff_net']:.2f}; "
              f"bootstrap p(B>A) = {r['boot_p_B_gt_A']:.3f}  ->  R1 {'SÍ' if r1 else 'NO'}")

    print("\nR2 — candidato absoluto (regla 4) para B:")
    out["R2"] = {}
    for side in ("LONG", "SHORT"):
        m = rows[f"B_{side}"]
        ok = (m["t_folds_net"] >= 3 and m["t_folds_lift"] >= 3
              and (m["oos_pooled_mean_net_conservative"] or -1) > 0 and m["hac_t_3H_net"] >= 2
              and m["oos_entries"] >= 100)
        out["R2"][side] = {"cumple_sin_RC": bool(ok)}
        print(f"  {side}: t folds neto {m['t_folds_net']:.2f}, lift {m['t_folds_lift']:.2f}, "
              f"conservative {m['oos_pooled_mean_net_conservative']:+.5f}, HAC {m['hac_t_3H_net']:.2f} -> "
              f"{'cumple (falta RC)' if ok else 'NO cumple'}")

    # Reality Check
    print("\nReality Check (bloque 300, 1.000 remuestreos)")
    variants = {f"A_{s}": data[("A", s)][2] for s in ("LONG", "SHORT")}
    variants.update({f"B_{s}": data[("B", s)][2] for s in ("LONG", "SHORT")})
    k6 = dict(variants)
    if a.exp001:
        for s in ("LONG", "SHORT"):
            k6[f"EXP001_{s}"] = load(find(a.exp001, s))[2]
    out["RC"] = []
    for label, vs in (("K=6 (primario)" if a.exp001 else "K=4", k6), ("K=4 (sólo EXP-002 A y B)", variants)):
        cov = np.all([v["covered"] for v in vs.values()], axis=0)
        idx = np.flatnonzero(cov)
        for sc in ("typical", "conservative"):
            for bm in ("zero", "lift"):
                F = np.column_stack([procedure_series(v, sc, bm)[idx] for v in vs.values()])
                rc = reality_check(F, n_boot=a.boot, mean_block=300, seed=0)
                ind = {n: reality_check(F[:, [k]], n_boot=a.boot, mean_block=300, seed=0)["p_value"]
                       for k, n in enumerate(vs)}
                row = {"universe": label, "T": int(len(idx)), "scenario": sc, "benchmark": bm,
                       "rc_p": rc["p_value"], "best": list(vs)[rc["best"]], "individual_p": ind}
                out["RC"].append(row)
                print(f"  {label:<26} T={len(idx):>6} {sc:<12} {bm:<5} RC p = {rc['p_value']:.3f} "
                      f"mejor = {row['best']:<11} | " + " ".join(f"{n}={q:.2f}" for n, q in ind.items()))
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
