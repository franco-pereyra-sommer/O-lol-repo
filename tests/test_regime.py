"""EXP-008: features de régimen (tendencia 4h/1D, volatilidad relativa): causalidad y alineación."""
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_core import random_walk  # noqa: E402

from trading_research.condition_generator import ConditionGenerator
from trading_research.config import ResearchConfig
from trading_research.features import (FeatureStore, HTFTrend, RelativeVolatility,
                                       operand_from_dict)
from trading_research.lookahead import RecordingStore, check_conditions, check_operands

KS = [150, 421, 777, 1203, 1998, 2500]     # cortes en horas variadas del día (no sólo múltiplos de 4)


def _ops():
    return {o.key: o for o in (HTFTrend("4h", 6), HTFTrend("4h", 40), HTFTrend("1D", 5),
                               HTFTrend("1D", 30), RelativeVolatility(5, 60), RelativeVolatility(20, 200))}


def test_regime_operands_have_no_lookahead_truncation_and_perturbation():
    df = random_walk(3000, 4)
    ops = _ops()
    rng = np.random.default_rng(0)
    assert sum(check_operands(df, ops, KS, rng).values()) == 0


def test_regime_operands_causal_with_unaligned_start_gaps_and_timezones():
    base = random_walk(3000, 5)
    # inicio a las 17:00 (no alineado a velas de 4h/1D), huecos de datos y otra zona horaria
    idx = pd.date_range("2020-01-01 17:00", periods=len(base), freq="h", tz="UTC")
    df = base.copy()
    df.index = idx
    keep = np.ones(len(df), dtype=bool)
    keep[[310, 311, 312, 900, 1700, 1701]] = False          # velas faltantes
    df = df[keep]
    ops = _ops()
    ks = [200, 600, 1111, 1700, 2400]
    assert sum(check_operands(df, ops, ks, np.random.default_rng(1)).values()) == 0
    # la zona horaria del índice no cambia nada (la alineación usa la época UTC)
    dz = df.copy()
    dz.index = df.index.tz_convert("America/Argentina/Buenos_Aires")
    dn = df.copy()
    dn.index = df.index.tz_localize(None)                    # sin zona: se interpreta como UTC
    for op in ops.values():
        a = op.compute(df)
        assert np.array_equal(a, op.compute(dz), equal_nan=True)
        assert np.array_equal(a, op.compute(dn), equal_nan=True)


def test_htf_trend_uses_only_completed_higher_candles_known_values():
    """4h: en las horas 00,01,02 se usa la vela 4h anterior ya cerrada; en la hora 03 (última de la vela,
    cuyo cierre es el de esa misma hora) ya se usa la vela que acaba de cerrar."""
    n = 24 * 6
    idx = pd.date_range("2021-03-01 00:00", periods=n, freq="h", tz="UTC")
    close = 100.0 + np.arange(n) * 0.5 + (np.arange(n) % 7)
    df = pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close}, index=idx)
    v = HTFTrend("4h", 3).compute(df)
    c4 = close[3::4]                                         # cierre de cada vela 4h (horas 3, 7, 11…)
    sma = np.array([np.nan, np.nan] + [c4[i - 2:i + 1].mean() for i in range(2, len(c4))])
    trend = c4 / sma - 1
    for h in range(n):
        k = h // 4 if h % 4 == 3 else h // 4 - 1             # última vela 4h completa al cierre de la hora h
        exp = trend[k] if k >= 0 else np.nan
        assert (np.isnan(v[h]) and np.isnan(exp)) or v[h] == pytest.approx(exp), (h, v[h], exp)
    # entre el cierre de una vela 4h y el siguiente el valor no cambia; cambia justo en la hora 03
    assert v[16] == v[17] == v[18] and v[19] != v[18]
    d = HTFTrend("1D", 2).compute(df)
    assert np.isnan(d[0]) and np.isnan(d[46])                 # aún no hay 2 velas diarias completas
    assert d[48] == d[50] == d[70] and d[71] != d[70]         # cambia sólo a las 23:00 (cierra el día)


@dataclass(frozen=True, repr=False)
class _BadHTF(HTFTrend):
    """Canario: usa el cierre de la vela superior que CONTIENE a la vela actual (aún abierta)."""
    def compute(self, df):
        ts = df.index.as_unit("ns").asi8.astype("int64")
        tf_ns = int(pd.Timedelta(self.tf).value)
        bucket = ts // tf_ns
        last_close = df.groupby(bucket)["Close"].transform("last").to_numpy()   # mira velas futuras del bucket
        return last_close / df["Close"].rolling(self.n).mean().to_numpy() - 1


def test_canary_open_higher_candle_leak_is_detected():
    df = random_walk(3000, 6)
    bad = _BadHTF("4h", 6)
    assert sum(check_operands(df, {bad.key: bad}, KS, np.random.default_rng(2)).values()) > 0


def test_generator_regime_flag_off_is_unchanged_and_on_adds_regime_operands():
    df = random_walk(3000, 1)
    golden = ['(Xabove:ret:13|ret:14)', '(candle:upper_wick_ratio>candle:body_ratio)',
              '(ind:RSI(30,):value>const:41.9)', '(Xbelow:ret:50|const:0.0662)',
              '(Xabove:ind:RSI(21,):value|ind:RSI(17,):value)', '(Xbelow:ind:RSI(29,):value|const:42.8)']
    gen = ConditionGenerator(ResearchConfig(), FeatureStore(df), slice(0, 1500), np.random.default_rng(5))
    assert [c.key for c in gen.generate_simple(6)] == golden      # misma semilla -> mismas condiciones que antes

    cfg = ResearchConfig(REGIME_FEATURES=True, MAX_CONDITION_DEPTH=3)
    st = RecordingStore(df)
    gen = ConditionGenerator(cfg, st, slice(0, 1500), np.random.default_rng(7))
    simple = gen.generate_simple(600)
    conds = simple + gen.generate_complex(simple[:150], 200, 3)
    sigs = [c.evaluate(st) for c in conds]
    kinds = {type(o).__name__ for o in st.operands.values()}
    assert {"HTFTrend", "RelativeVolatility"} <= kinds
    assert {o.tf for o in st.operands.values() if isinstance(o, HTFTrend)} == {"4h", "1D"}
    assert any(s.any() for s in sigs)
    # las condiciones con régimen también son causales a nivel de señal
    reg = [c for c in conds if "HTFTrend" in c.describe() or "ATR(" in c.describe() and "/ATR(" in c.describe()]
    assert len(reg) > 30
    assert sum(check_conditions(df, reg[:80], [400, 1300, 2300], np.random.default_rng(3)).values()) == 0


def test_regime_operands_roundtrip_dict():
    for op in _ops().values():
        assert operand_from_dict(op.to_dict()) == op
