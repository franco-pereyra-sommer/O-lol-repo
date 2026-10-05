"""EXP-009: condiciones estructuradas contexto + disparador."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_core import random_walk  # noqa: E402

from trading_research.condition_generator import ConditionGenerator
from trading_research.conditions import (And, Compare, ContextTrigger, Cross, Kind, OccurredWithin,
                                         condition_from_dict)
from trading_research.config import ResearchConfig
from trading_research.features import (Constant, FeatureStore, HTFTrend, PriceField,
                                       RelativeVolatility)
from trading_research.lookahead import RecordingStore, check_conditions, check_operands
from trading_research.search import ResearchPipeline
from trading_research.entry_detector import Segment


def _cfg(side="LONG", **kw):
    return ResearchConfig(SEARCH_MODE="structured", MAX_CONDITION_DEPTH=3, POSITION_TYPE=side,
                          N_SIMPLE_CONDITIONS=300, MAX_HOLDING_BARS=40, TP_PERCENT=0.03,
                          SL_PERCENT=0.02, MIN_CASES_ABSOLUTE=5, MIN_CASES_FRACTION=0.0,
                          SAVE_EVENTS=False, FILTER_MODE="absolute", MIN_P_TP_FIRST=0.0,
                          MIN_EXPECTED_RETURN=-1.0, **kw)


def test_context_must_be_state_and_trigger_must_be_event():
    state = Compare(PriceField("Close"), ">", Constant(1.0))
    event = Cross(PriceField("Close"), Constant(1.0), "above")
    ContextTrigger(state, event)                      # ok
    with pytest.raises(ValueError, match="ESTADO"):
        ContextTrigger(event, event)                  # un evento no es un contexto
    with pytest.raises(ValueError, match="EVENTO"):
        ContextTrigger(state, state)                  # un estado no es un disparador


def test_active_context_does_not_create_one_entry_per_bar():
    """Contexto verdadero durante ~50 velas + un único cruce: una sola señal, no cincuenta."""
    n = 120
    close = np.r_[np.full(10, 100.0), np.linspace(101, 150, 50), np.full(60, 150.0)]
    idx = pd.date_range("2022-01-01", periods=n, freq="h", tz="UTC")
    df = pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close}, index=idx)
    st = FeatureStore(df)
    ctx = Compare(PriceField("Close"), ">", Constant(100.5))           # estado: vale 50+ velas
    trg = Cross(PriceField("Close"), Constant(125.0), "above")          # evento puntual
    cond = ContextTrigger(ctx, trg)
    assert ctx.evaluate(st).sum() > 50
    assert cond.evaluate(st).sum() == trg.evaluate(st).sum() == 1
    assert cond.kind == Kind.EVENT and cond.depth == 2
    assert cond.describe().startswith("CONTEXT[") and "] AND TRIGGER[" in cond.describe()
    # el contexto falso anula el disparador (misma vela t)
    never = ContextTrigger(Compare(PriceField("Close"), ">", Constant(1e9)), trg)
    assert never.evaluate(st).sum() == 0
    # ida y vuelta por diccionario
    again = condition_from_dict(cond.to_dict())
    assert again.key == cond.key and np.array_equal(again.evaluate(st), cond.evaluate(st))


def _classify_trigger(trig) -> str:
    if isinstance(trig, And):
        return "rsi_recovery"
    d = trig.describe()
    if "MACD" in d:
        return "macd_cross"
    if d.startswith("return("):
        return "ret_cross"
    return "rsi_cross"


@pytest.mark.parametrize("side", ["LONG", "SHORT"])
def test_generator_builds_only_direction_coherent_valid_structures(side):
    df = random_walk(3000, 3)
    cfg = _cfg(side)
    gen = ConditionGenerator(cfg, FeatureStore(df), slice(0, 1500), np.random.default_rng(1))
    conds = gen.generate_structured(400)
    assert len(conds) == 400 and len({c.key for c in conds}) == 400
    assert gen.stats["generated"] == 400 and gen.stats["attempts"] >= 400
    fams = set()
    for c in conds:
        assert isinstance(c, ContextTrigger)
        assert c.context.kind == Kind.STATE and c.trigger.kind == Kind.EVENT
        assert c.context.depth <= cfg.STRUCT_CONTEXT_MAX_DEPTH
        assert c.trigger.depth <= cfg.STRUCT_TRIGGER_MAX_DEPTH
        assert c.depth <= cfg.MAX_CONDITION_DEPTH
        fams.add(_classify_trigger(c.trigger))
        for leaf in c.context.leaves():                 # contexto: sólo operandos de régimen
            assert isinstance(leaf.left, (HTFTrend, RelativeVolatility))
            if isinstance(leaf.left, HTFTrend):         # contexto de tendencia coherente con la dirección
                assert leaf.op == (">" if side == "LONG" else "<")
        crosses = [l for l in c.trigger.leaves() if isinstance(l, Cross)]
        assert len(crosses) == 1
        assert crosses[0].direction == ("above" if side == "LONG" else "below")
    assert fams == {"rsi_cross", "macd_cross", "ret_cross", "rsi_recovery"}
    # recuperación del RSI: la zona extrema (OccurredWithin) es previa al cruce y los umbrales están ordenados
    rec = [c for c in conds if isinstance(c.trigger, And)]
    for c in rec:
        within = next(l for l in [c.trigger.a, c.trigger.b] if isinstance(l, OccurredWithin))
        cross = next(l for l in [c.trigger.a, c.trigger.b] if isinstance(l, Cross))
        zone = within.a
        assert zone.op == ("<" if side == "LONG" else ">")
        if side == "LONG":
            assert zone.right.value < cross.right.value
        else:
            assert cross.right.value < zone.right.value


def test_structured_requires_depth_two_and_respects_depth_limits():
    df = random_walk(2000, 4)
    with pytest.raises(ValueError, match="MAX_CONDITION_DEPTH"):
        ConditionGenerator(ResearchConfig(SEARCH_MODE="structured", MAX_CONDITION_DEPTH=1),
                           FeatureStore(df), slice(0, 1000), np.random.default_rng(0)).generate_structured(5)
    cfg = _cfg(STRUCT_CONTEXT_MAX_DEPTH=1, STRUCT_TRIGGER_MAX_DEPTH=1)
    gen = ConditionGenerator(cfg, FeatureStore(df), slice(0, 1000), np.random.default_rng(0))
    for c in gen.generate_structured(100):
        assert c.context.depth == 1 and c.trigger.depth == 1 and c.depth == 2
        assert not isinstance(c.trigger, And)


def test_structured_signals_are_subsets_of_trigger_events_and_are_causal():
    df = random_walk(3000, 6)
    cfg = _cfg("LONG")
    st = RecordingStore(df)
    gen = ConditionGenerator(cfg, st, slice(0, 1500), np.random.default_rng(2))
    conds = gen.generate_structured(120)
    n_active = 0
    for c in conds:
        sig, trg = c.evaluate(st), c.trigger.evaluate(st)
        assert not (sig & ~trg).any()                    # nunca hay entrada sin evento disparador
        n_active += int(sig.any())
    assert n_active > 20
    rng = np.random.default_rng(0)
    ks = [150, 421, 1203, 2500]
    assert sum(check_conditions(df, conds, ks, rng).values()) == 0
    assert sum(check_operands(df, st.operands, ks, rng).values()) == 0


def test_pipeline_structured_mode_budget_accounting_and_stage2_skipped():
    df = random_walk(2600, 8)
    segs = {"TRAIN": Segment("TRAIN", 0, 1500), "VALIDATION": Segment("VALIDATION", 1500, 2200)}
    res = ResearchPipeline(_cfg("SHORT"), df=df, segments=segs).run()
    m = res.meta
    assert m["search_mode"] == "structured"
    assert m["n_conditions_evaluated_complex"] == 0 and m["n_conditions_evaluated_simple"] == 300
    assert m["n_conditions_evaluated_total"] == 300
    g = m["generation"]
    assert g["generated"] == 300 and g["attempts"] == 300 + g["discarded_duplicate"]
    assert res.results["TRAIN"]["condition"].str.startswith("CONTEXT[").all()
    assert res.results["TRAIN"]["n_entries"].sum() > 0


def test_random_mode_reports_generation_stats_too():
    df = random_walk(2600, 8)
    segs = {"TRAIN": Segment("TRAIN", 0, 1500), "VALIDATION": Segment("VALIDATION", 1500, 2200)}
    cfg = ResearchConfig(MAX_CONDITION_DEPTH=1, N_SIMPLE_CONDITIONS=200, MAX_HOLDING_BARS=40,
                         MIN_CASES_ABSOLUTE=5, MIN_CASES_FRACTION=0.0, SAVE_EVENTS=False)
    res = ResearchPipeline(cfg, df=df, segments=segs).run()
    assert res.meta["search_mode"] == "random" and res.meta["generation"]["generated"] == 200
