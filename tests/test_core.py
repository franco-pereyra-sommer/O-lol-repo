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


def test_walk_forward_short_windows():
    from trading_research.walk_forward import make_folds
    cfg = ResearchConfig(WF_TRAIN_BARS=2500, WF_VAL_BARS=720, WF_HOLDOUT_FRACTION=0.1, MAX_HOLDING_BARS=100)
    folds, hold = make_folds(20000, cfg)
    n_dev = 20000 - hold.n_bars
    assert len(folds) == (n_dev - 2500) // 720
    assert folds[-1]["VALIDATION"].end <= n_dev
    for i, f in enumerate(folds):
        tr, va = f["TRAIN"], f["VALIDATION"]
        assert tr.n_bars == 2500 and va.n_bars == 720 and tr.end == va.start
        if i:
            assert va.start == folds[i - 1]["VALIDATION"].end
    with pytest.raises(ValueError):
        ResearchConfig(WF_TRAIN_BARS=2500).validate()


def test_pooled_t_matches_direct():
    from trading_research.walk_forward import pooled_t
    rng = np.random.default_rng(0)
    a, b = rng.normal(0.01, 0.02, 300), rng.normal(0.0, 0.03, 200)
    df = pd.DataFrame({"n_entries": [300, 200], "mean_net_return": [a.mean(), b.mean()],
                       "std_net_return": [a.std(ddof=1), b.std(ddof=1)]})
    x = np.concatenate([a, b])
    assert pooled_t(df) == pytest.approx(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))), rel=1e-9)


# ---------------------------------------------------------------------- #
# EXP-003: purga / embargo / dependencia temporal
# ---------------------------------------------------------------------- #
def _random_signal(n, p, seed):
    return np.random.default_rng(seed).random(n) < p


@pytest.mark.parametrize("mode,cd", [("fixed", 1), ("fixed", 15), ("until_exit", 1)])
def test_trade_label_window_stays_inside_segment(mode, cd):
    """Purga implícita: el intervalo [t, e+H-1] de CADA entrada cae dentro de su segmento,
    para cualquier cooldown. Es lo que impide que una operación de TRAIN use precios de VAL."""
    from trading_research.entry_detector import fits_in_segment, trade_intervals
    H = 40
    df = random_walk(3000, 3)
    tb = build_outcome_table(df, ResearchConfig(MAX_HOLDING_BARS=H))
    sig = _random_signal(3000, 0.2, 4)
    for seg in (Segment("TRAIN", 0, 1500), Segment("VALIDATION", 1500, 2100), Segment("TEST", 2100, 3000)):
        d = detect_entries(sig, seg, H, cd, mode, tb.exit_offset)
        assert len(d.entry_idx)
        assert fits_in_segment(d.entry_idx, H, seg).all()
        iv = trade_intervals(d.entry_idx, H, tb.exit_offset)
        assert (iv["exit_idx"] <= iv["info_end_idx"]).all() and iv["exit_idx"].max() <= seg.end - 1
        # y es exactamente el criterio: toda señal que sí cabe se conserva (modo fixed, cooldown 1)
        if (mode, cd) == ("fixed", 1):
            raw = np.flatnonzero(sig[seg.start:seg.end]) + seg.start
            assert set(d.confirm_idx) == {t for t in raw if t + 1 + H - 1 <= seg.end - 1}
            assert d.n_dropped_horizon == len(raw) - len(d.confirm_idx)


def _pipeline_cfg(**kw):
    return ResearchConfig(MAX_CONDITION_DEPTH=1, N_SIMPLE_CONDITIONS=300, MAX_HOLDING_BARS=40,
                          TP_PERCENT=0.03, SL_PERCENT=0.02, MIN_CASES_ABSOLUTE=5,
                          MIN_CASES_FRACTION=0.0, SAVE_EVENTS=False, FILTER_MODE="absolute",
                          MIN_P_TP_FIRST=0.0, MIN_EXPECTED_RETURN=-1.0, **kw)


def test_train_results_do_not_depend_on_future_prices():
    """Cambiar TODOS los precios posteriores al fin de TRAIN no puede alterar nada de lo que
    se ve en TRAIN (condiciones generadas, entradas, retornos, selección)."""
    from trading_research.search import ResearchPipeline
    n, cut = 2600, 1500
    a = random_walk(n, 11)
    b = a.copy()
    other = random_walk(n, 99)
    scale = a["Close"].iloc[cut - 1] / other["Close"].iloc[cut - 1]
    for col in ("Open", "High", "Low", "Close"):
        b.iloc[cut:, b.columns.get_loc(col)] = other[col].to_numpy()[cut:] * scale
    segs = {"TRAIN": Segment("TRAIN", 0, cut), "VALIDATION": Segment("VALIDATION", cut, 2200)}
    ra = ResearchPipeline(_pipeline_cfg(), df=a, segments=segs).run()
    rb = ResearchPipeline(_pipeline_cfg(), df=b, segments=segs).run()
    ta = ra.results["TRAIN"].sort_values("condition_id").reset_index(drop=True)
    tb_ = rb.results["TRAIN"].sort_values("condition_id").reset_index(drop=True)
    assert len(ta) > 50
    cols = ["condition_id", "n_entries", "n_dropped_horizon", "mean_net_return", "P_TP_FIRST",
            "mean_MFE", "mean_MAE", "passed"]
    pd.testing.assert_frame_equal(ta[cols], tb_[cols])
    assert ra.baselines["TRAIN"]["mean_net_return"] == rb.baselines["TRAIN"]["mean_net_return"]
    # el cambio sí es visible en VALIDATION (control de que el test puede fallar)
    assert ra.baselines["VALIDATION"]["mean_net_return"] != rb.baselines["VALIDATION"]["mean_net_return"]

    # Control negativo: SIN purga por horizonte (H=0) las entradas del final de TRAIN sí cambiarían.
    cfg = _pipeline_cfg()
    ta_, tb2 = build_outcome_table(a, cfg), build_outcome_table(b, cfg)
    e = np.arange(cut - cfg.MAX_HOLDING_BARS, cut)
    assert not np.allclose(ta_.net_return[e], tb2.net_return[e], equal_nan=True)


def test_validation_labels_use_only_validation_prices():
    """Simétrico: una operación del COMIENZO de VAL no usa precios de TRAIN en su resultado
    (sólo el indicador que genera la señal puede mirar atrás, lo cual es causal y legítimo)."""
    cfg = _pipeline_cfg()
    a = random_walk(2600, 5)
    b = a.copy()
    cut = 1500
    for col in ("Open", "High", "Low", "Close"):
        b.iloc[:cut, b.columns.get_loc(col)] = a[col].to_numpy()[:cut] * 1.37
    ta, tb_ = build_outcome_table(a, cfg), build_outcome_table(b, cfg)
    e = np.arange(cut, 2200)
    # gross_return/outcome no cambian (sólo la volatilidad usada en costos puede mirar atrás)
    assert np.array_equal(ta.outcome[e], tb_.outcome[e])
    assert np.allclose(ta.gross_return[e], tb_.gross_return[e])


def test_overlap_inflates_t_but_until_exit_does_not():
    """Simulación de nulidad (señales aleatorias, sin ventaja): con cooldown 1 y horizonte 50 las
    operaciones se solapan y el t naive rechaza H0 mucho más del 5 %; con until_exit no."""
    H = 50
    cfg = ResearchConfig(MAX_HOLDING_BARS=H, TP_PERCENT=0.05, SL_PERCENT=0.05)
    seg = Segment("S", 0, 5000)
    ts = {"fixed1": [], "until_exit": []}
    for seed in range(40):
        df = random_walk(5000, seed)
        tb = build_outcome_table(df, cfg)
        sig = _random_signal(5000, 0.1, seed + 1000)
        for k, (mode, cd) in {"fixed1": ("fixed", 1), "until_exit": ("until_exit", 1)}.items():
            d = detect_entries(sig, seg, H, cd, mode, tb.exit_offset)
            r = tb.gross_return[d.entry_idx]
            ts[k].append(r.mean() / (r.std(ddof=1) / np.sqrt(len(r))))
    assert np.std(ts["fixed1"]) > 1.4          # inflado (debería ser ~1)
    assert np.mean(np.abs(ts["fixed1"]) > 2) > 0.15   # falsos positivos >> 5 %
    assert np.mean(np.abs(ts["until_exit"]) > 2) <= 0.05


def test_fold_level_t():
    from trading_research.walk_forward import fold_level_t
    s = pd.DataFrame({"oos_pooled_mean_net": [0.01, 0.03, -0.01, np.nan, 0.02]})
    x = np.array([0.01, 0.03, -0.01, 0.02])
    assert fold_level_t(s) == pytest.approx(x.mean() / (x.std(ddof=1) / 2))
    assert np.isnan(fold_level_t(pd.DataFrame({"oos_pooled_mean_net": [0.01]})))


def test_fixed_cooldown_shorter_than_horizon_warns():
    with pytest.warns(UserWarning, match="until_exit"):
        ResearchConfig(COOLDOWN_MODE="fixed", MIN_BARS_BETWEEN_SAME_CONDITION_ENTRIES=15,
                       MAX_HOLDING_BARS=100).validate()
    ResearchConfig(COOLDOWN_MODE="until_exit").validate()


def test_walk_forward_oos_series_matches_fold_results(tmp_path):
    """La serie OOS por vela es consistente con los resultados por condición: la suma de retornos
    netos y el conteo de entradas coinciden, y sólo hay datos en las velas de VALIDATION."""
    from trading_research.walk_forward import make_folds, run_walk_forward, save_walk_forward
    df = random_walk(3500, 21)
    cfg = _pipeline_cfg(WF_TRAIN_BARS=800, WF_VAL_BARS=300, WF_HOLDOUT_FRACTION=0.1, WALK_FORWARD=True)
    wf = run_walk_forward(cfg, df)
    s = wf.oos_series
    folds, _ = make_folds(len(df), cfg)
    cov = np.zeros(len(df), dtype=bool)
    for f in folds:
        cov[f["VALIDATION"].slice] = True
    assert np.array_equal(s["covered"], cov)
    assert s["cnt"][~cov].sum() == 0 and s["sum_typical"][~cov].sum() == 0
    tot_n = sum(int(r.results["VALIDATION"]["n_entries"].sum()) for r in wf.folds)
    tot_sum = sum(float((r.results["VALIDATION"]["n_entries"] * r.results["VALIDATION"]["mean_net_return"]).sum())
                  for r in wf.folds)
    assert tot_n > 1000 and s["cnt"].sum() == tot_n
    assert s["sum_typical"].sum() == pytest.approx(tot_sum, rel=1e-9)
    assert np.isfinite(wf.aggregate["oos_hac_t_3H"])
    out = save_walk_forward(wf, tmp_path)
    z = np.load(out / "oos_series.npz")
    assert np.array_equal(z["cnt"], s["cnt"]) and "base_typical" in z.files


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


def test_execution_cost_model():
    from trading_research.costs import (EXIT_SL, EXIT_TIME, EXIT_TP, MarketContext,
                                        build_cost_model)
    df = random_walk(300)
    ctx = MarketContext(df)
    cfg = ResearchConfig()
    P, X = np.array([100.0, 100.0, 100.0]), np.array([105.0, 98.0, 101.0])
    kind = np.array([EXIT_TP, EXIT_SL, EXIT_TIME])
    idx = np.array([50, 50, 50])
    typ = build_cost_model("typical", cfg)
    net = typ.net_return("LONG", P, X, kind, idx, idx + 5, ctx)
    a = 0.0001 / 2 + 0.0002          # medio spread + slippage (típico)
    f = 0.001
    p_e = 100 * (1 + a)
    assert net[0] == pytest.approx(105 * (1 - f) / (p_e * (1 + f)) - 1)          # TP maker: sin spread/slip
    assert net[1] == pytest.approx(98 * (1 - a) * (1 - f) / (p_e * (1 + f)) - 1)  # SL stop de mercado
    # orden esperable de escenarios
    nets = {sc: build_cost_model(sc, cfg).net_return("LONG", P, X, kind, idx, idx + 5, ctx)
            for sc in ("optimistic", "typical", "conservative")}
    assert np.all(nets["optimistic"] > nets["typical"]) and np.all(nets["typical"] > nets["conservative"])
    # SHORT con precio plano: pierde sólo los costos
    sh = typ.net_return("SHORT", P[:1], P[:1], np.array([EXIT_TIME]), idx[:1], idx[:1], ctx)[0]
    lo = typ.net_return("LONG", P[:1], P[:1], np.array([EXIT_TIME]), idx[:1], idx[:1], ctx)[0]
    assert sh < 0 and sh == pytest.approx(lo, rel=0.01)


def test_volatility_slippage_is_causal():
    from trading_research.costs import MarketContext, VolatilitySlippage
    df = random_walk(400)
    m = VolatilitySlippage(0.0003, 0.05)
    full = m.slippage(np.arange(400), MarketContext(df))
    trunc = m.slippage(np.arange(250), MarketContext(df.iloc[:250]))
    assert np.allclose(full[:250][20:], trunc[20:])   # no depende de velas posteriores


def test_outcome_table_has_cost_scenarios():
    df = random_walk(500)
    t = build_outcome_table(df, ResearchConfig(MAX_HOLDING_BARS=20))
    assert set(t.net_by_scenario) == {"optimistic", "typical", "conservative"}
    assert np.allclose(t.net_return, t.net_by_scenario["typical"], equal_nan=True)
    ok = np.isfinite(t.net_return)
    assert np.all(t.net_by_scenario["optimistic"][ok] >= t.net_by_scenario["conservative"][ok])
