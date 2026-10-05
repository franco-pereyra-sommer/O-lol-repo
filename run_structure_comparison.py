"""
Comparación pareada de la búsqueda estructurada (S) contra la aleatoria con las mismas features de
régimen (A1, primaria) y sin ellas (A0, secundaria) (EXP-009).

    python run_structure_comparison.py --s results/exp009/structured --a1 results/exp008/regime \
        --a0 results/exp005/exp002 --exp001 results/exp005/exp001 --out results/exp009/comparison.json

Todo sale de resúmenes (`wf_summary.csv`, `wf_aggregate.json`), `oos_series.npz` y los JSON de PBO.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from run_regime_comparison import find, load, paired, side_metrics
from trading_research.multiple_testing import (bonferroni_t_threshold, newey_west_t,
                                               procedure_series, reality_check)

H = 100
SIDES = ("LONG", "SHORT")


def pbo_row(path: str) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--s", required=True)
    ap.add_argument("--a1", required=True)
    ap.add_argument("--a0", required=True)
    ap.add_argument("--exp001", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--boot", type=int, default=1000)
    a = ap.parse_args()
    pd.set_option("display.width", 220)
    arms = {"A0": a.a0, "A1": a.a1, "S": a.s}
    data = {(arm, s): load(find(base, s)) for arm, base in arms.items() for s in SIDES}
    out: dict = {}

    print("=" * 90)
    print("Métricas por procedimiento (costos typical; conservative donde se indica)")
    rows = {f"{arm}_{s}": side_metrics(*data[(arm, s)]) for arm in arms for s in SIDES}
    for s in SIDES:                                    # presupuesto y descartes (sólo S los registra)
        sm = data[("S", s)][0]
        rows[f"S_{s}"]["candidatos_intentos_total"] = int(sm["n_attempts"].sum())
        rows[f"S_{s}"]["descartados_repetidos_total"] = int(sm["n_discarded_duplicate"].sum())
        rows[f"S_{s}"]["evaluados_total"] = int(sm["n_evaluated"].sum())
    df = pd.DataFrame(rows)
    print(df.to_string(float_format=lambda v: f"{v:.5f}"))
    out["metrics"] = rows
    print("\nEvaluados por fold y lado (S):",
          {s: sorted(set(data[("S", s)][0]["n_evaluated"])) for s in SIDES})

    print(f"\nBonferroni (89 g.l.): 4 comparaciones = {bonferroni_t_threshold(4, 89):.2f}; "
          f"K=8 = {bonferroni_t_threshold(8, 89):.2f}")
    out["paired"] = {}
    r1 = {}
    print("\nR1 / comparación pareada S - baseline (mismos folds):")
    for base in ("A1", "A0"):
        for s in SIDES:
            sa, _, za = data[(base, s)]
            sb, _, zb = data[("S", s)]
            cov = za["covered"] & zb["covered"]
            diff = procedure_series(zb, "typical")[cov] - procedure_series(za, "typical")[cov]
            res = {"net": paired(sa, sb, za, zb, "oos_pooled_mean_net"),
                   "lift": paired(sa, sb, za, zb, "oos_pooled_lift_net"),
                   "conservative": paired(sa, sb, za, zb, "oos_pooled_mean_net_conservative"),
                   "hac_t_3H_diff_net": newey_west_t(diff, 3 * H),
                   "boot_p_S_gt_base": reality_check(diff[:, None], n_boot=a.boot, mean_block=3 * H,
                                                     seed=0)["p_value"]}
            ok = res["net"]["t_paired_folds"] >= 2.5 and res["hac_t_3H_diff_net"] >= 2.0
            res["R1_cumple"] = bool(ok)
            out["paired"][f"S_vs_{base}_{s}"] = res
            r1[(base, s)] = ok
            print(f"  S vs {base} {s}: dif. media por fold neto {res['net']['mean_diff']:+.5f} "
                  f"(t pareado {res['net']['t_paired_folds']:.2f}, n={res['net']['n_folds']}); lift t "
                  f"{res['lift']['t_paired_folds']:.2f}; conservative dif. {res['conservative']['mean_diff']:+.5f} "
                  f"(t {res['conservative']['t_paired_folds']:.2f}); HAC dif. {res['hac_t_3H_diff_net']:.2f}; "
                  f"bootstrap p(S>base) = {res['boot_p_S_gt_base']:.3f} -> R1 {'SÍ' if ok else 'NO'}")

    print("\nR2 — candidato absoluto (regla 4, K=8) para S:")
    out["R2"] = {}
    for s in SIDES:
        m = rows[f"S_{s}"]
        ok = (m["t_folds_net"] >= 3 and m["t_folds_lift"] >= 3
              and (m["oos_pooled_mean_net_conservative"] or -1) > 0 and m["hac_t_3H_net"] >= 2
              and m["oos_entries"] >= 100)
        out["R2"][s] = {"cumple_sin_RC": bool(ok)}
        print(f"  {s}: t folds neto {m['t_folds_net']:.2f}, lift {m['t_folds_lift']:.2f}, conservative "
              f"{m['oos_pooled_mean_net_conservative']:+.5f}, HAC {m['hac_t_3H_net']:.2f} -> "
              f"{'cumple (falta RC)' if ok else 'NO cumple'}")

    print("\nReality Check (bloque 300, 1.000 remuestreos)")
    variants = {f"{arm}_{s}": data[(arm, s)][2] for arm in arms for s in SIDES}
    k8 = dict(variants)
    if a.exp001:
        for s in SIDES:
            k8[f"EXP001_{s}"] = load(find(a.exp001, s))[2]
    out["RC"] = []
    for label, vs in (("K=8 (primario)" if a.exp001 else "K=6", k8), ("K=6 (sin EXP-001)", variants)):
        idx = np.flatnonzero(np.all([v["covered"] for v in vs.values()], axis=0))
        for sc in ("typical", "conservative"):
            for bm in ("zero", "lift"):
                F = np.column_stack([procedure_series(v, sc, bm)[idx] for v in vs.values()])
                rc = reality_check(F, n_boot=a.boot, mean_block=300, seed=0)
                ind = {n: reality_check(F[:, [k]], n_boot=a.boot, mean_block=300, seed=0)["p_value"]
                       for k, n in enumerate(vs)}
                out["RC"].append({"universe": label, "T": int(len(idx)), "scenario": sc, "benchmark": bm,
                                  "rc_p": rc["p_value"], "best": list(vs)[rc["best"]], "individual_p": ind})
                print(f"  {label:<18} T={len(idx):>6} {sc:<12} {bm:<5} RC p = {rc['p_value']:.3f} mejor = "
                      f"{list(vs)[rc['best']]:<11} | S_LONG={ind['S_LONG']:.2f} S_SHORT={ind['S_SHORT']:.2f} "
                      f"A1_LONG={ind['A1_LONG']:.2f} A1_SHORT={ind['A1_SHORT']:.2f}")

    print("\nPBO del proceso de selección (7.500 condiciones, 16 bloques; semillas 42 / 7)")
    paths = {"A0": ("results/exp004/pbo.json", "results/exp004/pbo_seed7.json"),
             "A1": ("results/exp008/pbo_regime_seed42.json", "results/exp008/pbo_regime_seed7.json"),
             "S": ("results/exp009/pbo_structured_seed42.json", "results/exp009/pbo_structured_seed7.json")}
    out["PBO"] = {}
    print(f"{'procedimiento':<14}{'PBO':>14}{'mejor IN':>18}{'mejor OUT':>18}{'IN-OUT':>16}{'P(pérd. OUT)':>16}")
    for arm, ps in paths.items():
        for s in SIDES:
            vals = [pbo_row(p) for p in ps]
            if any(v is None or s not in v for v in vals):
                continue
            v = [x[s] for x in vals]
            f = lambda k, mult=1.0: " / ".join(f"{e[k] * mult:.2f}" for e in v)   # noqa: E731
            gap = " / ".join(f"{(e['mean_is_best'] - e['mean_oos_best']) * 100:.2f}" for e in v)
            print(f"{arm + ' ' + s:<14}{f('pbo'):>14}{f('mean_is_best', 100):>18}{f('mean_oos_best', 100):>18}"
                  f"{gap:>16}{f('prob_oos_loss'):>16}")
            out["PBO"][f"{arm}_{s}"] = {"pbo": [e["pbo"] for e in v], "is": [e["mean_is_best"] for e in v],
                                        "oos": [e["mean_oos_best"] for e in v],
                                        "frac_all_dev_mean_gt0": [e["frac_all_dev_mean_gt0"] for e in v]}
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
