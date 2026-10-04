"""
Corrección por múltiples hipótesis y sobreajuste de la selección (EXP-004).

Dos herramientas, ambas funciones puras sobre matrices de rendimiento ya calculadas
(netas de costos, de las operaciones purgadas por `entry_detector`):

1. `reality_check`  — White (2000), "A Reality Check for Data Snooping", con
   bootstrap estacionario (Politis y Romano, 1994) para respetar la dependencia
   temporal. Pregunta: ¿el MEJOR de K reglas tiene rendimiento esperado > 0
   (o > un benchmark) una vez que se tiene en cuenta que se eligió el mejor entre K?
   Se usa el estadístico estudentizado (máximo de t, variante recomendada por
   Hansen 2005). NO incluye la re-centralización consistente de SPA: las reglas
   claramente malas siguen en el universo, lo que vuelve el test algo conservador.

2. `cscv_pbo`  — Probability of Backtest Overfitting (Bailey, Borwein, López de Prado
   y Zhu, 2016) por CSCV. Pregunta: si en cada partición IN/OUT elijo la mejor regla
   IN-sample, ¿con qué frecuencia queda por debajo de la mediana OUT-of-sample?

Ninguna es una prueba de que "algo funciona": la primera acota el azar del máximo
dentro de un universo explícito de reglas; la segunda mide cuánto se degrada lo que
se elige. Ver la entrada EXP-004 de RESEARCH_LOG.md para sus límites.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np

from .entry_detector import Segment, detect_entries


# ---------------------------------------------------------------------- #
# Adaptadores: operaciones -> series / sumas por bloque
# ---------------------------------------------------------------------- #
def entry_series(entry_idx: np.ndarray, net_return: np.ndarray, start: int, end: int,
                 benchmark_mean: float = 0.0) -> np.ndarray:
    """Serie por vela de [start, end): en la vela de ENTRADA de cada operación, su retorno neto
    menos `benchmark_mean` (0 = benchmark efectivo; la media de la línea base = exceso sobre
    entrar en cualquier vela); 0 en las velas sin operación. Los retornos se asignan a la vela de
    entrada y las operaciones duran hasta H velas, por lo que la serie es dependiente: el
    bootstrap debe usar bloques de longitud media >= H."""
    out = np.zeros(end - start)
    e = np.asarray(entry_idx)
    out[e - start] = net_return[e] - benchmark_mean
    return out


def condition_block_stats(signal: np.ndarray, net_return: np.ndarray, exit_offset: np.ndarray,
                          blocks: list[Segment], holding_bars: int, cooldown: int = 1,
                          mode: str = "until_exit") -> tuple[np.ndarray, np.ndarray]:
    """Suma y cantidad de retornos netos por bloque. Cada bloque se purga como un segmento
    (`detect_entries`: ninguna operación cruza el borde del bloque), lo que es obligatorio en
    CSCV porque los bloques IN y OUT se mezclan en el tiempo."""
    s = np.zeros(len(blocks))
    c = np.zeros(len(blocks))
    for j, b in enumerate(blocks):
        d = detect_entries(signal, b, holding_bars, cooldown, mode, exit_offset)
        r = net_return[d.entry_idx]
        s[j], c[j] = r.sum(), len(r)
    return s, c


def procedure_series(z: dict[str, np.ndarray], scenario: str, benchmark: str = "zero") -> np.ndarray:
    """Serie por vela de un walk-forward a partir de su `oos_series.npz`: promedio simple de los
    retornos netos de las operaciones abiertas en la vela (0 si no hay). benchmark "lift": se resta la
    media de la línea base del fold en las velas con operación."""
    cnt = z["cnt"]
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.where(cnt > 0, z[f"sum_{scenario}"] / cnt, 0.0)
    if benchmark == "lift":
        r = np.where(cnt > 0, r - np.nan_to_num(z[f"base_{scenario}"]), 0.0)
    return r


def newey_west_t(x: np.ndarray, lags: int) -> float:
    """t de la media de una serie con error estándar HAC (Newey-West, pesos de Bartlett).
    `lags` debe cubrir la dependencia: para series de operaciones de hasta H velas, >= H."""
    x = np.asarray(x, dtype=float)
    T = len(x)
    if T < 3:
        return float("nan")
    u = x - x.mean()
    omega = float(u @ u) / T
    for j in range(1, min(lags, T - 1) + 1):
        omega += 2.0 * (1.0 - j / (lags + 1.0)) * float(u[j:] @ u[:-j]) / T
    return float(x.mean() / np.sqrt(omega / T)) if omega > 0 else float("nan")


# ---------------------------------------------------------------------- #
# White Reality Check (bootstrap estacionario, estadístico estudentizado)
# ---------------------------------------------------------------------- #
def stationary_bootstrap_weights(T: int, n_boot: int, mean_block: float,
                                 rng: np.random.Generator) -> np.ndarray:
    """Matriz (n_boot, T): fracción de veces que cada período entra en cada remuestreo.
    Bloques circulares de largo geométrico con media `mean_block`."""
    p = 1.0 / max(mean_block, 1.0)
    starts = rng.integers(0, T, size=(n_boot, T))
    restart = rng.random((n_boot, T)) < p
    restart[:, 0] = True
    idx = np.empty((n_boot, T), dtype=np.int64)
    idx[:, 0] = starts[:, 0]
    for t in range(1, T):
        idx[:, t] = np.where(restart[:, t], starts[:, t], (idx[:, t - 1] + 1) % T)
    w = np.zeros((n_boot, T))
    for b in range(n_boot):
        w[b] = np.bincount(idx[b], minlength=T)
    return w / T


def reality_check(perf: np.ndarray, n_boot: int = 1000, mean_block: float | None = None,
                  studentize: bool = True, seed: int = 0) -> dict:
    """
    perf: (T, K) rendimiento por período de cada una de las K reglas del universo, ya neto de
          costos y ya restado el benchmark (H0: E[perf_k] <= 0 para todo k).
    Devuelve el p-valor de H0 "ninguna de las K reglas supera al benchmark".
    p = P*( max_k estadístico*_k >= max_k estadístico_k ) con las medias bootstrap centradas en
    las medias muestrales (caso menos favorable, White 2000).
    Reglas sin variabilidad (nunca operan) se ignoran. mean_block por defecto T^(1/3): fijarlo
    explícitamente >= horizonte cuando la serie viene de `entry_series`.
    """
    x = np.asarray(perf, dtype=float)
    if x.ndim == 1:
        x = x[:, None]
    T, K = x.shape
    mean_block = float(mean_block) if mean_block else max(1.0, T ** (1 / 3))
    rng = np.random.default_rng(seed)
    fbar = x.mean(axis=0)
    # Por tandas para no materializar (n_boot, T) con T ~ 10^5.
    chunk = max(1, int(2e7 // max(T, 1)))
    parts = []
    for i in range(0, n_boot, chunk):
        w = stationary_bootstrap_weights(T, min(chunk, n_boot - i), mean_block, rng)
        parts.append(w @ x)
    boot = np.vstack(parts) - fbar            # (n_boot, K), centradas
    sd = boot.std(axis=0, ddof=1) if studentize else np.ones(K)
    live = sd > 1e-15
    if not live.any():
        return {"p_value": float("nan"), "stat": float("nan"), "best": -1, "n_rules": K,
                "n_live": 0, "mean_block": mean_block}
    scale = np.where(live, sd, np.inf)
    stat_k = fbar / scale
    stat = float(stat_k.max())
    boot_max = (boot / scale).max(axis=1)
    p = float((1 + (boot_max >= stat).sum()) / (n_boot + 1))
    k = int(np.argmax(stat_k))
    return {"p_value": p, "stat": stat, "best": k, "best_mean": float(fbar[k]),
            "n_rules": K, "n_live": int(live.sum()), "mean_block": mean_block}


# ---------------------------------------------------------------------- #
# Probability of Backtest Overfitting (CSCV)
# ---------------------------------------------------------------------- #
def cscv_pbo(block_sum: np.ndarray, block_cnt: np.ndarray, min_trades: int = 30,
             max_combinations: int | None = None, seed: int = 0) -> dict:
    """
    block_sum, block_cnt: (S, N) suma y cantidad de retornos netos de cada una de las N reglas en
    cada uno de los S bloques temporales (S par). Métrica de selección: retorno neto medio por
    operación sobre la unión de bloques (se exige `min_trades` en el lado IN y OUT).
    Para cada una de las C(S, S/2) particiones IN/OUT: elegir la mejor regla IN, calcular el rango
    relativo omega de esa regla en OUT entre las demás, lambda = ln(omega/(1-omega)).
    PBO = fracción de particiones con lambda <= 0 (la mejor IN queda en la mitad inferior OUT).
    Con reglas sin ninguna información, PBO ~ 0,5. Un valor bajo NO prueba que haya señal.
    """
    S, N = block_sum.shape
    if S % 2:
        raise ValueError("S debe ser par.")
    combos = list(combinations(range(S), S // 2))
    if max_combinations and len(combos) > max_combinations:
        rng = np.random.default_rng(seed)
        combos = [combos[i] for i in rng.choice(len(combos), max_combinations, replace=False)]
    allb = set(range(S))
    lam, is_best, oos_best = [], [], []
    for c in combos:
        i = list(c)
        o = sorted(allb - set(c))
        cnt_i, cnt_o = block_cnt[i].sum(0), block_cnt[o].sum(0)
        with np.errstate(invalid="ignore", divide="ignore"):
            m_i = np.where(cnt_i >= min_trades, block_sum[i].sum(0) / cnt_i, np.nan)
            m_o = np.where(cnt_o >= min_trades, block_sum[o].sum(0) / cnt_o, np.nan)
        if np.isnan(m_i).all():
            continue
        k = int(np.nanargmax(m_i))
        if np.isnan(m_o[k]):
            continue
        valid = ~np.isnan(m_o)
        rank = 1 + int((m_o[valid] < m_o[k]).sum())
        omega = rank / (int(valid.sum()) + 1)
        lam.append(np.log(omega / (1 - omega)))
        is_best.append(m_i[k])
        oos_best.append(m_o[k])
    if not lam:
        return {"pbo": float("nan"), "n_combinations": 0}
    lam, is_best, oos_best = np.array(lam), np.array(is_best), np.array(oos_best)
    slope = (float(np.polyfit(is_best, oos_best, 1)[0])
             if len(lam) > 2 and is_best.std() > 0 else float("nan"))
    return {"pbo": float((lam <= 0).mean()), "n_combinations": int(len(lam)),
            "mean_is_best": float(is_best.mean()), "mean_oos_best": float(oos_best.mean()),
            "prob_oos_loss": float((oos_best < 0).mean()), "slope_oos_on_is": slope,
            "lambda": lam}
