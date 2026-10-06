"""EXP-010: salidas TP/SL proporcionales al ATR (causalidad, niveles, ambigüedad, baseline intacto)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_core import random_walk  # noqa: E402

from trading_research.config import ResearchConfig
from trading_research.entry_detector import Segment
from trading_research.features import Indicator
from trading_research.indicators import atr as atr_indicator
from trading_research.lookahead import check_exit_levels, modified
from trading_research.outcome_evaluator import (AMBIGUOUS, SL_FIRST, TP_FIRST, atr_at_entry,
                                                atr_exit_levels, build_outcome_table)
from trading_research.search import ResearchPipeline
from trading_research.statistics import baseline_stats
from trading_research.walk_forward import run_walk_forward


def _cfg(side="LONG", tp=2.0, sl=1.0, H=60, **kw):
    return ResearchConfig(EXIT_MODE="atr", TP_ATR_MULT=tp, SL_ATR_MULT=sl, MAX_HOLDING_BARS=H,
                          POSITION_TYPE=side, **kw)


def _manual_atr(df, period=14):
    return atr_indicator(df, period)["value"].to_numpy()


# 1) causalidad del ATR de entrada ------------------------------------------------------------
def test_atr_at_entry_uses_only_information_up_to_signal_bar():
    df = random_walk(3000, 3)
    full = atr_at_entry(df, 14)
    manual = _manual_atr(df)
    assert np.isnan(full[0]) and np.allclose(full[1:], manual[:-1], equal_nan=True)   # ATR[e-1]
    for e in (20, 300, 1234, 2999):                                   # recalculado sin nada posterior a t = e-1
        trunc = _manual_atr(df.iloc[:e])[-1]                          # ATR[e-1] con datos hasta e-1
        assert full[e] == pytest.approx(trunc, rel=1e-12)


# 2) y 3) truncación y perturbación del futuro ------------------------------------------------
@pytest.mark.parametrize("side", ["LONG", "SHORT"])
def test_exit_levels_invariant_to_truncation_and_future_perturbation(side):
    df = random_walk(3000, 4)
    out = check_exit_levels(df, _cfg(side), [60, 300, 777, 1500, 2600], np.random.default_rng(0))
    assert out == {"tp": 0, "sl": 0, "valid": 0}


def test_check_exit_levels_detects_a_leaky_atr(monkeypatch):
    """Canario: un ATR que usa la vela t+1 (shift negativo) debe ser detectado."""
    import trading_research.outcome_evaluator as oe

    def leaky(df, period):
        a = oe.atr_values(df, period)
        return np.r_[a[1:], np.nan]                  # ATR[e]: incluye la vela de entrada y la siguiente

    monkeypatch.setattr(oe, "atr_at_entry", lambda df, period: leaky(df, period))
    df = random_walk(3000, 5)
    out = check_exit_levels(df, _cfg("LONG"), [300, 1500], np.random.default_rng(1))
    assert out["tp"] > 0 and out["sl"] > 0


# 4) y 5) niveles correctos --------------------------------------------------------------------
def test_levels_long_and_short_match_the_formula():
    df = random_walk(2000, 6)
    a = _manual_atr(df)
    o = df["Open"].to_numpy()
    for e in (30, 500, 1999):
        tp, sl, ok = atr_exit_levels(df, _cfg("LONG", 3.0, 2.0))
        assert ok[e] and tp[e] == pytest.approx(o[e] + 3.0 * a[e - 1]) and sl[e] == pytest.approx(o[e] - 2.0 * a[e - 1])
        tp, sl, ok = atr_exit_levels(df, _cfg("SHORT", 4.0, 2.0))
        assert ok[e] and tp[e] == pytest.approx(o[e] - 4.0 * a[e - 1]) and sl[e] == pytest.approx(o[e] + 2.0 * a[e - 1])


# 6) fijados al entrar --------------------------------------------------------------------------
@pytest.mark.parametrize("side", ["LONG", "SHORT"])
def test_levels_are_fixed_at_entry_and_exits_happen_exactly_at_them(side):
    df = random_walk(4000, 7)
    cfg = _cfg(side, 2.0, 1.0, H=80)
    tb = build_outcome_table(df, cfg)
    tp, sl, ok = atr_exit_levels(df, cfg)
    m = len(df) - 80 + 1
    sel = np.flatnonzero(ok[:m] & (tb.outcome[:m] == TP_FIRST))
    assert len(sel) > 100
    assert np.allclose(tb.exit_price[sel], tp[sel], rtol=1e-9)         # sale en el TP calculado al entrar
    p = df["Open"].to_numpy()[:m]
    dist = np.abs(tb.exit_price[sel] - p[sel])
    a = _manual_atr(df)
    assert np.allclose(dist, 2.0 * a[sel - 1], rtol=1e-9)              # nunca se reescala con ATR posteriores
    assert np.allclose(tb.tp_frac[sel] * p[sel], 2.0 * a[sel - 1], rtol=1e-9)
    ssl = np.flatnonzero(ok[:m] & (tb.outcome[:m] == SL_FIRST))
    gap_free = np.isclose(tb.exit_price[ssl], sl[ssl], rtol=1e-9)
    assert gap_free.mean() > 0.8                                       # SL en su nivel (salvo gaps de apertura)
    assert (np.abs(tb.exit_price[ssl] - p[ssl]) >= 1.0 * a[ssl - 1] * (1 - 1e-9)).all()


# 7) calentamiento: sin ATR no hay operación ------------------------------------------------------
def test_warmup_entries_are_invalid_nan_and_excluded_from_signals_and_baseline():
    df = random_walk(2600, 8)
    cfg = _cfg("LONG", 2.0, 1.0, H=40, N_SIMPLE_CONDITIONS=50, MIN_CASES_ABSOLUTE=1, MIN_CASES_FRACTION=0.0,
               SAVE_EVENTS=False, MAX_CONDITION_DEPTH=1)
    tb = build_outcome_table(df, cfg)
    n_warm = int((~tb.entry_valid[:2500]).sum())
    assert 10 <= n_warm <= 16 and not tb.entry_valid[:14].any() and tb.entry_valid[20]
    bad = np.flatnonzero(~tb.entry_valid[: len(df) - 40 + 1])
    assert np.isnan(tb.net_return[bad]).all() and (tb.outcome[bad] == -1).all()
    assert all(np.isnan(a[bad]).all() for a in tb.net_by_scenario.values())
    seg = Segment("T", 0, 1000)
    base = baseline_stats(seg, tb, cfg)
    assert base["n_entries"] == (1000 - 40) - (n_warm - 1)           # t = 0..959 -> e = 1..960; e = 0 no es entrada de ningún t
    assert np.isfinite(base["mean_net_return"])
    segs = {"TRAIN": Segment("TRAIN", 0, 1500), "VALIDATION": Segment("VALIDATION", 1500, 2200)}
    pipe = ResearchPipeline(cfg, df=df, segments=segs)
    assert pipe.sig_ok is not None and not pipe.sig_ok[:13].any()      # señal en t=13 -> entrada e=14 (primer ATR en 13)
    res = pipe.run()
    assert np.isfinite(res.results["TRAIN"]["mean_net_return"].dropna()).all()


# 8) ambigüedad TP/SL en la misma vela --------------------------------------------------------------
def test_ambiguous_bar_keeps_the_conservative_policy_with_atr_levels():
    n = 60
    idx = pd.date_range("2022-01-01", periods=n, freq="h", tz="UTC")
    o = np.full(n, 100.0)
    h, l, c = np.full(n, 100.5), np.full(n, 99.5), np.full(n, 100.0)
    h[26], l[26] = 130.0, 70.0                                         # toca TP y SL en la misma vela
    df = pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c}, index=idx)
    e = 25
    for side in ("LONG", "SHORT"):
        cfg = _cfg(side, 2.0, 1.0, H=10)
        tb = build_outcome_table(df, cfg)
        a = _manual_atr(df)[e - 1]
        assert a == pytest.approx(1.0) and tb.outcome[e] == AMBIGUOUS
        tp, sl, _ = atr_exit_levels(df, cfg)
        worst = (sl[e] - 100.0) / 100.0 if side == "LONG" else (100.0 - sl[e]) / 100.0
        assert tb.gross_return[e] == pytest.approx(worst)              # política `worst`: se asume el SL
        assert tb.exit_offset[e] == 1


# 9) el resultado de una operación no depende de nada posterior a ella --------------------------------
def test_trade_results_invariant_to_data_after_the_trade():
    df = random_walk(3500, 9)
    H = 50
    cfg = _cfg("LONG", 3.0, 2.0, H=H)
    tb = build_outcome_table(df, cfg)
    for k in (400, 1500, 3000):
        for mode in ("truncate", "perturb"):
            tb2 = build_outcome_table(modified(df, k, mode, np.random.default_rng(k)), cfg)
            last_e = k - H + 1                                         # e + H - 1 <= k
            sl = slice(0, last_e + 1)
            assert np.array_equal(tb.outcome[sl], tb2.outcome[sl])
            assert np.array_equal(tb.exit_offset[sl], tb2.exit_offset[sl])
            for name in tb.net_by_scenario:
                assert np.allclose(tb.net_by_scenario[name][sl], tb2.net_by_scenario[name][sl], equal_nan=True)
            assert np.allclose(tb.exit_price[sl], tb2.exit_price[sl], equal_nan=True)


# 10) el baseline fijo no cambió (números dorados capturados con el código anterior a EXP-010) ----------
@pytest.mark.parametrize("side,counts,net,gross,cons,hold,mfe", [
    ("LONG", [1639, 2302, 0, 0], -1.4617996511915496, 7.973123284619335, -7.860278737080005, 38546, 278.76993776483255),
    ("SHORT", [1407, 2534, 0, 0], -16.63333292194023, -7.105808231968055, -23.38924258366164, 38904, 207.24873209421358),
])
def test_fixed_exits_baseline_is_numerically_unchanged(side, counts, net, gross, cons, hold, mfe):
    df = random_walk(4000, 13)
    cfg = ResearchConfig(POSITION_TYPE=side, TP_PERCENT=0.04, SL_PERCENT=0.025, MAX_HOLDING_BARS=60)
    assert cfg.EXIT_MODE == "fixed"
    t = build_outcome_table(df, cfg)
    ok = t.outcome >= 0
    assert [int((t.outcome == c).sum()) for c in range(4)] == counts
    assert float(np.nansum(t.net_return)) == pytest.approx(net, rel=1e-12)
    assert float(np.nansum(t.gross_return)) == pytest.approx(gross, rel=1e-12)
    assert float(np.nansum(t.net_by_scenario["conservative"])) == pytest.approx(cons, rel=1e-12)
    assert int(t.exit_offset[ok].sum()) == hold
    assert float(np.nansum(t.mfe)) == pytest.approx(mfe, rel=1e-12)
    assert t.entry_valid is None                                       # el modo fijo no enmascara nada


# Serie OOS por motivo de salida ----------------------------------------------------------------------
def test_wf_oos_series_exit_reason_breakdown_is_consistent():
    df = random_walk(4200, 21)
    cfg = _cfg("LONG", 2.0, 1.0, H=40, WALK_FORWARD=True, WF_TRAIN_BARS=1000, WF_VAL_BARS=400,
               WF_HOLDOUT_FRACTION=0.0, N_SIMPLE_CONDITIONS=200, MAX_CONDITION_DEPTH=1, MIN_CASES_ABSOLUTE=5,
               MIN_CASES_FRACTION=0.0, SAVE_EVENTS=False, FILTER_MODE="absolute", MIN_P_TP_FIRST=0.0,
               MIN_EXPECTED_RETURN=-1.0)
    wf = run_walk_forward(cfg, df)
    s = wf.oos_series
    names = ("TP_FIRST", "SL_FIRST", "NONE", "AMBIGUOUS")
    tot = s["cnt"].sum()
    assert tot > 500
    assert sum(s[f"x_cnt_{nm}"].sum() for nm in names) == pytest.approx(tot)
    for sc in ("typical", "conservative"):
        assert sum(s[f"x_sum_{nm}_{sc}"].sum() for nm in names) == pytest.approx(s[f"sum_{sc}"].sum())
    assert 0.0 < s["tp_frac_sum"].sum() / tot < 0.2                   # distancia media del TP en fracción del precio
    assert s["hold_sum"].sum() / tot >= 1.0
