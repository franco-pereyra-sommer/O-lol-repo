"""
Tests de las propiedades críticas: ausencia de look-ahead, semántica de
cruces y condiciones temporales, clasificación de resultados, cooldown,
purga de horizonte, serialización y reproducibilidad.

    python -m pytest -q
"""
import numpy as np
import pandas as pd
import pytest

from trading_research.condition_generator import ConditionGenerator
from trading_research.conditions import (And, Compare, Cross, Not, OccurredWithin, Then,
                                         condition_from_dict)
from trading_research.config import ResearchConfig
from trading_research.entry_detector import Segment, apply_cooldown, detect_entries
from trading_research.features import Constant, FeatureStore, Indicator, PriceField
from trading_research.outcome_evaluator import (AMBIGUOUS, NONE, SL_FIRST, TP_FIRST,
                                                build_outcome_table)
from trading_research.statistics import compute_stats


def random_walk(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    o = np.r_[c[0], c[:-1]] * np.exp(rng.normal(0, 0.002, n))
    h = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, 0.004, n)))
    l = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, 0.004, n)))
    idx = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c}, index=idx)


def ohlc(rows):
    idx = pd.date_range("2020-01-01", periods=len(rows), freq="h", tz="UTC")
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close"], index=idx, dtype=float)


# ---------------------------------------------------------------------- #
def test_no_lookahead_truncation_invariance():
    """La señal en t no puede cambiar si se borran las velas posteriores a t."""
    df = random_walk()
    cfg = ResearchConfig(MAX_CONDITION_DEPTH=3)
    full = FeatureStore(df)
    gen = ConditionGenerator(cfg, full, slice(0, 1500), np.random.default_rng(1))
    simple = gen.generate_simple(150)
    conds = simple + gen.generate_complex(simple, 150, 3)
    for k in (400, 1100, 2200):
        trunc = FeatureStore(df.iloc[:k])
        for c in conds:
            a = c.evaluate(full)[:k]
            b = c.evaluate(trunc)
            assert np.array_equal(a, b), f"look-ahead en {c.describe()} (k={k})"


def test_cross_semantics_and_event():
    df = ohlc([[1, 1, 1, c] for c in [10, 20, 30, 40, 30, 20, 30]])
    st = FeatureStore(df)
    up = Cross(PriceField("Close"), Constant(30.0), "above").evaluate(st)
    dn = Cross(PriceField("Close"), Constant(30.0), "below").evaluate(st)
    # A[t-1] < 30 y A[t] >= 30 : t=2 (20->30) y t=6 (20->30)
    assert list(np.flatnonzero(up)) == [2, 6]
    # A[t-1] > 30 y A[t] <= 30 : t=4 (40->30)
    assert list(np.flatnonzero(dn)) == [4]
    state = Compare(PriceField("Close"), ">=", Constant(30.0)).evaluate(st)
    assert list(np.flatnonzero(state)) == [2, 3, 4, 6]


def test_then_confirms_at_second_event():
    """RSI cruza en t=100, MACD en t=106 -> confirmación 106, entrada Open[107]."""
    n = 200
    df = ohlc([[1, 1, 1, 1]] * n)
    a = np.zeros(n); a[100:] = 1   # "cruza" en 100
    b = np.zeros(n); b[106:] = 1   # "cruza" en 106
    df["Close"] = 1.0
    st = FeatureStore(df)

    class Arr(PriceField):
        def __init__(self, name, arr):
            object.__setattr__(self, "field", name); object.__setattr__(self, "_arr", arr)
        def compute(self, _): return self._arr

    A = Cross(Arr("A", a), Constant(0.5), "above")
    B = Cross(Arr("B", b), Constant(0.5), "above")
    sig = Then(A, B, 10).evaluate(st)
    assert list(np.flatnonzero(sig)) == [106]
    assert not Then(A, B, 5).evaluate(st).any()          # fuera de ventana
    assert not Then(B, A, 10).evaluate(st).any()         # orden inverso
    within = And(OccurredWithin(A, 10), B).evaluate(st)
    assert np.array_equal(within, sig)                   # equivalencia documentada
    det = detect_entries(sig, Segment("ALL", 0, n), holding_bars=5, cooldown=0)
    assert list(det.entry_idx) == [107]


def test_not_is_false_during_warmup():
    df = random_walk(300)
    st = FeatureStore(df)
    c = Not(Compare(Indicator("EMA", (50,)), ">", PriceField("Close")))
    assert not c.evaluate(st)[:49].any()


def test_outcome_classification():
    cfg = ResearchConfig(MAX_HOLDING_BARS=3, TP_PERCENT=0.05, SL_PERCENT=0.02,
                         COMMISSION_RATE=0, SLIPPAGE_RATE=0, SPREAD_RATE=0,
                         FAVORABLE_OUTCOMES=())
    rows = [
        [100, 101, 99, 100],    # 0: entrada -> TP en barra 2
        [100, 103, 99, 102],    # 1
        [102, 106, 100, 105],   # 2: High 106 >= 105
        [100, 100.5, 97, 98],   # 3: entrada -> SL inmediato (Low 97 <= 98)
        [98, 99, 97, 98],       # 4
        [100, 106, 97, 100],    # 5: entrada -> AMBIGUOUS (ambos en la misma vela)
        [100, 101, 99, 100.5],  # 6: entrada -> NONE
        [100.5, 101, 99, 100.7],
        [100.7, 101, 99.5, 100.2],
        [95, 96, 94, 95],       # 9: gap bajo el SL de la entrada en 7
        [95, 96, 94, 95],
    ]
    t = build_outcome_table(ohlc(rows), cfg)
    assert t.outcome[0] == TP_FIRST and t.gross_return[0] == pytest.approx(0.05)
    assert t.outcome[3] == SL_FIRST and t.gross_return[3] == pytest.approx(-0.02)
    assert t.outcome[5] == AMBIGUOUS
    assert t.gross_return[5] == pytest.approx(-0.02)          # política "worst"
    assert t.outcome[6] == NONE and t.gross_return[6] == pytest.approx(100.2 / 100 - 1)
    # entrada en 7 (P=100.5, SL=98.49): la vela 9 abre en 95 -> llena en 95
    assert t.outcome[7] == SL_FIRST and t.exit_price[7] == pytest.approx(95)
    assert t.mfe[0] == pytest.approx(0.06) and t.mae[0] == pytest.approx(-0.01)
    assert t.outcome[-1] == -1                                 # horizonte incompleto


def test_costs_reduce_return():
    base = dict(MAX_HOLDING_BARS=3, FAVORABLE_OUTCOMES=())
    df = random_walk(200)
    g = build_outcome_table(df, ResearchConfig(**base))
    assert np.nanmax(g.net_return - g.gross_return) < 0


def test_probabilities_sum_to_one():
    df = random_walk(2000)
    cfg = ResearchConfig()
    t = build_outcome_table(df, cfg)
    s = compute_stats(np.arange(1, 1500), t, cfg, 2000)
    tot = s["P_TP_FIRST"] + s["P_SL_FIRST"] + s["P_NONE"] + s["P_AMBIGUOUS"]
    assert tot == pytest.approx(1.0)


def test_cooldown_and_purge():
    assert list(apply_cooldown(np.array([0, 1, 2, 3, 10, 11, 25]), 10)) == [0, 10, 25]
    sig = np.zeros(100, bool); sig[[5, 6, 7, 50, 89, 95]] = True
    det = detect_entries(sig, Segment("S", 0, 100), holding_bars=10, cooldown=5)
    # t <= 100-1-10 = 89 ; 6 y 7 caen por cooldown ; 95 por horizonte
    assert list(det.confirm_idx) == [5, 50, 89]
    assert det.n_dropped_horizon == 1 and det.n_dropped_cooldown == 2
    assert det.entry_idx.max() + 10 - 1 <= 99


def test_serialization_roundtrip():
    df = random_walk(800)
    st = FeatureStore(df)
    gen = ConditionGenerator(ResearchConfig(), st, slice(0, 500), np.random.default_rng(3))
    simple = gen.generate_simple(40)
    for c in simple + gen.generate_complex(simple, 40, 3):
        c2 = condition_from_dict(c.to_dict())
        assert c2.key == c.key
        assert np.array_equal(c2.evaluate(FeatureStore(df)), c.evaluate(st))


def test_reproducible_generation():
    df = random_walk(800)
    def keys(seed):
        st = FeatureStore(df)
        g = ConditionGenerator(ResearchConfig(), st, slice(0, 500), np.random.default_rng(seed))
        s = g.generate_simple(50)
        return [c.key for c in s + g.generate_complex(s, 50, 3)]
    assert keys(11) == keys(11)
    assert keys(11) != keys(12)


def test_until_exit_no_overlap():
    from trading_research.entry_detector import apply_until_exit
    off = np.zeros(100, dtype=int); off[6] = 3; off[10] = 29
    # entra en 6 (t=5), sale en la vela 9 -> la siguiente señal válida es t>=9
    assert list(apply_until_exit(np.array([5, 6, 9, 20, 45]), off)) == [5, 9, 45]
    # con datos reales: cada entrada ocurre después de la salida anterior
    df = random_walk(3000)
    cfg = ResearchConfig(MAX_HOLDING_BARS=30, COOLDOWN_MODE="until_exit")
    t = build_outcome_table(df, cfg)
    sig = np.ones(len(df), bool)
    det = detect_entries(sig, Segment("S", 0, len(df)), 30, 0, "until_exit", t.exit_offset)
    e = det.entry_idx
    exits = e + t.exit_offset[e]
    assert np.all(e[1:] > exits[:-1])
    assert np.all(e[1:] == exits[:-1] + 1)   # señal siempre activa -> re-entra justo después


def test_lift_filter():
    from trading_research.validation import passes_filters
    st = {"n_entries": 500, "P_TP_FIRST": 0.10, "mean_net_return": -0.002,
          "lift_P_TP_FIRST": 0.05, "lift_mean_net_return": 0.001}
    seg = 10000
    assert not passes_filters(st, ResearchConfig(FILTER_MODE="absolute"), seg)[0]
    assert passes_filters(st, ResearchConfig(FILTER_MODE="lift"), seg)[0]
    assert not passes_filters(st, ResearchConfig(FILTER_MODE="both"), seg)[0]
    st2 = dict(st, lift_mean_net_return=-0.001)
    ok, why = passes_filters(st2, ResearchConfig(FILTER_MODE="lift"), seg)
    assert not ok and any("lift_mean_net" in w for w in why)


def test_short_outcome_classification():
    cfg = ResearchConfig(POSITION_TYPE="SHORT", MAX_HOLDING_BARS=3, TP_PERCENT=0.05,
                         SL_PERCENT=0.02, COMMISSION_RATE=0, SLIPPAGE_RATE=0, SPREAD_RATE=0,
                         FAVORABLE_OUTCOMES=({"type": "reach", "p": 0.03, "bars": 2},))
    rows = [
        [100, 101, 99, 100],     # 0: entrada SHORT -> TP en barra 2 (Low 94 <= 95)
        [100, 101, 97, 98],      # 1
        [98, 99, 94, 95],        # 2
        [100, 103, 99.5, 102],   # 3: entrada -> SL inmediato (High 103 >= 102)
        [102, 103, 101, 102],    # 4
        [100, 103, 94, 100],     # 5: entrada -> AMBIGUOUS
        [100, 101, 99, 99.5],    # 6: entrada -> NONE
        [99.5, 100, 99, 99.7],
        [99.7, 100.5, 99.2, 99.4],
        [105, 106, 104, 105],    # 9: gap sobre el SL de la entrada en 7 (SL=101.49)
        [105, 106, 104, 105],
    ]
    t = build_outcome_table(ohlc(rows), cfg)
    assert t.outcome[0] == TP_FIRST and t.gross_return[0] == pytest.approx(0.05)
    assert t.outcome[3] == SL_FIRST and t.gross_return[3] == pytest.approx(-0.02)
    assert t.outcome[5] == AMBIGUOUS and t.gross_return[5] == pytest.approx(-0.02)
    assert t.outcome[6] == NONE and t.gross_return[6] == pytest.approx(1 - 99.4 / 100)
    assert t.outcome[7] == SL_FIRST and t.exit_price[7] == pytest.approx(105)   # llena en el gap
    assert t.mfe[0] == pytest.approx(0.06) and t.mae[0] == pytest.approx(-0.01)
    assert t.favorable["reach_0.03_in_2"][0] and not t.favorable["reach_0.03_in_2"][6]


def test_short_costs_symmetric():
    from trading_research.outcome_evaluator import apply_costs
    cfg = ResearchConfig(COMMISSION_RATE=0.001, SLIPPAGE_RATE=0.0005, SPREAD_RATE=0.0002)
    e, x = np.array([100.0]), np.array([100.0])
    long_c, short_c = apply_costs(e, x, cfg, "LONG")[0], apply_costs(e, x, cfg, "SHORT")[0]
    assert long_c < 0 and short_c < 0
    assert long_c == pytest.approx(short_c, rel=0.01)       # mismo costo en precio plano
    assert apply_costs(e, np.array([95.0]), cfg, "SHORT")[0] == pytest.approx(0.05 - 0.0032, abs=3e-4)


def test_walk_forward_folds():
    from trading_research.walk_forward import make_folds
    for anchored in (False, True):
        cfg = ResearchConfig(WF_N_FOLDS=4, WF_TRAIN_VAL_RATIO=3, WF_HOLDOUT_FRACTION=0.2,
                             WF_ANCHORED=anchored, MAX_HOLDING_BARS=30)
        folds, hold = make_folds(10000, cfg)
        assert len(folds) == 4 and hold.start == 8000 and hold.end == 10000
        assert folds[-1]["VALIDATION"].end == 8000
        for i, f in enumerate(folds):
            tr, va = f["TRAIN"], f["VALIDATION"]
            assert tr.end == va.start and tr.start >= 0      # VAL justo después de TRAIN
            if i:
                assert va.start == folds[i - 1]["VALIDATION"].end   # VALs contiguas, sin solaparse
            if anchored:
                assert tr.start == 0
            else:
                assert tr.n_bars == folds[0]["TRAIN"].n_bars


def test_cache_eviction_keeps_results():
    df = random_walk(2000)
    small = FeatureStore(df, max_feature_mb=0.05, max_signal_mb=0.01)
    big = FeatureStore(df)
    gen = ConditionGenerator(ResearchConfig(), big, slice(0, 1200), np.random.default_rng(5))
    simple = gen.generate_simple(80)
    conds = simple + gen.generate_complex(simple, 80, 3)
    for c in conds:
        assert np.array_equal(c.evaluate(small), c.evaluate(big))
    assert small._feature_bytes <= small.max_feature_bytes + 2000 * 8
