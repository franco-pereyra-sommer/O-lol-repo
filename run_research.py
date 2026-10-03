#%%
"""
Punto de entrada.

Ejemplos (desde la carpeta del repo, dentro del entorno de Pixi):

    python run_research.py --csv "C:\\O lol\\Guardado de datos\\BTC-USD_int1h_combinado.csv" --depth 2

    # TP / SL / horizonte
    python run_research.py --csv ... --tp 0.08 --sl 0.03 --horizon 100

    # Grilla: prueba TODAS las combinaciones (aquí 2 x 2 x 2 = 8 corridas)
    python run_research.py --csv ... --tp 0.05 0.08 --sl 0.02 0.03 --horizon 30 100

    # Sin operaciones superpuestas y filtro por mejora sobre la línea base
    python run_research.py --csv ... --cooldown-mode until_exit --filter-mode lift

    python run_research.py --help        # todas las opciones

Cualquier opción que no se pase usa el valor de trading_research/config.py.
"""
from __future__ import annotations

import argparse
import itertools
import logging
from pathlib import Path

import pandas as pd

from trading_research.config import ResearchConfig
from trading_research.data import load_data
from trading_research.features import FeatureStore
from trading_research.search import ResearchPipeline, SearchResult, save_results
from trading_research.statistics import format_report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Búsqueda exploratoria de condiciones de entrada.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    d = ResearchConfig()

    g = p.add_argument_group("datos")
    g.add_argument("--csv", help="Usar un CSV OHLC en lugar de yfinance.")
    g.add_argument("--asset", default=d.ASSET)
    g.add_argument("--timeframe", default=d.TIMEFRAME)
    g.add_argument("--train", type=float, default=d.TRAIN_FRACTION, help="Fracción TRAIN.")
    g.add_argument("--val", type=float, default=d.VALIDATION_FRACTION,
                   help="Fracción VALIDATION (TEST = el resto).")

    g = p.add_argument_group("búsqueda")
    g.add_argument("--seed", type=int, default=d.RANDOM_SEED)
    g.add_argument("--depth", type=int, default=d.MAX_CONDITION_DEPTH, help="MAX_CONDITION_DEPTH")
    g.add_argument("--n-simple", type=int, default=d.N_SIMPLE_CONDITIONS)
    g.add_argument("--n-complex", type=int, default=d.N_COMPLEX_CONDITIONS)
    g.add_argument("--pool-size", type=int, default=d.STAGE2_POOL_SIZE,
                   help="Cuántas condiciones simples se usan como piezas en la etapa 2.")

    g = p.add_argument_group("operación (se aceptan varios valores -> grilla)")
    g.add_argument("--tp", type=float, nargs="+", default=[d.TP_PERCENT],
                   help="Take profit como fracción (0.05 = 5%%).")
    g.add_argument("--sl", type=float, nargs="+", default=[d.SL_PERCENT],
                   help="Stop loss como fracción (0.02 = 2%%).")
    g.add_argument("--horizon", type=int, nargs="+", default=[d.MAX_HOLDING_BARS],
                   help="Horizonte máximo en velas (MAX_HOLDING_BARS).")
    g.add_argument("--cooldown", type=int, default=d.MIN_BARS_BETWEEN_SAME_CONDITION_ENTRIES,
                   help="Velas entre entradas de la misma condición (modo fixed).")
    g.add_argument("--cooldown-mode", choices=("fixed", "until_exit"), default=d.COOLDOWN_MODE,
                   help="fixed = cooldown fijo; until_exit = no re-entrar con la operación abierta.")
    g.add_argument("--ambiguous", choices=("worst", "best", "midpoint"),
                   default=d.AMBIGUOUS_RETURN_POLICY, help="Retorno asignado a casos AMBIGUOUS.")

    g = p.add_argument_group("costos (fracciones por lado)")
    g.add_argument("--commission", type=float, default=d.COMMISSION_RATE)
    g.add_argument("--slippage", type=float, default=d.SLIPPAGE_RATE)
    g.add_argument("--spread", type=float, default=d.SPREAD_RATE, help="Spread completo.")

    g = p.add_argument_group("filtros")
    g.add_argument("--filter-mode", choices=("absolute", "lift", "both"), default=d.FILTER_MODE)
    g.add_argument("--min-p-tp", type=float, default=d.MIN_P_TP_FIRST)
    g.add_argument("--min-return", type=float, default=d.MIN_EXPECTED_RETURN)
    g.add_argument("--min-lift-p-tp", type=float, default=d.MIN_LIFT_P_TP_FIRST)
    g.add_argument("--min-lift-return", type=float, default=d.MIN_LIFT_EXPECTED_RETURN)
    g.add_argument("--return-basis", choices=("net", "gross"), default=d.EXPECTED_RETURN_BASIS)
    g.add_argument("--min-cases", type=int, default=d.MIN_CASES_ABSOLUTE,
                   help="Mínimo absoluto de entradas.")
    g.add_argument("--min-cases-frac", type=float, default=d.MIN_CASES_FRACTION)

    g = p.add_argument_group("salida")
    g.add_argument("--run-test", action="store_true", help="Evaluar el segmento TEST.")
    g.add_argument("--output", default=d.OUTPUT_DIR, help="Directorio de salida.")
    g.add_argument("--top", type=int, default=5, help="Cuántas sobrevivientes mostrar por corrida.")
    g.add_argument("--no-events", action="store_true", help="No guardar events.csv.gz.")
    return p.parse_args()


def base_config(a: argparse.Namespace) -> ResearchConfig:
    cfg = ResearchConfig(
        ASSET=a.asset, TIMEFRAME=a.timeframe,
        TRAIN_FRACTION=a.train, VALIDATION_FRACTION=a.val,
        TEST_FRACTION=round(1.0 - a.train - a.val, 10),
        RANDOM_SEED=a.seed, MAX_CONDITION_DEPTH=a.depth,
        N_SIMPLE_CONDITIONS=a.n_simple, N_COMPLEX_CONDITIONS=a.n_complex,
        STAGE2_POOL_SIZE=a.pool_size,
        MIN_BARS_BETWEEN_SAME_CONDITION_ENTRIES=a.cooldown, COOLDOWN_MODE=a.cooldown_mode,
        AMBIGUOUS_RETURN_POLICY=a.ambiguous,
        COMMISSION_RATE=a.commission, SLIPPAGE_RATE=a.slippage, SPREAD_RATE=a.spread,
        FILTER_MODE=a.filter_mode, MIN_P_TP_FIRST=a.min_p_tp, MIN_EXPECTED_RETURN=a.min_return,
        MIN_LIFT_P_TP_FIRST=a.min_lift_p_tp, MIN_LIFT_EXPECTED_RETURN=a.min_lift_return,
        EXPECTED_RETURN_BASIS=a.return_basis,
        MIN_CASES_ABSOLUTE=a.min_cases, MIN_CASES_FRACTION=a.min_cases_frac,
        RUN_TEST_EVALUATION=a.run_test, OUTPUT_DIR=a.output, SAVE_EVENTS=not a.no_events,
    )
    if a.csv:
        cfg.DATA_SOURCE, cfg.CSV_PATH = "csv", a.csv
    return cfg


def print_run(res: SearchResult, top: int) -> None:
    cfg, m = res.cfg, res.meta
    print("\n" + "=" * 72)
    print(f"TP={cfg.TP_PERCENT:g}  SL={cfg.SL_PERCENT:g}  horizonte={cfg.MAX_HOLDING_BARS} velas  "
          f"re-entrada={cfg.COOLDOWN_MODE}"
          + (f"({cfg.MIN_BARS_BETWEEN_SAME_CONDITION_ENTRIES})" if cfg.COOLDOWN_MODE == "fixed" else "")
          + f"  filtro={cfg.FILTER_MODE}")
    print(f"Condiciones evaluadas: {m['n_conditions_evaluated_total']} "
          f"({m['n_conditions_evaluated_simple']} simples + {m['n_conditions_evaluated_complex']} complejas,"
          f" pool {m['stage2_pool_size']})")
    print(f"Pasan TRAIN: {m['n_passed_train']}   pasan VALIDATION: {m['n_passed_validation']}"
          + (f"   pasan TEST: {m['n_passed_test'] or 0}" if cfg.RUN_TEST_EVALUATION else ""))
    print("Línea base (entrar en todas las velas):")
    for k, b in res.baselines.items():
        print(f"  {k:<10} P_TP={b['P_TP_FIRST']:.3f} P_SL={b['P_SL_FIRST']:.3f} "
              f"mean_gross={b['mean_gross_return']:.4f} mean_net={b['mean_net_return']:.4f}")

    val = res.results["VALIDATION"]
    surv = val[val["passed"]] if len(val) else val
    test = res.results.get("TEST")
    if not len(surv):
        print("Ninguna condición sobrevivió a TRAIN + VALIDATION con los filtros actuales.")
        return
    # Orden sólo para mostrar; no es un ranking de estrategias.
    surv = surv.sort_values("mean_net_return", ascending=False).head(top)
    print(f"\nSobrevivientes de TRAIN + VALIDATION (primeras {len(surv)} por retorno neto medio en VALIDATION):")
    for _, r in surv.iterrows():
        print("-" * 72)
        print("[VALIDATION]")
        print(format_report(r.to_dict()))
        print(f"Lift vs línea base: P_TP {r['lift_P_TP_FIRST']:+.3f}   "
              f"mean_net {r['lift_mean_net_return']:+.4f}")
        if test is not None and len(test):
            tr = test[test["condition_id"] == r["condition_id"]]
            if len(tr):
                t = tr.iloc[0]
                print(f"[TEST] entradas={t['n_entries']}  P_TP={t['P_TP_FIRST']:.3f}  "
                      f"mean_net={t['mean_net_return']:.4f}  lift_P_TP={t['lift_P_TP_FIRST']:+.3f}  "
                      f"{'PASA' if t['passed'] else 'NO PASA: ' + str(t['reject_reasons'])}")


def summary_row(res: SearchResult, out: Path) -> dict:
    c, m = res.cfg, res.meta
    row = {"TP": c.TP_PERCENT, "SL": c.SL_PERCENT, "horizon": c.MAX_HOLDING_BARS,
           "n_evaluated": m["n_conditions_evaluated_total"],
           "passed_train": m["n_passed_train"], "passed_validation": m["n_passed_validation"],
           "passed_test": m["n_passed_test"] if c.RUN_TEST_EVALUATION else None}
    for seg, b in res.baselines.items():
        row[f"base_{seg}_P_TP"] = b["P_TP_FIRST"]
        row[f"base_{seg}_mean_net"] = b["mean_net_return"]
    row["folder"] = out.name
    return row


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    a = parse_args()
    cfg0 = base_config(a)
    cfg0.validate()

    combos = list(itertools.product(a.tp, a.sl, a.horizon))
    output = Path(a.output)
    if len(combos) > 1:
        output = output / f"grid_{pd.Timestamp.utcnow().strftime('%Y%m%d_%H%M%S')}"
        logging.info("Grilla de %d combinaciones TP/SL/horizonte → %s", len(combos), output)

    # Datos e indicadores se calculan una sola vez y se comparten entre corridas.
    df = load_data(cfg0)
    store = FeatureStore(df)

    rows = []
    for i, (tp, sl, h) in enumerate(combos, 1):
        cfg = base_config(a)
        cfg.TP_PERCENT, cfg.SL_PERCENT, cfg.MAX_HOLDING_BARS = tp, sl, h
        if len(combos) > 1:
            logging.info("[%d/%d] TP=%g SL=%g horizonte=%d", i, len(combos), tp, sl, h)
        res = ResearchPipeline(cfg, df=df, store=store).run()
        out = save_results(res, str(output))
        print_run(res, a.top)
        rows.append(summary_row(res, out))

    m = res.meta
    print("\n" + "=" * 72)
    print(f"Datos: {m['data']['n_bars']} velas  {m['data']['start']} → {m['data']['end']}"
          f"  (huecos: {m['data']['n_gaps']})")
    for k, s in m["segments"].items():
        if k == "TEST" and not cfg0.RUN_TEST_EVALUATION:
            print(f"  {k:<10} reservado (no evaluado)")
            continue
        print(f"  {k:<10} {s['start']} → {s['end']}  ({s['n_bars']} velas, mín. casos {s['min_cases']})")

    if len(combos) > 1:
        summ = pd.DataFrame(rows)
        summ.to_csv(output / "grid_summary.csv", index=False)
        cols = ["TP", "SL", "horizon", "passed_train", "passed_validation"] + \
               (["passed_test"] if cfg0.RUN_TEST_EVALUATION else []) + \
               ["base_TRAIN_P_TP", "base_TRAIN_mean_net", "base_VALIDATION_mean_net"]
        print("\nResumen de la grilla:")
        print(summ[cols].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
        print(f"\nAtención: probar {len(combos)} combinaciones de TP/SL/horizonte multiplica la "
              f"cantidad de hipótesis ({len(combos)} x {m['n_conditions_evaluated_total']}). "
              "Elegir la mejor combinación mirando VALIDATION también es selección.")
        print(f"Resumen: {output / 'grid_summary.csv'}")
    print("=" * 72)
    print(m["warning"])
    print(f"Resultados: {output}")


if __name__ == "__main__":
    pd.set_option("display.width", 160)
    main()

# %%
