"""
Comparación 1h vs 4h (EXP-011): economía por operación y por condición, turnover, comparación emparejada por
calendario y Reality Check con K = 18.

    python run_timeframe_comparison.py --csv "D:\\O lol\\Guardado de datos\\BTCUSDT_binance_1h.csv" \
        --h1 results/exp011/h1 --h4 results/exp011/h4 --exp002-old results/exp005/exp002 \
        --exp001 results/exp005/exp001 --a1 results/exp008/regime --s results/exp009/structured \
        --v results/exp010/v1 results/exp010/v2 results/exp010/v3 results/exp010/v4 --out results/exp011/comparison.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from run_atr_comparison import exit_table
from run_regime_comparison import find, load, side_metrics
from trading_research.config import ResearchConfig
from trading_research.data import load_data
from trading_research.multiple_testing import (bonferroni_t_threshold, newey_west_t,
                                               procedure_series, reality_check, student_t_sf)

SIDES = ("LONG", "SHORT")
HOURS_YEAR = 8766.0
T_REL = 2.5


def to_hour_grid(z: dict, idx_tf: pd.DatetimeIndex, idx1: pd.DatetimeIndex, bar_hours: int) -> dict:
    """Pasa una serie OOS por barra (4h) a la grilla horaria: cada valor queda en la hora de apertura de su
    barra (0 / NaN en las demás horas); `covered` cubre las `bar_hours` horas de cada barra cubierta."""
    pos = idx1.get_indexer(idx_tf)
    assert (pos >= 0).all()
    out = {}
    n1 = len(idx1)
    for k, v in z.items():
        if k == "covered":
            cov = np.zeros(n1, bool)
            for off in range(bar_hours):
                cov[pos[v] + off] = True
            out[k] = cov
        elif k.startswith("base_"):
            g = np.full(n1, np.nan)
            g[pos] = v
            out[k] = g
        else:
            g = np.zeros(n1)
            g[pos] = v
            out[k] = g
    return out


def fold_of_bars(idx: pd.DatetimeIndex, summ: pd.DataFrame) -> np.ndarray:
    """Número de fold (0..K-1) de cada barra según el rango de VALIDATION de wf_summary; -1 fuera."""
    t = idx.as_unit("ns").asi8
    vs = pd.to_datetime(summ["val_start"], utc=True).dt.as_unit("ns").astype("int64").to_numpy()
    ve = pd.to_datetime(summ["val_end"], utc=True).dt.as_unit("ns").astype("int64").to_numpy()
    f = np.searchsorted(vs, t, side="right") - 1
    ok = (f >= 0) & (t <= ve[np.clip(f, 0, len(ve) - 1)])
    return np.where(ok, f, -1)


def per_condition_series(z: dict, summ: pd.DataFrame, idx: pd.DatetimeIndex, key: str) -> np.ndarray:
    """Por barra: suma de `key` (p. ej. retornos netos, brutos o conteo) de las operaciones abiertas en la barra
    dividida por las condiciones seleccionadas del fold. Su suma sobre una ventana de VALIDATION es el valor por
    condición seleccionada y ventana."""
    f = fold_of_bars(idx, summ)
    nsel = summ["selected_in_train"].to_numpy(float)
    w = np.zeros(len(idx))
    ok = (f >= 0) & z["covered"]
    w[ok] = np.where(nsel[f[ok]] > 0, 1.0 / np.maximum(nsel[f[ok]], 1), 0.0)
    return z[key] * w


def paired_t(d: np.ndarray) -> float:
    d = d[np.isfinite(d)]
    return float(d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))) if len(d) > 2 and d.std() > 0 else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--h1", required=True)
    ap.add_argument("--h4", required=True)
    ap.add_argument("--exp002-old", default=None)
    ap.add_argument("--exp001", default=None)
    ap.add_argument("--a1", default=None)
    ap.add_argument("--s", default=None)
    ap.add_argument("--v", nargs=4, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--boot", type=int, default=1000)
    a = ap.parse_args()
    pd.set_option("display.width", 250)
    base = dict(DATA_SOURCE="csv", CSV_PATH=a.csv)
    cfg1 = ResearchConfig(TIMEFRAME="1h", **base)
    cfg4 = ResearchConfig(TIMEFRAME="4h", CSV_TIMEFRAME="1h", **base)
    df1, df4 = load_data(cfg1), load_data(cfg4)
    idx1, idx4 = df1.index, df4.index
    runs = {("1h", s): load(find(a.h1, s)) for s in SIDES}
    runs.update({("4h", s): load(find(a.h4, s)) for s in SIDES})
    bar_h = {"1h": 1, "4h": 4}
    Hn = {"1h": 100, "4h": 25}
    out: dict = {}

    if a.exp002_old:
        print("=" * 110)
        print("Regresión: 1h re-corrido con el código nuevo vs EXP-002")
        out["regression"] = {}
        for s in SIDES:
            new, old = runs[("1h", s)][0], load(find(a.exp002_old, s))[0]
            cols = [c for c in old.columns if c in new.columns and old[c].dtype.kind in "fi"]
            same = all(np.array_equal(new[c].to_numpy(float), old[c].to_numpy(float), equal_nan=True) for c in cols)
            out["regression"][s] = {"identical": bool(same), "columns": len(cols)}
            print(f"  {s}: {len(cols)} columnas numéricas idénticas = {same}")

    print("=" * 110)
    print("Métricas por timeframe y lado (costos typical; conservative donde se indica)")
    rows = {f"{tf}|{s}": side_metrics(*runs[(tf, s)], h=Hn[tf]) for tf in ("1h", "4h") for s in SIDES}
    print(pd.DataFrame(rows).to_string(float_format=lambda v: f"{v:.5f}"))
    out["metrics"] = rows

    print("\nEconomía y turnover (pooled sobre todas las operaciones OOS de las condiciones seleccionadas)")
    econ = {}
    for tf in ("1h", "4h"):
        for s in SIDES:
            summ, ag, z = runs[(tf, s)]
            cov = z["covered"]
            n = float(z["cnt"][cov].sum())
            gross = float(z["gross_sum"][cov].sum()) / n
            net_t = float(z["sum_typical"][cov].sum()) / n
            net_c = float(z["sum_conservative"][cov].sum()) / n
            sel = float(summ["selected_in_train"].sum())
            hours = float(cov.sum()) * bar_h[tf]
            idx_tf = idx1 if tf == "1h" else idx4
            nf = int((summ["selected_in_train"] > 0).sum())             # ventanas con condiciones seleccionadas
            pc = {k: float(per_condition_series(z, summ, idx_tf, k).sum()) / nf
                  for k in ("cnt", "gross_sum", "sum_typical", "sum_conservative")}
            e = {"trades": int(n), "gross_per_trade": gross, "net_per_trade_typical": net_t,
                 "net_per_trade_conservative": net_c, "cost_per_trade_typical": gross - net_t,
                 "cost_per_trade_conservative": gross - net_c, "selected_conditions_total": int(sel),
                 "trades_per_condition_window": pc["cnt"], "gross_per_condition_window": pc["gross_sum"],
                 "net_per_condition_window_typical": pc["sum_typical"],
                 "net_per_condition_window_conservative": pc["sum_conservative"],
                 "cost_per_condition_window_typical": pc["gross_sum"] - pc["sum_typical"],
                 "pooled_trades_per_year": n / (hours / HOURS_YEAR),
                 "pooled_trades_per_1000_bars": n / float(cov.sum()) * 1000,
                 "hours_between_entries_per_condition": 720.0 / pc["cnt"],
                 "mean_duration_hours": float(z["hold_sum"][cov].sum()) / n * bar_h[tf],
                 "mean_duration_bars": float(z["hold_sum"][cov].sum()) / n,
                 "tp_share_of_resolved": None, "ambiguous_pct": None}
            ex = exit_table(z)
            tp, sl = ex["TP_FIRST"]["n"], ex["SL_FIRST"]["n"]
            e["tp_share_of_resolved"] = tp / (tp + sl)
            e["tp_share_random_walk"] = ex["mean_sl_pct"] / (ex["mean_tp_pct"] + ex["mean_sl_pct"])
            e["ambiguous_pct"] = ex["AMBIGUOUS"]["pct"]
            e["exits"] = ex
            econ[f"{tf}|{s}"] = e
    out["economics"] = econ
    keys = ["trades", "gross_per_trade", "cost_per_trade_typical", "net_per_trade_typical", "net_per_trade_conservative",
            "cost_per_trade_conservative", "trades_per_condition_window", "gross_per_condition_window",
            "cost_per_condition_window_typical", "net_per_condition_window_typical", "net_per_condition_window_conservative",
            "pooled_trades_per_year", "pooled_trades_per_1000_bars", "hours_between_entries_per_condition",
            "mean_duration_hours", "mean_duration_bars", "tp_share_of_resolved", "tp_share_random_walk", "ambiguous_pct"]
    print(pd.DataFrame({k: {m: v[m] for m in keys} for k, v in econ.items()}).to_string(float_format=lambda v: f"{v:.5f}"))
    print("\nMotivo de salida (typical): TP_FIRST / SL_FIRST / NONE / AMBIGUOUS  [% de operaciones | neto medio por operación]")
    for k, v in econ.items():
        ex = v["exits"]
        print(f"  {k:<9} " + "  ".join(f"{nm} {ex[nm]['pct'] * 100:5.1f}% {ex[nm]['mean_net'] * 100:+6.2f}%"
                                      for nm in ("TP_FIRST", "SL_FIRST", "NONE", "AMBIGUOUS"))
              + f"  | TP/SL medios {ex['mean_tp_pct'] * 100:.1f}/{ex['mean_sl_pct'] * 100:.1f}%")
    print("\nDiferencia 4h - 1h (pooled)")
    out["diff_4h_minus_1h"] = {}
    for s in SIDES:
        d = {k: econ[f"4h|{s}"][k] - econ[f"1h|{s}"][k] for k in keys if isinstance(econ[f"4h|{s}"][k], (int, float))}
        out["diff_4h_minus_1h"][s] = d
        print(f"  {s}: neto/op {d['net_per_trade_typical'] * 100:+.3f} pp (bruto {d['gross_per_trade'] * 100:+.3f}, costo {-d['cost_per_trade_typical'] * 100:+.3f}); "
              f"operaciones/condición·ventana {d['trades_per_condition_window']:+.2f}; neto/condición·ventana {d['net_per_condition_window_typical'] * 100:+.3f} pp; "
              f"duración {d['mean_duration_hours']:+.1f} h; operaciones totales {d['trades']:+.0f}")
        e1, e4 = econ[f"1h|{s}"], econ[f"4h|{s}"]
        # valores por operación con el MISMO peso que el neto por condición·ventana (identidad exacta:
        # neto_cw = operaciones_cw × neto por operación)
        def pt(e, k):
            return e[k] / e["trades_per_condition_window"]
        n1, n4 = e1["trades_per_condition_window"], e4["trades_per_condition_window"]
        npt1, npt4 = pt(e1, "net_per_condition_window_typical"), pt(e4, "net_per_condition_window_typical")
        turn = (n4 - n1) * npt1
        pert = n4 * (npt4 - npt1)
        gro = n4 * (pt(e4, "gross_per_condition_window") - pt(e1, "gross_per_condition_window"))
        cos = -n4 * (pt(e4, "cost_per_condition_window_typical") - pt(e1, "cost_per_condition_window_typical"))
        out["diff_4h_minus_1h"][s]["decomposition"] = {"turnover_effect": turn, "per_trade_effect": pert,
                                                       "per_trade_gross_part": gro, "per_trade_cost_part": cos,
                                                       "total": turn + pert}
        print(f"     descomposición del cambio en neto por condición·ventana: turnover {turn * 100:+.3f} pp + por operación {pert * 100:+.3f} pp "
              f"(de éste: bruto {gro * 100:+.3f}, costo {cos * 100:+.3f}) = {(turn + pert) * 100:+.3f} pp")

    # ---- comparación emparejada por calendario (grilla horaria)
    print("\nComparación emparejada 4h - 1h por calendario (ventanas = las VALIDATION de 1h; grilla horaria común)")
    s1_summ = runs[("1h", "LONG")][0]
    win = fold_of_bars(idx1, s1_summ)
    out["paired"] = {}
    r1h, r1t = {}, {}
    grid4 = {s: to_hour_grid(runs[("4h", s)][2], idx4, idx1, 4) for s in SIDES}
    for s in SIDES:
        z1, z4 = runs[("1h", s)][2], grid4[s]
        common = z1["covered"] & z4["covered"] & (win >= 0)
        res = {}
        for sc in ("typical", "conservative"):
            ser1 = per_condition_series(z1, runs[("1h", s)][0], idx1, f"sum_{sc}")
            n4 = per_condition_series(runs[("4h", s)][2], runs[("4h", s)][0], idx4, f"sum_{sc}")
            ser4 = np.zeros(len(idx1))
            ser4[idx1.get_indexer(idx4)] = n4
            diff = (ser4 - ser1)
            dw = np.array([diff[common & (win == w)].sum() for w in range(win.max() + 1)])
            ok = np.array([(common & (win == w)).any() for w in range(win.max() + 1)])
            dwv = dw[ok]
            hac = newey_west_t(diff[common], 300)
            boot = reality_check(diff[common][:, None], n_boot=a.boot, mean_block=300, seed=0)["p_value"]
            res[sc] = {"mean_window_diff": float(dwv.mean()), "t_paired": paired_t(dwv), "n_windows": int(ok.sum()),
                       "hac_t_300": hac, "boot_p_4h_gt_1h": boot,
                       "mean_1h": float(np.array([ser1[common & (win == w)].sum() for w in range(win.max() + 1)])[ok].mean()),
                       "mean_4h": float(np.array([ser4[common & (win == w)].sum() for w in range(win.max() + 1)])[ok].mean())}
        # por operación, por ventana
        pt = {}
        for sc in ("typical", "conservative"):
            dvals = []
            for w in range(win.max() + 1):
                m = common & (win == w)
                c1, c4 = z1["cnt"][m].sum(), z4["cnt"][m].sum()
                if c1 > 0 and c4 > 0:
                    dvals.append(z4[f"sum_{sc}"][m].sum() / c4 - z1[f"sum_{sc}"][m].sum() / c1)
            dvals = np.array(dvals)
            pt[sc] = {"mean_diff": float(dvals.mean()), "t_paired": paired_t(dvals), "n_windows": int(len(dvals))}
        res["per_trade"] = pt
        h = res["typical"]["t_paired"] >= T_REL and res["typical"]["hac_t_300"] >= 2 and res["conservative"]["t_paired"] >= 2
        t = pt["typical"]["t_paired"] >= T_REL and pt["conservative"]["t_paired"] >= 2
        res["R1h"], res["R1t"] = bool(h), bool(t)
        r1h[s], r1t[s] = h, t
        out["paired"][s] = res
        print(f"  {s}: neto por condición·ventana (suma de 30 días): 1h {res['typical']['mean_1h'] * 100:+.3f}%  4h {res['typical']['mean_4h'] * 100:+.3f}%  "
              f"dif. {res['typical']['mean_window_diff'] * 100:+.3f} pp (t pareado {res['typical']['t_paired']:+.2f}, n={res['typical']['n_windows']}; "
              f"HAC {res['typical']['hac_t_300']:+.2f}; bootstrap p(4h>1h) {res['typical']['boot_p_4h_gt_1h']:.3f}; conservative t {res['conservative']['t_paired']:+.2f}) -> R1h {'SÍ' if h else 'NO'}")
        print(f"       neto por operación por ventana: dif. {pt['typical']['mean_diff'] * 100:+.3f} pp (t {pt['typical']['t_paired']:+.2f}, n={pt['typical']['n_windows']}; "
              f"conservative t {pt['conservative']['t_paired']:+.2f}) -> R1t {'SÍ' if t else 'NO'}")

    # ---- Reality Check K = 18
    print("\nReality Check (bloque 300 h, 1.000 remuestreos), universo K = 18 sobre grilla horaria")
    uni = {}
    if a.exp001:
        for s in SIDES:
            uni[f"EXP001|{s}"] = load(find(a.exp001, s))[2]
    for s in SIDES:
        uni[f"EXP002(1h)|{s}"] = runs[("1h", s)][2]
        if a.a1:
            uni[f"EXP008|{s}"] = load(find(a.a1, s))[2]
        if a.s:
            uni[f"EXP009|{s}"] = load(find(a.s, s))[2]
    if a.v:
        for i, p in enumerate(a.v, 1):
            for s in SIDES:
                uni[f"EXP010-V{i}|{s}"] = load(find(p, s))[2]
    for s in SIDES:
        uni[f"EXP011(4h)|{s}"] = grid4[s]
    idx = np.flatnonzero(np.all([v["covered"] for v in uni.values()], axis=0))
    print(f"  K = {len(uni)}, T = {len(idx)} horas")
    out["RC"] = []
    for sc in ("typical", "conservative"):
        for bm in ("zero", "lift"):
            F = np.column_stack([procedure_series(v, sc, bm)[idx] for v in uni.values()])
            rc = reality_check(F, n_boot=a.boot, mean_block=300, seed=0)
            ind = {n: reality_check(F[:, [k]], n_boot=a.boot, mean_block=300, seed=0)["p_value"] for k, n in enumerate(uni)}
            out["RC"].append({"scenario": sc, "benchmark": bm, "K": len(uni), "T": int(len(idx)), "rc_p": rc["p_value"],
                              "best": list(uni)[rc["best"]], "individual_p": ind})
            print(f"  {sc:<12} {bm:<5} RC p = {rc['p_value']:.3f} mejor = {list(uni)[rc['best']]:<16} | 4h LONG={ind['EXP011(4h)|LONG']:.2f} 4h SHORT={ind['EXP011(4h)|SHORT']:.2f}")

    # ---- reglas de decisión
    rc_ok = min(r["rc_p"] for r in out["RC"] if r["scenario"] == "typical") < 0.05
    print("\nReglas de decisión (4h):")
    d_any = c_any = b_any = False
    out["R2"] = {}
    for s in SIDES:
        m = rows[f"4h|{s}"]
        net_pos = (m["oos_pooled_mean_net"] or -1) > 0
        cons_pos = (m["oos_pooled_mean_net_conservative"] or -1) > 0
        stab = m["t_folds_net"] >= 3 and m["t_folds_lift"] >= 3
        hac = m["hac_t_3H_net"] >= 2
        ent = m["oos_entries"] >= 100
        d = bool(net_pos and cons_pos and stab and hac and ent and rc_ok and r1h[s])
        c = bool(net_pos and m["t_folds_net"] >= 2)
        b = bool(r1h[s] or r1t[s])
        out["R2"][s] = {"R1h": r1h[s], "R1t": r1t[s], "net>0": net_pos, "cons>0": cons_pos, "t_folds>=3 (net, lift)": bool(stab),
                        "HAC>=2": bool(hac), "entries>=100": ent, "RC<0.05": bool(rc_ok), "D": d, "C": c, "B": b}
        d_any |= d
        c_any |= c
        b_any |= b
        print(f"  {s}: R1h={r1h[s]} R1t={r1t[s]} | neto>0={net_pos} (cons>0={cons_pos}) | t folds net {m['t_folds_net']:+.2f} lift {m['t_folds_lift']:+.2f} | "
              f"HAC {m['hac_t_3H_net']:+.2f} | RC<0.05={rc_ok} -> {'D' if d else ('C' if c else ('B' if b else 'A'))}")
    verdict = ("D (evidencia fuerte: DETENERSE y mostrar al usuario)" if d_any else
               "C (neto > 0 pero no cumple R2)" if c_any else
               "B (4h mejora pero el neto sigue <= 0)" if b_any else "A (4h no mejora y sigue negativo)")
    out["verdict"] = verdict
    print(f"\nESCENARIO: {verdict}")
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
