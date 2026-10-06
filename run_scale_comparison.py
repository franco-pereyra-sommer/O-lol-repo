"""
Comparación de las escalas de objetivo (EXP-012): B0 (TP 5 % / SL 3 % / H 100) contra V1-V3 (k = 2, 3, 4).

    python run_scale_comparison.py --csv "D:\\O lol\\Guardado de datos\\BTCUSDT_binance_1h.csv" \
        --b0 results/exp012/b0 --v results/exp012/v1 results/exp012/v2 results/exp012/v3 \
        --exp002-old results/exp005/exp002 --exp001 results/exp005/exp001 --a1 results/exp008/regime \
        --s results/exp009/structured --v10 results/exp010/v1 results/exp010/v2 results/exp010/v3 results/exp010/v4 \
        --h4 results/exp011/h4 --out results/exp012/comparison.json

La métrica de predictibilidad es el LIFT (condición menos línea base de la misma ventana y geometría), no el
retorno absoluto: a horizontes largos la línea base sin condición ya gana (LONG) o pierde (SHORT) por la deriva de
BTC. Las reglas P1-P6 y los escenarios A-D son los pre-registrados en RESEARCH_LOG.md (EXP-012).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from run_atr_comparison import exit_table
from run_regime_comparison import find, load, side_metrics
from run_timeframe_comparison import fold_of_bars, per_condition_series, to_hour_grid
from trading_research.config import ResearchConfig
from trading_research.data import load_data
from trading_research.multiple_testing import (bonferroni_t_threshold, newey_west_t, procedure_series,
                                               reality_check)

SIDES = ("LONG", "SHORT")
VAR = {"B0": (100, 1), "V1": (200, 2), "V2": (300, 3), "V3": (400, 4)}     # H (barras = horas), k
RANDOM_WALK_TP_SHARE = 0.375


def t_stat(x) -> float:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 and x.std(ddof=1) > 0 else float("nan")


def is_empty(summ: pd.DataFrame) -> bool:
    """Variante/lado sin ninguna operación OOS (ninguna condición seleccionada en ningún fold)."""
    return int(summ["oos_entries"].sum()) == 0


def fold_blocks(idx: pd.DatetimeIndex, summ: pd.DataFrame) -> list[np.ndarray]:
    f = fold_of_bars(idx, summ)
    return [np.flatnonzero(f == i) for i in range(len(summ))]


def fold_stats(z: dict, summ: pd.DataFrame, idx: pd.DatetimeIndex) -> dict:
    """Métricas por fold propio, agrupadas por operación (todas las condiciones seleccionadas)."""
    cnt = z["cnt"]
    base_g = np.nan_to_num(z["base_gross"])
    base_n = np.nan_to_num(z["base_typical"])
    base_c = np.nan_to_num(z["base_conservative"])
    gl, nl, cl = z["gross_sum"] - cnt * base_g, z["sum_typical"] - cnt * base_n, z["sum_conservative"] - cnt * base_c
    rows = []
    for b in fold_blocks(idx, summ):
        n = cnt[b].sum()
        if n <= 0:
            rows.append({k: np.nan for k in ("n", "gross", "net", "net_cons", "gross_lift", "net_lift", "tp_share")})
            continue
        tp, sl = z["x_cnt_TP_FIRST"][b].sum(), z["x_cnt_SL_FIRST"][b].sum()
        rows.append({"n": n, "gross": z["gross_sum"][b].sum() / n, "net": z["sum_typical"][b].sum() / n,
                     "net_cons": z["sum_conservative"][b].sum() / n, "gross_lift": gl[b].sum() / n,
                     "net_lift": nl[b].sum() / n, "tp_share": tp / (tp + sl) if tp + sl > 0 else np.nan})
    df = pd.DataFrame(rows)
    df["tp_lift"] = (summ["oos_pooled_P_TP"] - summ["base_val_P_TP"]).to_numpy()
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--b0", required=True)
    ap.add_argument("--v", nargs=3, required=True)
    ap.add_argument("--exp002-old", default=None)
    ap.add_argument("--exp001", default=None)
    ap.add_argument("--a1", default=None)
    ap.add_argument("--s", default=None)
    ap.add_argument("--v10", nargs=4, default=None)
    ap.add_argument("--h4", default=None)
    ap.add_argument("--pbo-dir", default="results/exp012")
    ap.add_argument("--out", default=None)
    ap.add_argument("--boot", type=int, default=1000)
    a = ap.parse_args()
    pd.set_option("display.width", 250)
    base = dict(DATA_SOURCE="csv", CSV_PATH=a.csv)
    df1 = load_data(ResearchConfig(TIMEFRAME="1h", **base))
    idx = df1.index
    dirs = {"B0": a.b0, "V1": a.v[0], "V2": a.v[1], "V3": a.v[2]}
    runs = {(nm, s): load(find(d, s)) for nm, d in dirs.items() for s in SIDES}
    out: dict = {}

    if a.exp002_old:
        print("=" * 120)
        print("Regresión: B0 re-corrido con el código final vs EXP-002")
        out["regression"] = {}
        for s in SIDES:
            new, old = runs[("B0", s)][0], load(find(a.exp002_old, s))[0]
            cols = [c for c in old.columns if c in new.columns and old[c].dtype.kind in "fi"]
            same = all(np.array_equal(new[c].to_numpy(float), old[c].to_numpy(float), equal_nan=True) for c in cols)
            out["regression"][s] = {"identical": bool(same), "columns": len(cols)}
            print(f"  {s}: {len(cols)} columnas numéricas idénticas = {same}")
            if not same:
                raise SystemExit("B0 no reproduce EXP-002: se detiene el experimento.")

    # ------------------------------------------------------------------ por fold propio
    FS = {k: fold_stats(z, summ, idx) for k, (summ, ag, z) in runs.items()}
    thr_abs = {nm: max(3.0, bonferroni_t_threshold(24, len(runs[(nm, "LONG")][0]) - 1)) for nm in VAR}
    thr_rel = {nm: max(2.5, bonferroni_t_threshold(6, len(runs[(nm, "LONG")][0]) - 1)) for nm in VAR}
    out["thresholds"] = {"absolute": thr_abs, "relative": thr_rel}
    rows, series_hac = {}, {}
    for (nm, s), (summ, ag, z) in runs.items():
        H, k = VAR[nm]
        fs = FS[(nm, s)]
        cov = z["covered"]
        if is_empty(summ):
            rows[f"{nm}|{s}"] = {"folds": int(len(summ)), "folds_with_trades": 0, "oos_entries": 0,
                                 "selected_in_train_total": int(summ["selected_in_train"].sum()), "empty": True}
            continue
        m = side_metrics(summ, ag, z, h=H)
        g_ser, gl_ser = procedure_series(z, "gross")[cov], procedure_series(z, "gross", "lift")[cov]
        n_ser = procedure_series(z, "typical")[cov]
        m.update({
            "gross_pooled": float(z["gross_sum"][cov].sum() / z["cnt"][cov].sum()),
            "mean_fold_gross": float(fs["gross"].mean()), "mean_fold_gross_lift": float(fs["gross_lift"].mean()),
            "t_folds_gross": t_stat(fs["gross"]), "t_folds_gross_lift": t_stat(fs["gross_lift"]),
            "t_folds_net_lift": t_stat(fs["net_lift"]),
            "hac_gross": newey_west_t(g_ser, 3 * H), "hac_gross_lift": newey_west_t(gl_ser, 3 * H),
            "hac_net": newey_west_t(n_ser, 3 * H), "tp_lift_mean": float(fs["tp_lift"].mean()),
            "t_folds_tp_lift": t_stat(fs["tp_lift"]), "tp_share_pooled": float(
                z["x_cnt_TP_FIRST"][cov].sum() / (z["x_cnt_TP_FIRST"][cov].sum() + z["x_cnt_SL_FIRST"][cov].sum())),
            "tp_share_vs_375_t_folds": t_stat(fs["tp_share"] - RANDOM_WALK_TP_SHARE)})
        rows[f"{nm}|{s}"] = m
        series_hac[(nm, s)] = gl_ser
    out["metrics"] = rows
    print("=" * 120)
    print("Métricas por variante y lado, con sus propios folds (retorno agrupado por operación; costos typical)")
    keys = ["folds", "folds_with_trades", "oos_entries", "selected_in_train_total", "gross_pooled", "oos_pooled_mean_net",
            "oos_pooled_mean_net_conservative", "mean_fold_gross", "mean_fold_net", "mean_fold_gross_lift", "mean_fold_lift",
            "t_folds_gross", "t_folds_net", "t_folds_gross_lift", "t_folds_net_lift", "hac_gross", "hac_t_3H_net",
            "hac_gross_lift", "hac_t_3H_lift", "folds_net_gt0", "folds_beat_base", "tp_share_pooled", "tp_lift_mean",
            "t_folds_tp_lift", "tp_share_vs_375_t_folds"]
    print(pd.DataFrame({k: {m: v.get(m, np.nan) for m in keys} for k, v in rows.items()}).to_string(float_format=lambda v: f"{v:.5f}"))
    fw = {k: (int(runs[(k.split("|")[0], k.split("|")[1])][0]["selected_in_train"].gt(0).sum()), v["folds"]) for k, v in rows.items()}
    print("Folds con al menos una condición seleccionada en TRAIN (de los folds totales):", fw)
    out["folds_with_selection"] = fw

    # ------------------------------------------------------------------ economía y operaciones
    print("\nOperaciones, duración y economía (por operación y por condición seleccionada y ventana de 30 días)")
    econ = {}
    for (nm, s), (summ, ag, z) in runs.items():
        H, k = VAR[nm]
        cov = z["covered"]
        if is_empty(summ):
            continue
        n = float(z["cnt"][cov].sum())
        nf = int((summ["selected_in_train"] > 0).sum())
        pc = {key: float(per_condition_series(z, summ, idx, key).sum()) / nf / k
              for key in ("cnt", "gross_sum", "sum_typical", "sum_conservative")}          # por 720 h (30 días)
        hist = z["hold_hist"]
        cdf = np.cumsum(hist) / hist.sum()
        ex = exit_table(z)
        e = {"trades": int(n), "trades_per_fold": n / len(summ), "trades_per_selected_condition": n / float(summ["selected_in_train"].sum()),
             "trades_per_condition_30d": pc["cnt"], "hours_between_entries_per_condition": 720.0 / pc["cnt"],
             "pooled_trades_per_year": n / (float(cov.sum()) / 8766.0), "pooled_trades_per_1000_bars": n / float(cov.sum()) * 1000,
             "duration_mean_h": float(z["hold_sum"][cov].sum() / n), "duration_median_h": float(np.searchsorted(cdf, 0.5) + 0),
             "gross_per_trade": float(z["gross_sum"][cov].sum() / n), "net_per_trade": float(z["sum_typical"][cov].sum() / n),
             "cost_per_trade": float((z["gross_sum"][cov].sum() - z["sum_typical"][cov].sum()) / n),
             "net_per_trade_cons": float(z["sum_conservative"][cov].sum() / n),
             "gross_30d": pc["gross_sum"], "net_30d": pc["sum_typical"], "net_30d_cons": pc["sum_conservative"],
             "cost_30d": pc["gross_sum"] - pc["sum_typical"], "exits": ex}
        econ[f"{nm}|{s}"] = e
    out["economics"] = econ
    ek = ["trades", "trades_per_fold", "trades_per_selected_condition", "trades_per_condition_30d", "hours_between_entries_per_condition",
          "pooled_trades_per_year", "duration_mean_h", "duration_median_h", "gross_per_trade", "cost_per_trade", "net_per_trade",
          "net_per_trade_cons", "gross_30d", "cost_30d", "net_30d", "net_30d_cons"]
    print(pd.DataFrame({k: {m: v[m] for m in ek} for k, v in econ.items()}).to_string(float_format=lambda v: f"{v:.5f}"))
    print("  (sin operaciones OOS, omitidos: " + ", ".join(k for k, v in rows.items() if v.get("empty")) + ")")
    print("\nMotivo de salida (typical): % de operaciones · retorno medio · contribución al retorno medio por operación")
    for k, v in econ.items():
        ex = v["exits"]
        print(f"  {k:<9} " + "  ".join(f"{nm[:2]} {ex[nm]['pct'] * 100:5.1f}% {ex[nm]['mean_net'] * 100:+6.2f}% ({ex[nm]['contribution'] * 100:+.3f})"
                                       for nm in ("TP_FIRST", "SL_FIRST", "NONE", "AMBIGUOUS")) + f" | TP/SL medios {ex['mean_tp_pct'] * 100:.0f}/{ex['mean_sl_pct'] * 100:.0f}%")

    # ------------------------------------------------------------------ pareo por calendario V_k - B0
    print("\nComparación emparejada por calendario V_k − B0 (ventanas = VALIDATION de V_k; B0 sobre las mismas horas)")
    out["paired"] = {}
    for nm in ("V1", "V2", "V3"):
        H, k = VAR[nm]
        for s in SIDES:
            sk, _, zk = runs[(nm, s)]
            zb = runs[("B0", s)][2]
            if is_empty(sk):
                print(f"  {nm} {s:<5}: sin operaciones OOS (ninguna condición seleccionada en TRAIN): comparación imposible")
                continue
            common = zk["covered"] & zb["covered"]
            blocks = [b[common[b]] for b in fold_blocks(idx, sk)]

            def block_series(z, label):
                cnt = z["cnt"]
                comp = {"gross": z["gross_sum"], "net": z["sum_typical"], "net_cons": z["sum_conservative"],
                        "gross_lift": z["gross_sum"] - cnt * np.nan_to_num(z["base_gross"]),
                        "net_lift": z["sum_typical"] - cnt * np.nan_to_num(z["base_typical"])}
                res = {c: [] for c in comp}
                res["n"] = []
                for b in blocks:
                    n = cnt[b].sum()
                    res["n"].append(n)
                    for c, arr in comp.items():
                        res[c].append(arr[b].sum() / n if n > 0 else np.nan)
                return {c: np.array(v) for c, v in res.items()}

            bk, bb = block_series(zk, nm), block_series(zb, "B0")
            res = {}
            for c in ("gross_lift", "gross", "net", "net_lift", "net_cons"):
                d = bk[c] - bb[c]
                res[c] = {"mean_diff": float(np.nanmean(d)), "t": t_stat(d), "n_blocks": int(np.isfinite(d).sum())}
            ser = lambda z, kind: procedure_series(z, "gross", kind)[common]    # noqa: E731
            diff = ser(zk, "lift") - ser(zb, "lift")
            res["hac_diff_gross_lift"] = newey_west_t(diff, 3 * H)
            res["boot_p_gross_lift"] = reality_check(diff[:, None], n_boot=a.boot, mean_block=3 * H, seed=0)["p_value"]
            ek_, eb_ = econ[f"{nm}|{s}"], econ[f"B0|{s}"]
            pt = lambda e, key: e[key] / e["trades_per_condition_30d"]    # noqa: E731
            n0, n1 = eb_["trades_per_condition_30d"], ek_["trades_per_condition_30d"]
            dec = {"d_net_30d": ek_["net_30d"] - eb_["net_30d"],
                   "turnover_effect": (n1 - n0) * pt(eb_, "net_30d"),
                   "gross_effect": n1 * (pt(ek_, "gross_30d") - pt(eb_, "gross_30d")),
                   "cost_effect": -n1 * (pt(ek_, "cost_30d") - pt(eb_, "cost_30d"))}
            dec["check_sum"] = dec["turnover_effect"] + dec["gross_effect"] + dec["cost_effect"]
            res["decomposition_net_30d"] = dec
            out["paired"][f"{nm}|{s}"] = res
            print(f"  {nm} {s:<5}: Δ lift bruto por operación {res['gross_lift']['mean_diff'] * 100:+.3f} pp (t {res['gross_lift']['t']:+.2f}, n={res['gross_lift']['n_blocks']}; "
                  f"HAC dif. {res['hac_diff_gross_lift']:+.2f}; bootstrap p(V>B0) {res['boot_p_gross_lift']:.3f}) | Δ bruto {res['gross']['mean_diff'] * 100:+.3f} (t {res['gross']['t']:+.2f}) | "
                  f"Δ neto {res['net']['mean_diff'] * 100:+.3f} (t {res['net']['t']:+.2f}) | Δ neto cons. t {res['net_cons']['t']:+.2f}")
            print(f"       descomposición Δ neto por condición·30d {dec['d_net_30d'] * 100:+.3f} pp = operaciones {dec['turnover_effect'] * 100:+.3f} + bruto {dec['gross_effect'] * 100:+.3f} + costo {dec['cost_effect'] * 100:+.3f} "
                  f"(suma {dec['check_sum'] * 100:+.3f})")

    # ------------------------------------------------------------------ Reality Check de predictibilidad (K_pred = 8)
    print("\nReality Check de PREDICTIBILIDAD: series de lift bruto de {B0,V1,V2,V3}×{LONG,SHORT} (K_pred = 8), horas comunes")
    pred_cov = np.all([runs[k][2]["covered"] for k in runs], axis=0)
    pidx = np.flatnonzero(pred_cov)
    names = [f"{nm}|{s}" for nm in VAR for s in SIDES]
    F = np.column_stack([procedure_series(runs[(nm, s)][2], "gross", "lift")[pidx] for nm in VAR for s in SIDES])
    out["RC_pred"] = []
    rc_pred_primary = {}
    for blk in (1200, 300):
        rc = reality_check(F, n_boot=a.boot, mean_block=blk, seed=0)
        ind = {n: reality_check(F[:, [j]], n_boot=a.boot, mean_block=blk, seed=0)["p_value"] for j, n in enumerate(names)}
        out["RC_pred"].append({"block": blk, "T": int(len(pidx)), "K": len(names), "rc_p": rc["p_value"], "best": names[rc["best"]], "individual_p": ind})
        print(f"  bloque {blk:>4} h ({'principal' if blk == 1200 else 'sensibilidad'}): T = {len(pidx)} h, K_pred = {len(names)}, RC p = {rc['p_value']:.3f}, mejor = {names[rc['best']]}; "
              + " ".join(f"{n}={q:.2f}" for n, q in ind.items()))
        if blk == 1200:
            rc_pred_primary = {"rc_p": rc["p_value"], "individual": ind}

    # ------------------------------------------------------------------ Reality Check K = 24 (neto)
    print("\nReality Check del protocolo existente (neto), universo K = 24, grilla horaria")
    uni = {}
    if a.exp001:
        for s in SIDES:
            uni[f"EXP001|{s}"] = load(find(a.exp001, s))[2]
    for s in SIDES:
        uni[f"EXP002(B0)|{s}"] = runs[("B0", s)][2]
        if a.a1:
            uni[f"EXP008|{s}"] = load(find(a.a1, s))[2]
        if a.s:
            uni[f"EXP009|{s}"] = load(find(a.s, s))[2]
    if a.v10:
        for i, p in enumerate(a.v10, 1):
            for s in SIDES:
                uni[f"EXP010-V{i}|{s}"] = load(find(p, s))[2]
    if a.h4:
        for s in SIDES:
            df4 = load_data(ResearchConfig(TIMEFRAME="4h", CSV_TIMEFRAME="1h", **base))
            uni[f"EXP011(4h)|{s}"] = to_hour_grid(load(find(a.h4, s))[2], df4.index, idx, 4)
    for nm in ("V1", "V2", "V3"):
        for s in SIDES:
            uni[f"EXP012-{nm}|{s}"] = runs[(nm, s)][2]
    uidx = np.flatnonzero(np.all([v["covered"] for v in uni.values()], axis=0))
    print(f"  K = {len(uni)}, T = {len(uidx)} h")
    out["RC"] = []
    for blk in (300, 1200):
        for sc in ("typical", "conservative"):
            for bm in ("zero", "lift"):
                G = np.column_stack([procedure_series(v, sc, bm)[uidx] for v in uni.values()])
                rc = reality_check(G, n_boot=a.boot, mean_block=blk, seed=0)
                ind = {n: reality_check(G[:, [j]], n_boot=a.boot, mean_block=blk, seed=0)["p_value"] for j, n in enumerate(uni)}
                new = {n: q for n, q in ind.items() if n.startswith("EXP012")}
                out["RC"].append({"block": blk, "scenario": sc, "benchmark": bm, "K": len(uni), "T": int(len(uidx)), "rc_p": rc["p_value"],
                                  "best": list(uni)[rc["best"]], "individual_p": ind})
                print(f"  bloque {blk:>4} {sc:<12} {bm:<5} RC p = {rc['p_value']:.3f} mejor = {list(uni)[rc['best']]:<16} | menor p de EXP-012: "
                      f"{min(new, key=new.get)}={min(new.values()):.2f}")

    # ------------------------------------------------------------------ PBO
    print("\nPBO (7.500 condiciones, 16 bloques; semillas 42 / 7): mejor IN, mejor OUT, brecha")
    out["PBO"] = {}
    srcs = {"B0": ("results/exp004/pbo.json", "results/exp004/pbo_seed7.json")}
    for nm, i in (("V1", 1), ("V2", 2), ("V3", 3)):
        srcs[nm] = tuple(f"{a.pbo_dir}/pbo_v{i}_seed{sd}.json" for sd in (42, 7))
    for nm, ps in srcs.items():
        for s in SIDES:
            if not all(Path(p).exists() for p in ps):
                continue
            v = [json.loads(Path(p).read_text())[s] for p in ps]
            out["PBO"][f"{nm}|{s}"] = {"pbo": [e["pbo"] for e in v], "is": [e["mean_is_best"] for e in v], "oos": [e["mean_oos_best"] for e in v]}
            print(f"  {nm} {s:<5}: PBO " + " / ".join(f"{e['pbo']:.2f}" for e in v) + " | mejor IN " + " / ".join(f"{e['mean_is_best'] * 100:+.2f}%" for e in v)
                  + " | mejor OUT " + " / ".join(f"{e['mean_oos_best'] * 100:+.2f}%" for e in v)
                  + " | P(pérdida OUT) " + " / ".join(f"{e['prob_oos_loss']:.2f}" for e in v))

    # ------------------------------------------------------------------ reglas de decisión
    print("\nReglas pre-registradas (P1-P6; escenarios A-D)")
    rc_net_ok = min(r["rc_p"] for r in out["RC"] if r["block"] == 300 and r["scenario"] == "typical") < 0.05
    ev = {}
    for nm in ("V1", "V2", "V3"):
        for s in SIDES:
            m = rows[f"{nm}|{s}"]
            if m.get("empty") or f"{nm}|{s}" not in out["paired"]:
                ev[(nm, s)] = {k_: False for k_ in ("P1", "P2", "P3", "P4", "P5")}
                continue
            pr = out["paired"][f"{nm}|{s}"]
            P1 = m["mean_fold_gross_lift"] > 0 and m["t_folds_gross_lift"] >= thr_abs[nm]
            P2 = m["hac_gross_lift"] >= 2
            P3 = pr["gross_lift"]["t"] >= thr_rel[nm] and pr["hac_diff_gross_lift"] >= 2
            P4 = rc_pred_primary["rc_p"] < 0.05 and rc_pred_primary["individual"][f"{nm}|{s}"] < 0.05
            P5 = m["tp_lift_mean"] > 0 and m["t_folds_tp_lift"] >= thr_abs[nm]
            ev[(nm, s)] = {"P1": bool(P1), "P2": bool(P2), "P3": bool(P3), "P4": bool(P4), "P5": bool(P5)}
    c_any = d_any = b_any = False
    out["rules"] = {}
    for s in SIDES:
        p6 = sum(ev[(nm, s)]["P1"] and ev[(nm, s)]["P2"] for nm in ("V1", "V2", "V3")) >= 2
        for nm in ("V1", "V2", "V3"):
            e = ev[(nm, s)]
            m = rows[f"{nm}|{s}"]
            if m.get("empty") or f"{nm}|{s}" not in out["paired"]:
                e.update({"P6": bool(p6), "C": False, "D": False, "B": False, "empty": True})
                out["rules"][f"{nm}|{s}"] = e
                print(f"  {nm} {s:<5}: sin operaciones OOS -> ninguna regla evaluable (A)")
                continue
            pr = out["paired"][f"{nm}|{s}"]
            C = bool(all(e[p] for p in ("P1", "P2", "P3", "P4", "P5")) and p6)
            D = bool(C and m["oos_pooled_mean_net"] > 0 and m["oos_pooled_mean_net_conservative"] > 0 and m["oos_entries"] >= 100
                     and m["t_folds_net"] >= thr_abs[nm] and m["t_folds_net_lift"] >= thr_abs[nm] and m["hac_t_3H_net"] >= 2 and rc_net_ok)
            B = bool((m["t_folds_gross_lift"] >= 2 and m["mean_fold_gross_lift"] > 0) or (pr["gross_lift"]["t"] >= 2 and pr["gross_lift"]["mean_diff"] > 0))
            e.update({"P6": bool(p6), "C": C, "D": D, "B": B})
            out["rules"][f"{nm}|{s}"] = e
            c_any |= C
            d_any |= D
            b_any |= B
            print(f"  {nm} {s:<5}: P1 {e['P1']!s:<5} P2 {e['P2']!s:<5} P3 {e['P3']!s:<5} P4 {e['P4']!s:<5} P5 {e['P5']!s:<5} P6 {p6!s:<5} | t folds lift bruto {m['t_folds_gross_lift']:+.2f} "
                  f"(umbral {thr_abs[nm]:.2f}); HAC {m['hac_gross_lift']:+.2f}; Δ vs B0 t {pr['gross_lift']['t']:+.2f} (umbral {thr_rel[nm]:.2f}); TP-lift t {m['t_folds_tp_lift']:+.2f} -> "
                  f"{'D' if D else ('C' if C else ('B' if B else 'A'))}")
    verdict = ("D (predictibilidad y rentabilidad: DETENERSE y mostrar al usuario)" if d_any else
               "C (evidencia robusta de predictibilidad: DETENERSE y mostrar al usuario)" if c_any else
               "B (pista exploratoria sin robustez suficiente)" if b_any else "A (sin evidencia de predictibilidad)")
    out["verdict"] = verdict
    print(f"\nESCENARIO: {verdict}")
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
