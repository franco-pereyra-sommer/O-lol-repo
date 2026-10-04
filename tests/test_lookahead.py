"""EXP-006: la prueba de look-ahead a nivel de señales detecta fugas reales y no da falsos positivos."""
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_core import random_walk  # noqa: E402

from trading_research.condition_generator import ConditionGenerator
from trading_research.conditions import Compare
from trading_research.config import ResearchConfig
from trading_research.features import Constant, Indicator, Operand, PriceField
from trading_research.lookahead import (RecordingStore, check_conditions, check_entries,
                                        check_operands, startup_sensitivity)


@dataclass(frozen=True, repr=False)
class _Leaky(Operand):
    kind: str

    @property
    def key(self): return f"leaky:{self.kind}"
    @property
    def label(self): return f"leaky_{self.kind}"
    @property
    def scale(self): return "price"
    def to_dict(self): return {"type": "leaky", "kind": self.kind}

    def compute(self, df):
        c = df["Close"]
        if self.kind == "shift_neg":          # el cierre de la vela SIGUIENTE
            return c.shift(-1).to_numpy()
        if self.kind == "centered_sma":       # media centrada: usa 5 velas futuras
            return c.rolling(11, center=True, min_periods=11).mean().to_numpy()
        if self.kind == "global_z":           # z-score con media/desvío de TODA la muestra
            return (c / c.mean()).to_numpy()
        if self.kind == "future_max":         # máximo de las próximas 5 velas
            return c[::-1].rolling(5, min_periods=1).max()[::-1].to_numpy()
        raise ValueError(self.kind)


KINDS = ["shift_neg", "centered_sma", "global_z", "future_max"]
KS = [400, 900, 1500, 2100]


def _real_conditions(df, n_simple=200, n_complex=150):
    cfg = ResearchConfig(MAX_CONDITION_DEPTH=3)
    store = RecordingStore(df)
    gen = ConditionGenerator(cfg, store, slice(0, 1500), np.random.default_rng(3))
    simple = gen.generate_simple(n_simple)
    conds = simple + gen.generate_complex(simple, n_complex, 3)
    sigs = {c.key: c.evaluate(store) for c in conds}
    return conds, store.operands, sigs


def test_real_operands_conditions_and_entries_have_no_lookahead():
    df = random_walk(2600, 8)
    conds, operands, sigs = _real_conditions(df)
    assert len(operands) > 30
    rng = np.random.default_rng(0)
    assert sum(check_operands(df, operands, KS, rng).values()) == 0
    assert sum(check_conditions(df, conds, KS, rng).values()) == 0
    for mode, cd in (("until_exit", 1), ("fixed", 15)):
        cfg = ResearchConfig(MAX_HOLDING_BARS=40, COOLDOWN_MODE=mode,
                             MIN_BARS_BETWEEN_SAME_CONDITION_ENTRIES=cd)
        sub = dict(list(sigs.items())[:120])
        assert sum(check_entries(df, sub, cfg, KS).values()) == 0


@pytest.mark.parametrize("kind", KINDS)
def test_leaky_operands_are_detected_at_operand_and_condition_level(kind):
    df = random_walk(2600, 9)
    op = _Leaky(kind)
    rng = np.random.default_rng(1)
    assert sum(check_operands(df, {op.key: op}, KS, rng).values()) > 0
    right = Constant(1.0) if kind == "global_z" else PriceField("Close")
    cond = Compare(op, ">", right)
    assert sum(check_conditions(df, [cond], KS, rng).values()) > 0


def test_global_statistic_leak_is_only_caught_when_future_is_perturbed_not_when_cut_short():
    """Un indicador normalizado con estadísticas de toda la muestra cambia al truncar, y el modo
    `perturb` lo detecta también sin cambiar el largo del arreglo: ambos modos son necesarios en
    general; acá comprobamos que `perturb` solo ya lo detecta."""
    df = random_walk(2600, 10)
    op = _Leaky("global_z")
    f = check_operands(df, {op.key: op}, KS, np.random.default_rng(2), modes=("perturb",))
    assert f[op.key] > 0


def test_leaky_signal_is_detected_at_entry_level():
    df = random_walk(2600, 11)
    def leaky(d):                              # "sube la vela siguiente": señal con look-ahead
        c = d["Close"].to_numpy()
        sig = np.zeros(len(d), dtype=bool)
        sig[:-1] = c[1:] > c[:-1]
        return sig

    def honest(d):                             # "subió la vela anterior": causal
        c = d["Close"].to_numpy()
        sig = np.zeros(len(d), dtype=bool)
        sig[1:] = c[1:] > c[:-1]
        return sig
    cfg = ResearchConfig(MAX_HOLDING_BARS=40, COOLDOWN_MODE="until_exit")
    out = check_entries(df, {"leaky": leaky, "honest": honest}, cfg, KS)
    assert out["leaky"] > 0 and out["honest"] == 0


def test_startup_sensitivity_flags_recursive_but_not_windowed_indicators():
    df = random_walk(6000, 12)
    ops = {"sma": Indicator("SMA", (20,)), "ema": Indicator("EMA", (50,)),
           "rsi": Indicator("RSI", (14,))}
    out = startup_sensitivity(df, ops, starts=[100, 777], after=300, rtol=1e-12)
    assert out["sma"] == 0                      # ventana finita: no depende del arranque
    assert out["ema"] > 0 and out["rsi"] > 0    # recursivos: dependen (decaen, pero no exactamente)
