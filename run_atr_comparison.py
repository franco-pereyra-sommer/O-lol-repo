"""
Comparación pareada de las salidas TP/SL por ATR (V1-V4) contra el baseline de TP/SL fijos (B0) (EXP-010).

    python run_atr_comparison.py --b0 results/exp010/b0 --v results/exp010/v1 results/exp010/v2 \
        results/exp010/v3 results/exp010/v4 --exp002-old results/exp005/exp002 \
        --exp001 results/exp005/exp001 --a1 results/exp008/regime --s results/exp009/structured \
        --out results/exp010/comparison.json

Todo sale de `wf_summary.csv`, `wf_aggregate.json` y `oos_series.npz` de cada corrida.
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
NAMES = {"v1": "V1 2/1", "v2": "V2 3/1", "v3": "V3 3/2", "v4": "V4 4/2"}
OUTCOMES = ("TP_FIRST", "SL_FIRST", "NONE", "AMBIGUOUS")
T_REL = 2.55          # Bonferroni 8 comparaciones, 89 g.l. (fijado antes de correr)


def exit_table(z: dict, scenario: str = "typical") -> dict:
    cov = z["covered"]
    tot = float(z["cnt"][cov].sum())
    res = {"trades": int(tot)}
    for nm in OUTCOMES:
        c = float(z[f"x_cnt_{nm}"][cov].sum())
        s = float(z[f"x_sum_{nm}_{scenario}"][cov].sum())
        res[nm] = {"n": int(c), "pct": c / tot if tot else float("nan"),
                   "mean_net": s / c if c else float("nan"), "contribution": s / tot if tot else float("nan")}
    res["mean_tp_pct"] = float(z["tp_frac_sum"][cov].sum() / tot)
    res["mean_sl_pct"] = float(z["sl_frac_sum"][cov].sum() / tot)
    res["mean_hold_bars"] = float(z["hold_sum"][cov].sum() / tot)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--b0", required=True)
    ap.add_argument("--v", nargs=4, required=True)
    ap.add_argument("--exp002-old", default=None)
    ap.add_argument("--exp001", default=None)
    ap.add_argument("--a1", default=None)
    ap.add_argument("--s", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--boot", type=int, default=1000)
    a = ap.parse_args()
    pd.set_option("display.width", 250)
    arms = {"B0": a.b0, **{NAMES[f"v{i + 1}"]: p for i, p in enumerate(a.v)}}
    data = {(arm, s): load(find(base, s)) for arm, base in arms.items() for s in SIDES}
    out: dict = {}

    if a.exp002_old:
        print("=" * 100)
        print("Regresión: B0 (código nuevo) vs EXP-002 (código anterior), columnas numéricas de wf_summary.csv")
        out["regression"] = {}
        for s in SIDES:
            new, old = data[("B0", s)][0], load(find(a.exp002_old, s))[0]
            cols = [c for c in old.columns if c in new.columns and old[c].dtype.kind in "fi"
                    and not c.startswith("n_att") and c not in ("n_discarded_duplicate",)]
            diff = max(float(np.nanmax(np.abs(new[c].to_numpy(float) - old[c].to_numpy(float)))) for c in cols)
            same = all(np.array_equal(new[c].to_numpy(float), old[c].to_numpy(float), equal_nan=True) for c in cols)
            out["regression"][s] = {"identical": bool(same), "max_abs_diff": diff, "columns": len(cols)}
            print(f"  {s}: {len(cols)} columnas, idénticas = {same}, diferencia máxima = {diff:.3g}")

    rows = {f"{arm}|{s}": side_metrics(*data[(arm, s)]) for arm in arms for s in SIDES}
    print("=" * 100)
    print("Métricas por variante (costos typical; conservative donde se indica)")
    df = pd.DataFrame(rows)
    print(df.to_string(float_format=lambda v: f"{v:.5f}"))
    out["metrics"] = rows

    print("\nComparación pareada (variante - B0), mismos folds. Umbral R1: t >= %.2f, HAC >= 2, t conservative >= 2" % T_REL)
    out["paired"] = {}
    per_fold = {}
    for arm in list(arms)[1:]:
        for s in SIDES:
            sa, _, za = data[("B0", s)]
            sb, _, zb = data[(arm, s)]
            cov = za["covered"] & zb["covered"]
            diff = procedure_series(zb, "typical")[cov] - procedure_series(za, "typical")[cov]
            net, lift, cons = (paired(sa, sb, za, zb, c) for c in
                               ("oos_pooled_mean_net", "oos_pooled_lift_net", "oos_pooled_mean_net_conservative"))
            hac = newey_west_t(diff, 3 * H)
            p = reality_check(diff[:, None], n_boot=a.boot, mean_block=3 * H, seed=0)["p_value"]
            r1 = bool(net["t_paired_folds"] >= T_REL and hac >= 2 and cons["t_paired_folds"] >= 2)
            out["paired"][f"{arm}|{s}"] = {"net": net, "lift": lift, "conservative": cons, "hac_diff": hac,
                                           "boot_p": p, "R1": r1}
            per_fold[f"{arm}|{s}|net"] = sb["oos_pooled_mean_net"].to_numpy()
            per_fold[f"{arm}|{s}|lift"] = sb["oos_pooled_lift_net"].to_numpy()
            print(f"  {arm} {s:<5}: dif. media por fold {net['mean_diff']:+.5f} (t {net['t_paired_folds']:.2f}, "
                  f"n={net['n_folds']}); lift t {lift['t_paired_folds']:.2f}; cons. dif. {cons['mean_diff']:+.5f} "
                  f"(t {cons['t_paired_folds']:.2f}); HAC dif. {hac:.2f}; bootstrap p(V>B0) {p:.3f} -> R1 {'SÍ' if r1 else 'NO'}")
    for s in SIDES:
        per_fold[f"B0|{s}|net"] = data[("B0", s)][0]["oos_pooled_mean_net"].to_numpy()
        per_fold[f"B0|{s}|lift"] = data[("B0", s)][0]["oos_pooled_lift_net"].to_numpy()
    pf = pd.DataFrame({"fold": data[("B0", "LONG")][0]["fold"], "val_start": data[("B0", "LONG")][0]["val_start"], **per_fold})
    if a.out:
        pf.to_csv(Path(a.out).with_name("per_fold.csv"), index=False)

    print("\nMotivo de salida de las operaciones OOS (todas las condiciones seleccionadas, costos typical)")
    out["exits"] = {}
    print(f"{'variante':<9}{'lado':<6}{'operac.':>9} | " + " | ".join(f"{nm:^30}" for nm in OUTCOMES) +
          " | TP% SL% hold")
    print(f"{'':<24} | " + " | ".join(f"{'n   %    medio   contrib.':^30}" for _ in OUTCOMES))
    for arm in arms:
        for s in SIDES:
            t = exit_table(data[(arm, s)][2])
            out["exits"][f"{arm}|{s}"] = t
            cells = " | ".join(f"{t[nm]['n']:>7} {t[nm]['pct'] * 100:5.1f}% {t[nm]['mean_net'] * 100:+7.3f}% {t[nm]['contribution'] * 100:+7.3f}%"
                               for nm in OUTCOMES)
            print(f"{arm:<9}{s:<6}{t['trades']:>9} | {cells} | {t['mean_tp_pct'] * 100:.2f} {t['mean_sl_pct'] * 100:.2f} {t['mean_hold_bars']:.1f}")

    print("\nReality Check (bloque 300, 1.000 remuestreos), universo K = 16")
    uni = {}
    if a.exp001:
        for s in SIDES:
            uni[f"EXP001|{s}"] = load(find(a.exp001, s))[2]
    for s in SIDES:
        uni[f"B0(EXP002)|{s}"] = data[("B0", s)][2]
        if a.a1:
            uni[f"EXP008|{s}"] = load(find(a.a1, s))[2]
        if a.s:
            uni[f"EXP009|{s}"] = load(find(a.s, s))[2]
    for arm in list(arms)[1:]:
        for s in SIDES:
            uni[f"{arm}|{s}"] = data[(arm, s)][2]
    idx = np.flatnonzero(np.all([v["covered"] for v in uni.values()], axis=0))
    print(f"  K = {len(uni)}, T = {len(idx)}")
    out["RC"] = []
    for sc in ("typical", "conservative"):
        for bm in ("zero", "lift"):
            F = np.column_stack([procedure_series(v, sc, bm)[idx] for v in uni.values()])
            rc = reality_check(F, n_boot=a.boot, mean_block=300, seed=0)
            ind = {n: reality_check(F[:, [k]], n_boot=a.boot, mean_block=300, seed=0)["p_value"]
                   for k, n in enumerate(uni)}
            vs = {n: q for n, q in ind.items() if n.startswith("V")}
            out["RC"].append({"scenario": sc, "benchmark": bm, "K": len(uni), "T": int(len(idx)),
                              "rc_p": rc["p_value"], "best": list(uni)[rc["best"]], "individual_p": ind})
            print(f"  {sc:<12} {bm:<5} RC p = {rc['p_value']:.3f} mejor = {list(uni)[rc['best']]:<14} | menores p individuales de V: "
                  + " ".join(f"{n}={q:.2f}" for n, q in sorted(vs.items(), key=lambda kv: kv[1])[:4]))

    # --- clasificación en casos A-D (reglas fijadas antes de correr)
    rc_typ_zero = next(r for r in out["RC"] if r["scenario"] == "typical" and r["benchmark"] == "zero")["rc_p"]
    rc_typ_lift = next(r for r in out["RC"] if r["scenario"] == "typical" and r["benchmark"] == "lift")["rc_p"]
    print("\nReglas de decisión:")
    cases = []
    r1_any = False
    pos_any = False
    d_any = False
    out["R2"] = {}
    for arm in list(arms)[1:]:
        for s in SIDES:
            m = rows[f"{arm}|{s}"]
            r1 = out["paired"][f"{arm}|{s}"]["R1"]
            net_pos = (m["oos_pooled_mean_net"] or -1) > 0
            cons_pos = (m["oos_pooled_mean_net_conservative"] or -1) > 0
            stab = m["t_folds_net"] >= 3 and m["t_folds_lift"] >= 3
            hac = m["hac_t_3H_net"] >= 2
            ent = m["oos_entries"] >= 100
            rc_ok = min(rc_typ_zero, rc_typ_lift) < 0.05
            d = bool(net_pos and cons_pos and stab and hac and ent and rc_ok and r1)
            c = bool(net_pos and m["t_folds_net"] >= 2)
            out["R2"][f"{arm}|{s}"] = {"R1": r1, "net>0": net_pos, "cons>0": cons_pos, "t_folds>=3 (net,lift)": bool(stab),
                                       "HAC>=2": bool(hac), "entries>=100": ent, "RC<0.05": rc_ok, "D": d, "C-like": c}
            r1_any |= r1
            pos_any |= (net_pos and m["t_folds_net"] >= 2)
            d_any |= d
            print(f"  {arm} {s:<5}: R1={r1} | neto>0={net_pos} (cons>0={cons_pos}) | t folds net {m['t_folds_net']:+.2f} lift {m['t_folds_lift']:+.2f} "
                  f"| HAC {m['hac_t_3H_net']:+.2f} | -> {'D' if d else ('C?' if c else '-')}")
    verdict = ("D (evidencia fuerte: DETENERSE y mostrar al usuario)" if d_any else
               "C (mejora fuerte no robusta)" if pos_any else
               "B (mejora relativa, retorno OOS agrupado <= 0)" if r1_any else "A (negativo)")
    out["verdict"] = verdict
    print(f"\nCASO: {verdict}")
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
