"""EXP-012: TP/SL/H escalados por k (y TRAIN/VALIDATION escalados): geometría, causalidad y ventanas."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_core import random_walk  # noqa: E402

from trading_research.config import ResearchConfig
from trading_research.entry_detector import Segment, detect_entries, fits_in_segment
from trading_research.lookahead import modified
from trading_research.outcome_evaluator import SL_FIRST, TP_FIRST, build_outcome_table
from trading_research.walk_forward import make_folds, run_walk_forward

VARIANTS = [("B0", 0.05, 0.03, 100, 1), ("V1", 0.10, 0.06, 200, 2), ("V2", 0.15, 0.09, 300, 3), ("V3", 0.20, 0.12, 400, 4)]


def _cfg(tp, sl, H, side="LONG", **kw):
    return ResearchConfig(TP_PERCENT=tp, SL_PERCENT=sl, MAX_HOLDING_BARS=H, POSITION_TYPE=side, **kw)


@pytest.mark.parametrize("name,tp,sl,H,k", VARIANTS)
@pytest.mark.parametrize("side", ["LONG", "SHORT"])
def test_scaled_geometry_levels_and_exits(name, tp, sl, H, k, side):
    assert tp / sl == pytest.approx(5 / 3)                       # misma relación TP/SL en todas las variantes
    assert _cfg(tp, sl, H).horizon_hours == H                    # timeframe 1h: H barras = H horas
    df = random_walk(5200, 3)
    tb = build_outcome_table(df, _cfg(tp, sl, H, side))
    m = len(df) - H + 1
    P = df["Open"].to_numpy()[:m]
    sgn = 1 if side == "LONG" else -1
    assert np.allclose(tb.tp_frac[:m], tp) and np.allclose(tb.sl_frac[:m], sl)
    tpm = np.flatnonzero(tb.outcome[:m] == TP_FIRST)
    slm = np.flatnonzero(tb.outcome[:m] == SL_FIRST)
    assert len(tpm) > 20 and len(slm) > 20
    assert np.allclose(tb.exit_price[tpm], P[tpm] * (1 + sgn * tp))      # sale exactamente en el TP escalado
    assert (sgn * (tb.exit_price[slm] / P[slm] - 1) <= -sl * (1 - 1e-12)).all()   # SL escalado (o peor por gap)
    assert tb.exit_offset[:m].max() <= H - 1                              # nunca excede el horizonte


@pytest.mark.parametrize("name,tp,sl,H,k", VARIANTS)
@pytest.mark.parametrize("mode", ["truncate", "perturb"])
def test_trade_results_invariant_to_later_data_for_every_horizon(name, tp, sl, H, k, mode):
    df = random_walk(4800, 5)
    cfg = _cfg(tp, sl, H, "LONG")
    tb = build_outcome_table(df, cfg)
    cut = 3000
    tb2 = build_outcome_table(modified(df, cut, mode, np.random.default_rng(1)), cfg)
    last_e = cut - H + 1                                                   # e + H - 1 <= cut
    sl_ = slice(0, last_e + 1)
    assert np.array_equal(tb.outcome[sl_], tb2.outcome[sl_])
    assert np.array_equal(tb.exit_offset[sl_], tb2.exit_offset[sl_])
    assert np.allclose(tb.gross_return[sl_], tb2.gross_return[sl_]) and np.allclose(tb.net_return[sl_], tb2.net_return[sl_])
    for scn in tb.net_by_scenario:
        assert np.allclose(tb.net_by_scenario[scn][sl_], tb2.net_by_scenario[scn][sl_], equal_nan=True)


def test_extending_or_shrinking_the_dataset_does_not_change_history():
    df = random_walk(5000, 7)
    for _, tp, sl, H, _ in VARIANTS:
        cfg = _cfg(tp, sl, H, "SHORT")
        a, b = build_outcome_table(df.iloc[:3600], cfg), build_outcome_table(df, cfg)
        e = slice(1, 3600 - H + 1)
        assert np.array_equal(a.outcome[e], b.outcome[e]) and np.allclose(a.net_return[e], b.net_return[e])
        assert np.allclose(a.entry_price[e], b.entry_price[e])


def test_entries_are_open_t_plus_1_and_purged_with_the_scaled_horizon():
    df = random_walk(6000, 9)
    sig = np.zeros(len(df), bool)
    sig[40::37] = True
    for _, tp, sl, H, _ in VARIANTS:
        tb = build_outcome_table(df, _cfg(tp, sl, H))
        seg = Segment("V", 1000, 4000)
        d = detect_entries(sig, seg, H, 1, "until_exit", tb.exit_offset)
        assert len(d.entry_idx) > 3 and (d.entry_idx == d.confirm_idx + 1).all()
        assert np.array_equal(tb.entry_price[d.entry_idx], df["Open"].to_numpy()[d.entry_idx])
        assert fits_in_segment(d.entry_idx, H, seg).all()                  # la ventana [t, e+H-1] cabe en el segmento
        assert d.entry_idx.max() + H - 1 <= seg.end - 1
        assert d.n_dropped_horizon == int(sig[seg.start:seg.end].sum()) - int((sig[seg.start:seg.end] & (np.arange(seg.start, seg.end) <= seg.end - 1 - H)).sum())


def test_scaled_walk_forward_windows():
    """Número de folds, escala de TRAIN/VAL, fracción útil de VALIDATION y holdout intacto (n real = 79.909 velas)."""
    n = 79909
    expected_folds = {"B0": 90, "V1": 43, "V2": 27, "V3": 20}
    ends = []
    for name, tp, sl, H, k in VARIANTS:
        cfg = _cfg(tp, sl, H, WF_TRAIN_BARS=2500 * k, WF_VAL_BARS=720 * k, WF_HOLDOUT_FRACTION=0.15)
        folds, hold = make_folds(n, cfg)
        assert len(folds) == expected_folds[name]
        assert all(f["TRAIN"].n_bars == 2500 * k and f["VALIDATION"].n_bars == 720 * k for f in folds)
        assert all(f["TRAIN"].end == f["VALIDATION"].start for f in folds)
        assert all(folds[i]["VALIDATION"].end == folds[i + 1]["VALIDATION"].start for i in range(len(folds) - 1))
        assert folds[-1]["VALIDATION"].end == hold.start == 67923          # ninguna ventana toca el holdout
        assert max(f["VALIDATION"].end for f in folds) <= hold.start
        usable = (720 * k - H) / (720 * k)
        assert usable == pytest.approx(0.8611, abs=1e-3)                   # igual fracción útil en todas las escalas
        ends.append(folds[-1]["VALIDATION"].end)
    assert len(set(ends)) == 1


def test_wf_series_has_gross_alias_base_gross_and_duration_histogram():
    df = random_walk(4200, 21)
    H = 40
    cfg = _cfg(0.03, 0.02, H, WALK_FORWARD=True, WF_TRAIN_BARS=1000, WF_VAL_BARS=400, WF_HOLDOUT_FRACTION=0.0,
               N_SIMPLE_CONDITIONS=200, MAX_CONDITION_DEPTH=1, MIN_CASES_ABSOLUTE=5, MIN_CASES_FRACTION=0.0,
               SAVE_EVENTS=False, FILTER_MODE="absolute", MIN_P_TP_FIRST=0.0, MIN_EXPECTED_RETURN=-1.0)
    s = run_walk_forward(cfg, df).oos_series
    cov = s["covered"]
    assert np.array_equal(s["sum_gross"], s["gross_sum"]) and s["cnt"].sum() > 500
    assert s["hold_hist"].shape == (H + 1,) and s["hold_hist"].sum() == pytest.approx(s["cnt"].sum())
    assert s["hold_hist"][0] == 0                                           # duración mínima 1 barra
    assert (s["hold_sum"].sum() / s["cnt"].sum()) == pytest.approx((np.arange(H + 1) * s["hold_hist"]).sum() / s["hold_hist"].sum())
    assert np.isfinite(s["base_gross"][cov]).all()
