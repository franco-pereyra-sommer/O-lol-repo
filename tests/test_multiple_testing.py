"""EXP-004: simulaciones que justifican y validan las correcciones por múltiples hipótesis."""
import numpy as np
import pytest

from trading_research.entry_detector import Segment, fits_in_segment
from trading_research.multiple_testing import (condition_block_stats, cscv_pbo, entry_series,
                                               reality_check, stationary_bootstrap_weights)


def _ma_noise(rng, T, K, w):
    z = rng.normal(0, 1, (T + w - 1, K))
    c = np.cumsum(z, 0)
    return (c[w - 1:] - np.vstack([np.zeros((1, K)), c[:-w]])) / np.sqrt(w)


def test_best_of_many_noise_rules_looks_significant_but_reality_check_is_calibrated():
    """El problema: entre K=200 reglas de ruido puro, la mejor tiene t > 2 siempre (selección);
    White RC rechaza ~5 % (no más de 20 % con 40 repeticiones)."""
    rng = np.random.default_rng(0)
    T, K, R = 500, 200, 40
    naive, rc = [], []
    for r in range(R):
        x = rng.normal(0, 1, (T, K))
        naive.append((x.mean(0) / (x.std(0, ddof=1) / np.sqrt(T))).max())
        rc.append(reality_check(x, n_boot=300, mean_block=1, seed=r)["p_value"] < 0.05)
    assert np.mean(np.array(naive) > 2) == 1.0          # "descubrimiento" garantizado por azar
    assert np.mean(rc) <= 0.2


def test_reality_check_detects_a_real_edge():
    rng = np.random.default_rng(1)
    rej = []
    for r in range(20):
        x = rng.normal(0, 1, (500, 200))
        x[:, 7] += 0.25                                  # una regla con ventaja real
        res = reality_check(x, n_boot=300, mean_block=1, seed=r)
        rej.append(res["p_value"] < 0.05 and res["best"] == 7)
    assert np.mean(rej) >= 0.9


def test_reality_check_needs_blocks_when_series_is_dependent():
    """Series de operaciones solapadas son dependientes (MA(20)): con bloques de largo 1 el test
    rechaza casi siempre bajo H0; con bloques largos (>= 4x la dependencia) y T >> bloque, ~5 %."""
    rng = np.random.default_rng(2)
    iid_block, long_block = [], []
    for r in range(30):
        x = _ma_noise(rng, 2000, 30, 20)
        iid_block.append(reality_check(x, n_boot=200, mean_block=1, seed=r)["p_value"] < 0.05)
        long_block.append(reality_check(x, n_boot=200, mean_block=80, seed=r)["p_value"] < 0.05)
    assert np.mean(iid_block) > 0.5
    assert np.mean(long_block) <= 0.2


def test_reality_check_ignores_rules_that_never_trade_and_bootstrap_weights_sum_to_one():
    x = np.random.default_rng(3).normal(0, 1, (300, 5))
    x[:, 2] = 0.0
    res = reality_check(x, n_boot=100, mean_block=5)
    assert res["n_live"] == 4 and res["best"] != 2
    w = stationary_bootstrap_weights(300, 50, 10, np.random.default_rng(0))
    assert w.shape == (50, 300) and np.allclose(w.sum(1), 1.0)


def test_pbo_is_about_half_for_noise_and_zero_for_a_real_edge():
    rng = np.random.default_rng(4)
    S, N = 16, 100
    cnt = np.full((S, N), 50.0)
    pbos = [cscv_pbo(rng.normal(0, 0.02, (S, N)) * np.sqrt(50), cnt)["pbo"] for _ in range(6)]
    assert 0.3 <= np.mean(pbos) <= 0.7
    sm = rng.normal(0, 0.02, (S, N)) * np.sqrt(50)
    sm[:, 0] += 50 * 0.01                                # ventaja estable en todos los bloques
    out = cscv_pbo(sm, cnt)
    assert out["pbo"] < 0.05 and out["mean_oos_best"] > 0


def test_pbo_selected_noise_degrades_out_of_sample():
    """El mejor IN-sample de ruido puro es positivo IN pero ~0 OUT: la degradación que mide PBO."""
    rng = np.random.default_rng(5)
    S, N = 16, 200
    out = cscv_pbo(rng.normal(0, 0.02, (S, N)) * np.sqrt(50), np.full((S, N), 50.0))
    assert out["mean_is_best"] > 0.002 and out["mean_oos_best"] < out["mean_is_best"] / 3


def test_entry_series_and_block_stats_respect_purge():
    n, H = 600, 20
    net = np.arange(n, dtype=float) / 1000
    s = entry_series(np.array([5, 9]), net, 0, 100, benchmark_mean=0.001)
    assert s.sum() == pytest.approx(net[5] + net[9] - 0.002) and s[5] != 0 and s[0] == 0
    exit_offset = np.full(n, H - 1, dtype=np.int16)
    sig = np.ones(n, dtype=bool)
    blocks = [Segment("b0", 0, 300), Segment("b1", 300, 600)]
    sm, cn = condition_block_stats(sig, net, exit_offset, blocks, H, mode="fixed", cooldown=1)
    for j, b in enumerate(blocks):
        e = np.arange(b.start + 1, b.end)
        assert cn[j] == fits_in_segment(e, H, b).sum()   # sólo entradas cuyo intervalo cabe en el bloque
        assert sm[j] == pytest.approx(net[e[fits_in_segment(e, H, b)]].sum())
