"""
Comprobaciones descriptivas ANTES del walk-forward de EXP-011 (no se usan para cambiar el protocolo).

    python run_sanity_4h.py --csv "D:\\O lol\\Guardado de datos\\BTCUSDT_binance_1h.csv" --out results/exp011/sanity.json
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from trading_research.config import ResearchConfig
from trading_research.data import load_data
from trading_research.entry_detector import Segment, detect_entries
from trading_research.outcome_evaluator import AMBIGUOUS, NONE, SL_FIRST, TP_FIRST, build_outcome_table
from trading_research.resample import aggregate_ohlc_strict
from trading_research.statistics import baseline_stats
from trading_research.walk_forward import make_folds

Q = (0.5, 0.75, 0.9, 0.99)


def describe_returns(df: pd.DataFrame) -> dict:
    c = df["Close"].to_numpy()
    r = np.abs(c[1:] / c[:-1] - 1)
    rng = (df["High"] / df["Low"] - 1).to_numpy()
    return {"abs_return_close_to_close": {f"q{q:g}": float(np.quantile(r, q)) for q in Q},
            "abs_return_mean": float(r.mean()), "std_return": float(np.std(c[1:] / c[:-1] - 1)),
            "high_low_range_pct": {f"q{q:g}": float(np.quantile(rng, q)) for q in Q}}


def random_condition_reference(df: pd.DataFrame, cfg: ResearchConfig, p: float, win_bars: int, reps: int = 30) -> dict:
    """Operaciones esperadas de UNA condición con señales aleatorias (prob. p por barra) en una ventana de
    `win_bars` barras (VALIDATION), con `until_exit`, más resultado medio por operación (referencia sin ventaja)."""
    tb = build_outcome_table(df, cfg)
    H = cfg.MAX_HOLDING_BARS
    rng = np.random.default_rng(0)
    n = len(df)
    ents, holds, gross, net, cons = [], [], [], [], []
    for _ in range(reps):
        sig = rng.random(n) < p
        s0 = int(rng.integers(0, n - win_bars - 1))
        d = detect_entries(sig, Segment("W", s0, s0 + win_bars), H, 1, "until_exit", tb.exit_offset)
        e = d.entry_idx
        ents.append(len(e))
        if len(e):
            holds.append(float(tb.exit_offset[e].mean() + 1))
            gross.append(float(np.nanmean(tb.gross_return[e])))
            net.append(float(np.nanmean(tb.net_return[e])))
            cons.append(float(np.nanmean(tb.net_by_scenario["conservative"][e])))
    return {"p_signal_per_bar": p, "mean_entries_per_window": float(np.mean(ents)),
            "mean_hold_bars": float(np.mean(holds)), "mean_hold_hours": float(np.mean(holds) * cfg.bar_hours),
            "mean_gross_per_trade": float(np.mean(gross)), "mean_net_per_trade": float(np.mean(net)),
            "mean_cost_per_trade_typical": float(np.mean(gross) - np.mean(net)),
            "mean_cost_per_trade_conservative": float(np.mean(gross) - np.mean(cons))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    base = dict(DATA_SOURCE="csv", CSV_PATH=a.csv, TP_PERCENT=0.05, SL_PERCENT=0.03,
                COOLDOWN_MODE="until_exit", WF_HOLDOUT_FRACTION=0.15)
    cfg1 = ResearchConfig(TIMEFRAME="1h", MAX_HOLDING_BARS=100, WF_TRAIN_BARS=2500, WF_VAL_BARS=720, **base)
    cfg4 = ResearchConfig(TIMEFRAME="4h", CSV_TIMEFRAME="1h", MAX_HOLDING_BARS=25, WF_TRAIN_BARS=625,
                          WF_VAL_BARS=180, **base)
    df1, df4 = load_data(cfg1), load_data(cfg4)
    raw = load_data(ResearchConfig(DATA_SOURCE="csv", CSV_PATH=a.csv, TIMEFRAME="1h"))
    _, rep = aggregate_ohlc_strict(raw, "4h", "1h")
    out: dict = {"construction": rep}
    print("=== Construcción 1h -> 4h (estricta, UTC, bloques completos) ===")
    for k, v in rep.items():
        print(f"  {k}: {v}")
    print(f"  velas 1h originales: {len(df1)}   velas 4h válidas: {len(df4)}   descartado por bloques "
          f"incompletos: {rep['pct_blocks_discarded'] * 100:.3f} %   huecos de tiempo en la serie 4h: {rep['n_time_holes']}")
    print(f"  rango 1h: {df1.index[0]} -> {df1.index[-1]}   rango 4h: {df4.index[0]} -> {df4.index[-1]}")
    ts4 = df4.index.as_unit("ns").asi8
    assert (ts4 % (4 * 3600 * 10 ** 9) == 0).all()
    gaps1 = int((np.diff(df1.index.as_unit("ns").asi8) != 3600 * 10 ** 9).sum())
    out["gaps_1h"] = gaps1
    print(f"  discontinuidades temporales en 1h (misma convención, no se corrigen): {gaps1}")

    print("\n=== Folds ===")
    f1, h1 = make_folds(len(df1), cfg1)
    f4, h4 = make_folds(len(df4), cfg4)
    out["folds"] = {"1h": len(f1), "4h": len(f4)}
    print(f"  1h: {len(f1)} folds (TRAIN {cfg1.WF_TRAIN_BARS} barras = {cfg1.WF_TRAIN_BARS * cfg1.bar_hours:g} h, "
          f"VAL {cfg1.WF_VAL_BARS} = {cfg1.WF_VAL_BARS * cfg1.bar_hours:g} h)")
    print(f"  4h: {len(f4)} folds (TRAIN {cfg4.WF_TRAIN_BARS} barras = {cfg4.WF_TRAIN_BARS * cfg4.bar_hours:g} h, "
          f"VAL {cfg4.WF_VAL_BARS} = {cfg4.WF_VAL_BARS * cfg4.bar_hours:g} h)   H = {cfg4.MAX_HOLDING_BARS} barras = "
          f"{cfg4.horizon_hours:g} h")
    for nm, f, df in (("1h", f1, df1), ("4h", f4, df4)):
        v0, v1 = f[0]["VALIDATION"], f[-1]["VALIDATION"]
        print(f"  {nm}: primera VALIDATION {df.index[v0.start]} -> {df.index[v0.end - 1]}; "
              f"última {df.index[v1.start]} -> {df.index[v1.end - 1]}")
    off = [(df4.index[b["VALIDATION"].start] - df1.index[a_["VALIDATION"].start]).total_seconds() / 3600
           for a_, b in zip(f1, f4)]
    out["val_start_offset_hours"] = {"min": float(min(off)), "max": float(max(off))}
    print(f"  desfase entre el inicio de VALIDATION de 4h y de 1h por fold: {min(off):.1f} a {max(off):.1f} horas")

    print("\n=== Distribución de retornos y rango (descriptivo) ===")
    for nm, df in (("1h", df1), ("4h", df4)):
        d = describe_returns(df)
        out[f"returns_{nm}"] = d
        print(f"  {nm}: |retorno cierre-cierre| " + "  ".join(f"{k}={v * 100:.3f}%" for k, v in d["abs_return_close_to_close"].items())
              + f"  | (High-Low)/Low " + "  ".join(f"{k}={v * 100:.3f}%" for k, v in d["high_low_range_pct"].items())
              + f"  | desvío {d['std_return'] * 100:.3f}%")

    print("\n=== Línea base sin condición (entrar en todas las barras), TP 5 % / SL 3 %, costos typical ===")
    for nm, cfg, df in (("1h H=100", cfg1, df1), ("4h H=25", cfg4, df4)):
        for side in ("LONG", "SHORT"):
            import dataclasses
            c = dataclasses.replace(cfg, POSITION_TYPE=side)
            tb = build_outcome_table(df, c)
            b = baseline_stats(Segment("ALL", 0, len(df)), tb, c)
            out.setdefault("baseline_all_bars", {})[f"{nm}|{side}"] = {
                k: float(b[k]) for k in ("P_TP_FIRST", "P_SL_FIRST", "P_NONE", "P_AMBIGUOUS", "mean_gross_return",
                                         "mean_net_return", "mean_holding_bars")}
            print(f"  {nm} {side}: TP {b['P_TP_FIRST'] * 100:.1f}%  SL {b['P_SL_FIRST'] * 100:.1f}%  NONE {b['P_NONE'] * 100:.1f}%  "
                  f"AMB {b['P_AMBIGUOUS'] * 100:.2f}%  | bruto {b['mean_gross_return'] * 100:+.3f}%  neto {b['mean_net_return'] * 100:+.3f}%  "
                  f"duración {b['mean_holding_bars']:.1f} barras ({b['mean_holding_bars'] * cfg.bar_hours:.0f} h)")

    print("\n=== Condición aleatoria (prob. p de señal por barra): operaciones esperadas por ventana de VALIDATION (720 h) ===")
    out["random_condition"] = {}
    for p in (0.01, 0.05):
        for nm, cfg, df, win in (("1h", cfg1, df1, 720), ("4h", cfg4, df4, 180)):
            r = random_condition_reference(df, cfg, p, win)
            out["random_condition"][f"{nm}|p={p}"] = r
            print(f"  {nm} p={p:g}: {r['mean_entries_per_window']:.1f} operaciones/ventana, duración {r['mean_hold_hours']:.0f} h, "
                  f"bruto {r['mean_gross_per_trade'] * 100:+.3f}%/op, costo típico {r['mean_cost_per_trade_typical'] * 100:.3f}%/op, "
                  f"neto {r['mean_net_per_trade'] * 100:+.3f}%/op")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1, default=float)


if __name__ == "__main__":
    main()
