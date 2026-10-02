#%%

"""
Punto de entrada.

Ejemplos:
    python run_research.py                                   # yfinance, config por defecto
    python run_research.py --csv "datos/BTC-USD_1h.csv"      # desde un CSV
    python run_research.py --depth 2 --seed 7
    python run_research.py --run-test                        # evaluar TEST (sólo al final)
"""
from __future__ import annotations

import argparse
import logging

import pandas as pd

from trading_research.config import ResearchConfig
from trading_research.search import ResearchPipeline, save_results
from trading_research.statistics import format_report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Búsqueda exploratoria de condiciones de entrada.")
    p.add_argument("--csv", help="Usar un CSV OHLC en lugar de yfinance.")
    p.add_argument("--asset")
    p.add_argument("--timeframe")
    p.add_argument("--seed", type=int)
    p.add_argument("--depth", type=int, help="MAX_CONDITION_DEPTH")
    p.add_argument("--n-simple", type=int)
    p.add_argument("--n-complex", type=int)
    p.add_argument("--run-test", action="store_true", help="Evaluar el segmento TEST.")
    p.add_argument("--output", help="Directorio de salida.")
    p.add_argument("--top", type=int, default=10, help="Cuántas sobrevivientes mostrar.")
    return p.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    a = parse_args()
    cfg = ResearchConfig()
    if a.csv:
        cfg.DATA_SOURCE, cfg.CSV_PATH = "csv", a.csv
    if a.asset: cfg.ASSET = a.asset
    if a.timeframe: cfg.TIMEFRAME = a.timeframe
    if a.seed is not None: cfg.RANDOM_SEED = a.seed
    if a.depth is not None: cfg.MAX_CONDITION_DEPTH = a.depth
    if a.n_simple is not None: cfg.N_SIMPLE_CONDITIONS = a.n_simple
    if a.n_complex is not None: cfg.N_COMPLEX_CONDITIONS = a.n_complex
    if a.run_test: cfg.RUN_TEST_EVALUATION = True
    if a.output: cfg.OUTPUT_DIR = a.output

    res = ResearchPipeline(cfg).run()
    out = save_results(res)

    m = res.meta
    print("\n" + "=" * 72)
    print(f"Datos: {m['data']['n_bars']} velas  {m['data']['start']} → {m['data']['end']}"
          f"  (huecos: {m['data']['n_gaps']})")
    for k, s in m["segments"].items():
        if k == "TEST" and not cfg.RUN_TEST_EVALUATION:
            print(f"  {k:<10} reservado (no evaluado)")
            continue
        print(f"  {k:<10} {s['start']} → {s['end']}  ({s['n_bars']} velas, mín. casos {s['min_cases']})")
    print(f"Condiciones evaluadas: {m['n_conditions_evaluated_total']} "
          f"({m['n_conditions_evaluated_simple']} simples + {m['n_conditions_evaluated_complex']} complejas)")
    print(f"Pasan TRAIN: {m['n_passed_train']}   pasan VALIDATION: {m['n_passed_validation']}"
          + (f"   pasan TEST: {m['n_passed_test']}" if cfg.RUN_TEST_EVALUATION else ""))
    print("\nLínea base (entrar en todas las velas):")
    for k, b in res.baselines.items():
        print(f"  {k:<10} P_TP={b['P_TP_FIRST']:.3f} P_SL={b['P_SL_FIRST']:.3f} "
              f"mean_gross={b['mean_gross_return']:.4f} mean_net={b['mean_net_return']:.4f}")

    val = res.results["VALIDATION"]
    surv = val[val["passed"]] if len(val) else val
    test = res.results.get("TEST")
    if len(surv):
        # Orden sólo para mostrar; no es un ranking de estrategias.
        surv = surv.sort_values("mean_net_return", ascending=False).head(a.top)
        print(f"\nSobrevivientes de TRAIN + VALIDATION (primeras {len(surv)} por retorno neto medio en VALIDATION):")
        for _, r in surv.iterrows():
            print("-" * 72)
            print("[VALIDATION]")
            print(format_report(r.to_dict()))
            if test is not None and len(test):
                tr = test[test["condition_id"] == r["condition_id"]]
                if len(tr):
                    t = tr.iloc[0]
                    print(f"[TEST] entradas={t['n_entries']}  P_TP={t['P_TP_FIRST']:.3f}  "
                          f"mean_net={t['mean_net_return']:.4f}  "
                          f"{'PASA' if t['passed'] else 'NO PASA: ' + str(t['reject_reasons'])}")
    else:
        print("\nNinguna condición sobrevivió a TRAIN + VALIDATION con los filtros actuales.")
    print("=" * 72)
    print(m["warning"])
    print(f"Resultados: {out}")


if __name__ == "__main__":
    pd.set_option("display.width", 160)
    main()

# %%
