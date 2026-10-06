"""EXP-011: velas 4h construidas de forma estricta desde 1h (alineación UTC, bloques completos, causalidad)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_research.condition_generator import ConditionGenerator
from trading_research.config import ResearchConfig
from trading_research.data import load_data
from trading_research.entry_detector import Segment, detect_entries
from trading_research.features import FeatureStore
from trading_research.lookahead import check_resample_causality, check_operands, perturb_future
from trading_research.outcome_evaluator import build_outcome_table
from trading_research.resample import aggregate_ohlc_strict


def hourly(n=2400, start="2021-03-01 00:00", seed=0, tz="UTC"):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    o = np.r_[c[0], c[:-1]] * np.exp(rng.normal(0, 0.002, n))
    h = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, 0.004, n)))
    l = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, 0.004, n)))
    idx = pd.date_range(start, periods=n, freq="h", tz=tz)
    return pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c}, index=idx)


# 1-6) vela conocida: Open/High/Low/Close y alineación UTC -------------------------------------------------
def test_known_4h_candle_open_high_low_close_and_utc_alignment():
    idx = pd.date_range("2022-05-10 00:00", periods=8, freq="h", tz="UTC")
    df = pd.DataFrame({"Open": [10, 11, 12, 13, 20, 21, 22, 23.0],
                       "High": [15, 16, 30, 17, 25, 26, 27, 28.0],
                       "Low": [9, 8, 11, 12, 19, 5, 21, 22.0],
                       "Close": [11, 12, 13, 14, 21, 22, 23, 24.0]}, index=idx)
    out, rep = aggregate_ohlc_strict(df, "4h", "1h")
    assert list(out.index) == [pd.Timestamp("2022-05-10 00:00", tz="UTC"), pd.Timestamp("2022-05-10 04:00", tz="UTC")]
    a, b = out.iloc[0], out.iloc[1]
    assert (a.Open, a.High, a.Low, a.Close) == (10, 30, 8, 14)        # Open 1ª, máx High, mín Low, Close 4ª
    assert (b.Open, b.High, b.Low, b.Close) == (20, 28, 5, 24)
    assert rep["n_blocks_complete"] == 2 and rep["pct_blocks_discarded"] == 0
    # el timestamp es el INICIO del intervalo y es múltiplo de 4h en UTC
    assert all(t.hour % 4 == 0 and t.minute == 0 for t in out.index)
    # la zona horaria del índice no cambia nada; sin zona = UTC
    arg = df.copy(); arg.index = df.index.tz_convert("America/Argentina/Buenos_Aires")
    naive = df.copy(); naive.index = df.index.tz_localize(None)
    o2, _ = aggregate_ohlc_strict(arg, "4h", "1h")
    o3, _ = aggregate_ohlc_strict(naive, "4h", "1h")
    assert np.array_equal(out.to_numpy(), o2.to_numpy()) and np.array_equal(out.to_numpy(), o3.to_numpy())
    assert list(o2.index.tz_convert("UTC")) == list(out.index)
    assert o3.index.tz is None and list(o3.index) == [t.tz_localize(None) for t in out.index]


def test_blocks_start_at_00_04_08_12_16_20_utc_even_if_data_starts_mid_block():
    df = hourly(48, start="2021-03-01 02:00")            # empieza a las 02:00: el primer bloque queda incompleto
    out, rep = aggregate_ohlc_strict(df)
    assert out.index[0] == pd.Timestamp("2021-03-01 04:00", tz="UTC")
    assert set(out.index.hour) <= {0, 4, 8, 12, 16, 20}
    assert rep["n_blocks_discarded"] >= 1 and rep["n_blocks_incomplete_with_data"] >= 1


# 7-8) bloques incompletos: se rechazan; nada de forward-fill ------------------------------------------------
def test_incomplete_blocks_are_dropped_and_nothing_is_filled():
    df = hourly(96)
    holes = [5, 30, 31]                                   # horas 05 (bloque 04-07) y 06-07 del día 2 (bloque 04-07)
    cut = df.drop(df.index[holes])
    out, rep = aggregate_ohlc_strict(cut)
    full, _ = aggregate_ohlc_strict(df)
    gone = {df.index[5].floor("4h"), df.index[30].floor("4h")}
    assert gone.isdisjoint(set(out.index))                # esos bloques no existen (ni incompletos ni rellenados)
    assert len(out) == len(full) - len(gone) and not out.isna().any().any()
    # el resto es idéntico a la serie completa (nada se alteró)
    same = full.loc[out.index]
    assert np.array_equal(out.to_numpy(), same.to_numpy())
    assert rep["n_blocks_discarded"] == 2 and rep["n_blocks_without_data"] == 0
    # tampoco se completa un bloque con una hora duplicada/corrida: velas fuera de la grilla horaria se descartan
    odd = df.copy()
    idx = odd.index.as_unit("ns").asi8.copy()
    idx[10] += 30 * 60 * 10 ** 9                          # 10:30 en lugar de 10:00
    odd.index = pd.DatetimeIndex(pd.to_datetime(idx, unit="ns", utc=True))
    out2, rep2 = aggregate_ohlc_strict(odd)
    assert rep2["n_source_misaligned"] == 1 and odd.index[10].floor("4h") not in set(out2.index)


# 9) no usa una quinta vela 1h ----------------------------------------------------------------------------------
def test_candle_uses_exactly_its_four_hourly_bars_not_a_fifth():
    df = hourly(96, seed=2)
    ref, _ = aggregate_ohlc_strict(df)
    blk = pd.Timestamp("2021-03-02 04:00", tz="UTC")
    for off, expect_change in ((0, True), (3, True), (4, False), (-1, False)):   # 04:00-07:59 -> horas 0..3 del bloque
        d = df.copy()
        q = df.index.get_loc(blk) + off
        for col in ("Open", "High", "Low", "Close"):
            d.iloc[q, d.columns.get_loc(col)] = d[col].iloc[q] * 1.5
        out, _ = aggregate_ohlc_strict(d)
        changed = not np.array_equal(out.loc[blk].to_numpy(), ref.loc[blk].to_numpy())
        assert changed == expect_change, off


# 10-11) truncación y perturbación ----------------------------------------------------------------------------
def test_features_and_signals_invariant_to_truncation_and_to_later_hourly_data():
    df = hourly(3000, seed=3)
    d4, _ = aggregate_ohlc_strict(df)
    cfg = ResearchConfig(MAX_CONDITION_DEPTH=2, TIMEFRAME="4h")
    st = FeatureStore(d4)
    gen = ConditionGenerator(cfg, st, slice(0, 300), np.random.default_rng(1))
    conds = gen.generate_simple(120)
    rng = np.random.default_rng(0)
    out = check_resample_causality(df, conds, [301, 603, 1000, 1501, 2200], rng)
    assert out["variants"] >= 20 and out["ohlc"] == out["signals"] == out["entries"] == 0
    # operandos 4h sobre datos 1h truncados a mitad de bloque
    ops = st.operands if hasattr(st, "operands") else {}
    for k in (500, 1234):                                  # cortes a mitad de bloque
        d4k, _ = aggregate_ohlc_strict(df.iloc[: k + 1])
        assert np.array_equal(d4.iloc[: len(d4k)].to_numpy(), d4k.to_numpy())


def test_canary_a_partial_open_candle_is_detected():
    """Un agregador que conserva el bloque 4h abierto (pandas resample) viola la causalidad y se detecta."""
    df = hourly(2400, seed=4)

    def leaky(d1):
        return d1.resample("4h", label="left", closed="left").agg(
            {"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()

    d4, _ = aggregate_ohlc_strict(df)
    cfg = ResearchConfig(MAX_CONDITION_DEPTH=1, TIMEFRAME="4h")
    conds = ConditionGenerator(cfg, FeatureStore(d4), slice(0, 300), np.random.default_rng(2)).generate_simple(40)
    good = check_resample_causality(df, conds, [1001, 1502], np.random.default_rng(0))
    bad = check_resample_causality(df, conds, [1001, 1502], np.random.default_rng(0), aggregate=leaky)
    assert good["ohlc"] == 0 and bad["ohlc"] > 0


# 12) la entrada es Open[t+1] = Open de la primera hora de la siguiente vela 4h completa ------------------------
def test_entry_is_next_complete_4h_open():
    df = hourly(3000, seed=5)
    d4, _ = aggregate_ohlc_strict(df)
    cfg = ResearchConfig(MAX_HOLDING_BARS=25, TIMEFRAME="4h", TP_PERCENT=0.05, SL_PERCENT=0.03)
    tb = build_outcome_table(d4, cfg)
    sig = np.zeros(len(d4), bool)
    sig[50::40] = True
    det = detect_entries(sig, Segment("S", 0, len(d4)), 25, 1, "until_exit", tb.exit_offset)
    assert len(det.entry_idx) > 5 and (det.entry_idx == det.confirm_idx + 1).all()
    for t, e in zip(det.confirm_idx, det.entry_idx):
        assert tb.entry_price[e] == d4["Open"].iloc[e]
        nxt_start = d4.index[t] + pd.Timedelta(hours=4)           # la vela t cierra cuando empieza la siguiente
        assert d4.index[e] == nxt_start                           # (sin huecos en este dato sintético)
        assert d4["Open"].iloc[e] == df.loc[nxt_start, "Open"]    # = Open de la primera vela 1h del bloque siguiente


def test_entry_after_a_hole_is_the_next_complete_candle_not_an_incomplete_one():
    df = hourly(400, seed=6)
    cut = df.drop(df.index[[41]])                                 # rompe el bloque 40-43 (índice 10 de 4h)
    d4, rep = aggregate_ohlc_strict(cut)
    hole = df.index[40]
    assert hole not in set(d4.index) and rep["n_time_holes"] == 1
    t = d4.index.get_loc(df.index[36])                            # vela 36-39: última antes del hueco
    assert d4.index[t + 1] == df.index[44]                        # la siguiente fila es la siguiente vela COMPLETA


# 14-15) especificación: TP/SL del baseline, H = 25 barras de 4h = 100 horas, TRAIN/VAL en horas ------------------
def test_experiment_configuration_matches_the_specification(monkeypatch):
    import run_research
    argv = ["run_research.py", "--csv", "x.csv", "--timeframe", "4h", "--csv-timeframe", "1h", "--walk-forward",
            "--wf-train-bars", "625", "--wf-val-bars", "180", "--side", "LONG", "SHORT", "--tp", "0.05",
            "--sl", "0.03", "--horizon", "25", "--cooldown-mode", "until_exit", "--filter-mode", "both",
            "--cost-scenario", "typical", "--no-events", "--n-simple", "7500", "--seed", "42"]
    monkeypatch.setattr(sys, "argv", argv)
    a = run_research.parse_args()
    cfg = run_research.base_config(a)
    assert (cfg.TIMEFRAME, cfg.CSV_TIMEFRAME) == ("4h", "1h")
    assert cfg.TP_PERCENT == 0.05 and a.sl == [0.03] and a.horizon == [25] and cfg.EXIT_MODE == "fixed"
    assert cfg.COOLDOWN_MODE == "until_exit" and cfg.FILTER_MODE == "both" and cfg.COST_SCENARIO == "typical"
    assert cfg.N_SIMPLE_CONDITIONS == 7500 and cfg.RANDOM_SEED == 42 and cfg.SEARCH_MODE == "random"
    assert not cfg.REGIME_FEATURES and cfg.WF_TRAIN_BARS == 625 and cfg.WF_VAL_BARS == 180
    c4 = ResearchConfig(TIMEFRAME="4h", MAX_HOLDING_BARS=25, WF_TRAIN_BARS=625, WF_VAL_BARS=180)
    c1 = ResearchConfig(TIMEFRAME="1h", MAX_HOLDING_BARS=100, WF_TRAIN_BARS=2500, WF_VAL_BARS=720)
    assert c4.horizon_hours == c1.horizon_hours == 100.0
    assert c4.WF_TRAIN_BARS * c4.bar_hours == c1.WF_TRAIN_BARS * c1.bar_hours == 2500.0
    assert c4.WF_VAL_BARS * c4.bar_hours == c1.WF_VAL_BARS * c1.bar_hours == 720.0


# 16) el camino 1h no cambia ---------------------------------------------------------------------------------
def test_loading_hourly_data_without_resampling_is_unchanged(tmp_path):
    df = hourly(300, seed=7)
    p = tmp_path / "h.csv"
    df.reset_index().rename(columns={"index": "Date"}).to_csv(p, index=False)
    cfg = ResearchConfig(DATA_SOURCE="csv", CSV_PATH=str(p), TIMEFRAME="1h")
    a = load_data(cfg)
    assert len(a) == 300 and np.allclose(a["Close"].to_numpy(), df["Close"].to_numpy())
    cfg4 = ResearchConfig(DATA_SOURCE="csv", CSV_PATH=str(p), TIMEFRAME="4h", CSV_TIMEFRAME="1h")
    b = load_data(cfg4)
    assert len(b) == 300 // 4 and b.index[0].hour % 4 == 0
