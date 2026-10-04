"""
Prueba de look-ahead a nivel de señales sobre datos reales (EXP-006).

    python run_lookahead.py --csv "D:\\O lol\\Guardado de datos\\BTCUSDT_binance_1h.csv"

Genera condiciones con el mismo generador de la búsqueda (profundidad 3, para cubrir
And/Or/Not/Then/OccurredWithin), y comprueba con la historia completa vs. datos truncados o con el
futuro reemplazado que: (1) cada operando, (2) cada señal y (3) las entradas y retornos netos
no cambian hasta la vela k. Ver trading_research/lookahead.py.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict

import numpy as np

from trading_research.condition_generator import ConditionGenerator
from trading_research.config import ResearchConfig
from trading_research.data import load_data
from trading_research.features import FeatureStore
from trading_research.lookahead import (RecordingStore, check_conditions, check_entries,
                                        check_operands, startup_sensitivity)


def family(key: str) -> str:
    if key.startswith("ind:"):
        return key.split("(")[0]
    return key.split(":")[0]


def by_family(d: dict[str, int]) -> dict[str, tuple[int, int]]:
    agg = defaultdict(lambda: [0, 0])
    for k, v in d.items():
        f = family(k)
        agg[f][0] += 1
        agg[f][1] += int(v > 0)
    return {f: (a, b) for f, (a, b) in sorted(agg.items())}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--n-simple", type=int, default=3000)
    p.add_argument("--n-complex", type=int, default=2000)
    p.add_argument("--n-entry-conds", type=int, default=300)
    p.add_argument("--n-ks", type=int, default=12)
    p.add_argument("--horizon", type=int, default=100)
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--out", default=None)
    a = p.parse_args()

    cfg0 = ResearchConfig(DATA_SOURCE="csv", CSV_PATH=a.csv, MAX_CONDITION_DEPTH=3)
    df = load_data(cfg0)
    n = len(df)
    rng = np.random.default_rng(a.seed)
    ks = sorted({int(x) for x in rng.integers(1500, n - 2000, a.n_ks)} | {60, 300, 700})
    print(f"Datos: {n} velas; cortes k = {ks}")

    store = RecordingStore(df)
    gen = ConditionGenerator(cfg0, store, slice(0, int(n * 0.6)), np.random.default_rng(a.seed))
    simple = gen.generate_simple(a.n_simple)
    conds = simple + gen.generate_complex(simple, a.n_complex, 3)
    sigs = {c.key: c.evaluate(store) for c in conds}
    ops = store.operands
    print(f"{len(conds)} condiciones, {len(ops)} operandos distintos")

    res = {"n_conditions": len(conds), "n_operands": len(ops), "ks": ks}
    f_ops = check_operands(df, ops, ks, rng)
    res["operands_failed"] = {k: v for k, v in f_ops.items() if v}
    print(f"[1] operandos con cambios hasta k: {len(res['operands_failed'])}/{len(ops)}")
    for fam, (tot, bad) in by_family(f_ops).items():
        print(f"      {fam:<22} {bad}/{tot}")

    f_cond = check_conditions(df, conds, ks, rng)
    res["conditions_failed"] = {k: v for k, v in f_cond.items() if v}
    print(f"[2] condiciones con señal distinta hasta k: {len(res['conditions_failed'])}/{len(conds)}")

    sub = conds[: a.n_entry_conds]
    for mode, cd in (("until_exit", 1), ("fixed", 15)):
        cfg = ResearchConfig(MAX_HOLDING_BARS=a.horizon, COOLDOWN_MODE=mode,
                             MIN_BARS_BETWEEN_SAME_CONDITION_ENTRIES=cd)
        fns = {c.key: (lambda d, c=c: c.evaluate(FeatureStore(d))) for c in sub}
        f_ent = check_entries(df, fns, cfg, ks)
        bad = {k: v for k, v in f_ent.items() if v}
        res[f"entries_failed_{mode}"] = bad
        print(f"[3] entradas ({mode}, H={a.horizon}) con diferencias: {len(bad)}/{len(sub)}")

    starts = [1000, 5000, 20000]
    sens = startup_sensitivity(df, ops, starts)
    res["startup_sensitive"] = {k: v for k, v in sens.items() if v}
    print(f"[4] (informativo) operandos que dependen del arranque de la historia: "
          f"{len(res['startup_sensitive'])}/{len(ops)}")
    for fam, (tot, bad) in by_family(sens).items():
        print(f"      {fam:<22} {bad}/{tot}")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1)


if __name__ == "__main__":
    main()
