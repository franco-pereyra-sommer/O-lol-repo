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
import pandas as pd

from trading_research.condition_generator import ConditionGenerator
from trading_research.config import ResearchConfig
from trading_research.data import load_data
from trading_research.features import FeatureStore
from trading_research.lookahead import (RecordingStore, check_conditions, check_entries, check_exit_levels,
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
    p.add_argument("--regime-features", action="store_true")
    p.add_argument("--timeframe", default="1h")
    p.add_argument("--csv-timeframe", default="")
    p.add_argument("--exit-mode", choices=("fixed", "atr"), default="fixed")
    p.add_argument("--tp", type=float, default=None, help="TP fijo (fracción) para el chequeo de entradas.")
    p.add_argument("--sl", type=float, default=None, help="SL fijo (fracción) para el chequeo de entradas.")
    p.add_argument("--tp-atr", type=float, default=2.0)
    p.add_argument("--sl-atr", type=float, default=1.0)
    p.add_argument("--search-mode", choices=("random", "structured"), default="random")
    p.add_argument("--out", default=None)
    a = p.parse_args()

    cfg0 = ResearchConfig(DATA_SOURCE="csv", CSV_PATH=a.csv, MAX_CONDITION_DEPTH=3,
                          REGIME_FEATURES=a.regime_features, TIMEFRAME=a.timeframe,
                          CSV_TIMEFRAME=a.csv_timeframe)
    df = load_data(cfg0)
    n = len(df)
    rng = np.random.default_rng(a.seed)
    ks = sorted({int(x) for x in rng.integers(1500, n - 2000, a.n_ks)} | {60, 300, 700})
    print(f"Datos: {n} velas; cortes k = {ks}")

    store = RecordingStore(df)
    if a.search_mode == "structured":
        import dataclasses
        conds = []
        for side in ("LONG", "SHORT"):
            cfg_s = dataclasses.replace(cfg0, POSITION_TYPE=side, SEARCH_MODE="structured")
            gen = ConditionGenerator(cfg_s, store, slice(0, int(n * 0.6)), np.random.default_rng(a.seed))
            conds += gen.generate_structured((a.n_simple + a.n_complex) // 2)
    else:
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

    sub = conds[:: max(1, len(conds) // a.n_entry_conds)][: a.n_entry_conds]
    for mode, cd in (("until_exit", 1), ("fixed", 15)):
        xkw = {k: v for k, v in (("TP_PERCENT", a.tp), ("SL_PERCENT", a.sl)) if v is not None}
        cfg = ResearchConfig(MAX_HOLDING_BARS=a.horizon, COOLDOWN_MODE=mode,
                             MIN_BARS_BETWEEN_SAME_CONDITION_ENTRIES=cd, EXIT_MODE=a.exit_mode,
                             TP_ATR_MULT=a.tp_atr, SL_ATR_MULT=a.sl_atr, **xkw)
        fns = {c.key: (lambda d, c=c: c.evaluate(FeatureStore(d))) for c in sub}
        f_ent = check_entries(df, fns, cfg, ks)
        bad = {k: v for k, v in f_ent.items() if v}
        res[f"entries_failed_{mode}"] = bad
        print(f"[3] entradas ({mode}, H={a.horizon}) con diferencias: {len(bad)}/{len(sub)}")

    if a.exit_mode == "atr":
        for side in ("LONG", "SHORT"):
            cfg_x = ResearchConfig(MAX_HOLDING_BARS=a.horizon, EXIT_MODE="atr", TP_ATR_MULT=a.tp_atr,
                                   SL_ATR_MULT=a.sl_atr, POSITION_TYPE=side)
            fx = check_exit_levels(df, cfg_x, ks, rng)
            res[f"exit_levels_failed_{side}"] = fx
            print(f"[3b] niveles de TP/SL por ATR ({side}, {a.tp_atr:g}/{a.sl_atr:g}) con cambios hasta k: {fx}")
    if a.csv_timeframe and a.csv_timeframe != a.timeframe:
        import dataclasses
        from trading_research.lookahead import check_resample_causality
        df1 = load_data(dataclasses.replace(cfg0, TIMEFRAME=a.csv_timeframe, CSV_TIMEFRAME=""))
        hrs = int(pd.Timedelta(a.timeframe) / pd.Timedelta(a.csv_timeframe))
        pos = sorted({int(x) for x in rng.integers(2000, len(df1) - 4000, 6)}
                     | {int(x) + o for x in rng.integers(2000, len(df1) - 4000, 2) for o in range(hrs)})
        cfg_r = ResearchConfig(MAX_HOLDING_BARS=a.horizon, COOLDOWN_MODE="until_exit", TIMEFRAME=a.timeframe)
        fr = check_resample_causality(df1, sub[:60], pos, rng, cfg=cfg_r)
        res["resample_causality"] = fr
        print(f"[3c] causalidad del remuestreo {a.csv_timeframe}->{a.timeframe} "
              f"({len(pos)} posiciones x 5 variantes: mismo bloque, bloque siguiente, bloque posterior, "
              f"futuro reemplazado, truncado): {fr}")
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
