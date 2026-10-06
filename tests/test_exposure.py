"""EXP-013: reglas de exposición (comprado/efectivo con revisión diaria): causalidad, mecánica y contabilidad."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from test_core import random_walk  # noqa: E402

from trading_research.config import ResearchConfig
from trading_research.costs import build_cost_model
from trading_research.entry_detector import Segment
from trading_research.exposure import (EXP013_RULES, ExposureRule, daily_positions, day_starts,
                                       evaluate_rule, segment_bar_returns, summarize)
from trading_research.features import Constant
from trading_research.lookahead import perturb_future, truncate
from trading_research.walk_forward import make_folds

CFG = ResearchConfig()
COSTS = {k: build_cost_model(k, CFG) for k in ("typical", "conservative")}


def _gappy(n=4000, seed=3):
    """Inicio no alineado (17:00), huecos de datos (incluida una vela de 00:00) y zona horaria distinta de UTC."""
    df = random_walk(n, seed)
    df.index = pd.date_range("2020-01-01 17:00", periods=n, freq="h", tz="UTC")
    keep = np.ones(n, dtype=bool)
    keep[[310, 311, 312, 7 + 24 * 40, 1700, 1701, 2999]] = False      # 7 + 24*40 = una vela de 00:00 UTC
    df = df[keep]
    df.index = df.index.tz_convert("America/Argentina/Buenos_Aires")
    return df


def test_positions_have_no_lookahead_truncation_and_perturbation():
    """La posición de las velas 0..k no cambia al truncar en k; la de 0..k+1 no cambia al alterar los
    precios posteriores a k (la posición de k+1 se decide al cierre de k)."""
    df = _gappy()
    rng = np.random.default_rng(0)
    # horas del día variadas y, sobre todo, la vela anterior a un cambio de día (donde se decide la posición)
    before_day = [int(j) - 1 for j in np.flatnonzero(day_starts(df.index)) if 2450 <= j < len(df) - 2][:25]
    ks = [2450, 2471, 2500, 2617, 3000, 3333, len(df) - 3] + before_day
    for rule in EXP013_RULES:
        full = daily_positions(df, rule.state(df))
        for k in ks:
            tr = truncate(df, k)
            assert np.array_equal(full[:k + 1], daily_positions(tr, rule.state(tr))), (rule.name, k)
            pt = perturb_future(df, k, rng)
            assert np.array_equal(full[:k + 2], daily_positions(pt, rule.state(pt))[:k + 2]), (rule.name, k)


def test_lookahead_canary_is_detected():
    """Una regla que mira el cierre SIGUIENTE debe romper la invariancia por perturbación (el test sirve)."""
    df = random_walk(800, 1)

    class Peek:
        label = "peek"

        def compute(self, d):
            c = d["Close"].to_numpy(float)
            return np.r_[c[1:] / c[:-1] - 1.0, np.nan]

    rule = ExposureRule("peek", Peek(), ">", 0.0)
    full = daily_positions(df, rule.state(df))
    broken = 0
    for k in range(400, 700):
        pt = perturb_future(df, k, np.random.default_rng(k))
        broken += not np.array_equal(full[:k + 2], daily_positions(pt, rule.state(pt))[:k + 2])
    assert broken > 0


def test_position_changes_only_on_first_bar_of_utc_day():
    df = _gappy()
    starts = day_starts(df.index)
    utc = df.index.tz_convert("UTC")
    first_of_day = np.r_[False, utc.date[1:] != utc.date[:-1]]
    assert np.array_equal(starts, first_of_day)
    st = np.random.default_rng(5).random(len(df)) > 0.5         # estado arbitrario hora por hora
    pos = daily_positions(df, st)
    changes = np.flatnonzero(np.diff(pos.astype(int)) != 0) + 1
    assert starts[changes].all()
    j = np.flatnonzero(starts)
    assert np.array_equal(pos[j], st[j - 1].astype(np.int8))   # = estado al cierre de la vela anterior
    assert (pos[:j[0]] == 0).all()                               # efectivo antes del primer cambio de día
    # la zona horaria del índice no influye
    dn = df.copy()
    dn.index = df.index.tz_convert("UTC").tz_localize(None)
    assert np.array_equal(daily_positions(dn, st), pos)


def _windows(n, k=4, size=500, start=200):
    return [Segment("VALIDATION", start + i * size, start + (i + 1) * size) for i in range(k)]


def test_always_long_has_zero_lift_and_pays_one_entry_and_one_exit():
    df = random_walk(3000, 2)
    always = ExposureRule("always", Constant(1.0), ">", 0.0)
    pos = daily_positions(df, always.state(df))
    w = _windows(len(df))
    res = evaluate_rule(df, "always", pos, w, COSTS)
    # la primera ventana empieza después del primer cambio de día: comprado todo el período
    assert res.exposure == 1.0
    assert np.allclose(res.gross_lift(), 0.0)
    assert res.switches.sum() == 2 and res.switches[0] == 1 and res.switches[-1] == 1
    s = summarize(res)
    assert s["n_entries"] == 1 and abs(s["gross_lift_sum"]) < 1e-15
    # lift neto = − (costo de entrar + costo de salir)
    assert np.isclose(s["net_lift_sum_typical"], -res.cost["typical"].sum())
    assert not s["evaluable"]                                   # ē = 1 y menos de 30 entradas


def test_each_switch_pays_exactly_one_side():
    df = random_walk(3000, 4)
    w = _windows(len(df))
    pos = np.zeros(len(df), dtype=np.int8)
    pos[260:400] = 1        # entra y sale dentro de la ventana 0
    pos[690:760] = 1        # cruza el borde 0/1 (700): no se paga nada en el borde
    pos[2150:] = 1          # sigue comprado al final: liquidación en la última vela
    res = evaluate_rule(df, "x", pos, w, COSTS)
    paid = res.bars[res.switches > 0]
    assert list(paid) == [260, 400, 690, 760, 2150, 2199]
    one_side = (COSTS["typical"].fees.rate("taker") + COSTS["typical"].spread.half_spread(np.array([0]), None)[0]
                + COSTS["typical"].slippage.slippage(np.array([0]), None)[0])
    assert np.isclose(one_side, 0.00125)
    assert np.isclose(res.cost["typical"].sum(), 6 * 0.00125)
    assert res.n_entries == 3


def test_window_returns_stay_inside_segment():
    """La última vela de cada ventana se valúa a su Close: cambiar precios fuera de la ventana no cambia nada."""
    df = random_walk(1500, 6)
    seg = Segment("VALIDATION", 300, 900)
    r = segment_bar_returns(df, seg)
    d2 = df.copy()
    for c in ("Open", "High", "Low", "Close"):
        d2.iloc[seg.end:, d2.columns.get_loc(c)] *= 3.0
        d2.iloc[:seg.start, d2.columns.get_loc(c)] *= 0.5
    assert np.array_equal(r, segment_bar_returns(d2, seg))
    o = df["Open"].to_numpy()
    assert np.isclose(r[0], o[301] / o[300] - 1)
    assert np.isclose(r[-1], df["Close"].iloc[899] / o[899] - 1)
    # suma de los retornos de un tramo comprado = movimiento Open→Close del tramo (sin reinversión, aprox.)
    assert len(r) == seg.n_bars


def test_net_lift_is_rule_minus_constant_exposure_benchmark():
    df = random_walk(3000, 8)
    rule = EXP013_RULES[0]
    w = _windows(len(df), k=5, size=500, start=500)
    res = evaluate_rule(df, rule.name, daily_positions(df, rule.state(df)), w, COSTS)
    e = res.exposure
    assert 0 < e < 1
    d = res.net_lift("typical")
    assert np.allclose(d, res.pos * res.r - res.cost["typical"] - e * res.r)
    s = summarize(res, threshold=3.05)
    assert np.isclose(s["net_lift_sum_typical"], s["rule_net_sum_typical"] - s["benchmark_sum"])
    assert np.isclose(sum(s["block_net_lift"]), s["net_lift_sum_typical"])
    assert set(s["criteria"]) == {"C1_t_windows_net_lift", "C2_hac_net_lift_ge_2", "C3_blocks_4_of_5",
                                  "C4_net_lift_conservative_gt0", "C5_rule_net_gt0_typical_and_conservative",
                                  "C6_min_entries"}


def test_windows_are_the_b0_validation_windows():
    """EXP-013 usa exactamente las VALIDATION de B0 (TRAIN 2.500 / VAL 720, holdout 15 %) sobre 79.909 velas."""
    cfg = ResearchConfig(WF_TRAIN_BARS=2500, WF_VAL_BARS=720, WF_HOLDOUT_FRACTION=0.15)
    folds, hold = make_folds(79909, cfg)
    v = [f["VALIDATION"] for f in folds]
    assert len(v) == 90 and v[0].start == 3123 and v[-1].end == 67923 == hold.start
    assert all(a.end == b.start for a, b in zip(v[:-1], v[1:]))
