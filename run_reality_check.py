"""
White Reality Check sobre variantes de procedimiento (EXP-005).

Cada variante es una carpeta de walk-forward con `oos_series.npz` (la escribe
`save_walk_forward`). Se usa la intersección de las velas de VALIDATION de todas las variantes.

    python run_reality_check.py --variant EXP001_LONG=results/exp005/exp001/grid_X/wf_..._LONG_... \
        --variant EXP001_SHORT=... --block 300 --sensitivity-blocks 100 600

Serie por vela de cada variante: promedio simple de los retornos netos de las operaciones
abiertas en esa vela por todas las condiciones seleccionadas (0 si no hay ninguna).
  benchmark "zero"  : H0 = el retorno esperado neto es <= 0.
  benchmark "lift"  : se resta la media de la línea base del fold en las velas con operación.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from trading_research.multiple_testing import reality_check


def load_variant(path: str | Path) -> dict[str, np.ndarray]:
    z = np.load(Path(path) / "oos_series.npz")
    return {k: z[k] for k in z.files}


def variant_series(z: dict[str, np.ndarray], scenario: str, benchmark: str) -> np.ndarray:
    cnt = z["cnt"]
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.where(cnt > 0, z[f"sum_{scenario}"] / cnt, 0.0)
    if benchmark == "lift":
        r = np.where(cnt > 0, r - np.nan_to_num(z[f"base_{scenario}"]), 0.0)
    return r


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--variant", action="append", required=True, help="NOMBRE=carpeta del walk-forward")
    p.add_argument("--block", type=float, default=300.0)
    p.add_argument("--sensitivity-blocks", type=float, nargs="*", default=[100.0, 600.0])
    p.add_argument("--boot", type=int, default=1000)
    p.add_argument("--scenarios", nargs="+", default=["typical", "conservative"])
    p.add_argument("--out", default=None)
    a = p.parse_args()

    names, data = [], []
    for v in a.variant:
        n, path = v.split("=", 1)
        names.append(n)
        data.append(load_variant(path))
    covered = np.all([d["covered"] for d in data], axis=0)
    idx = np.flatnonzero(covered)
    print(f"Variantes (K={len(names)}): {', '.join(names)}")
    print(f"Velas comunes de VALIDATION: T = {len(idx)}  "
          f"(contiguas: {bool(np.all(np.diff(idx) == 1))})")
    out = {"K": len(names), "T": int(len(idx)), "variants": names, "results": []}

    for sc in a.scenarios:
        for bm in ("zero", "lift"):
            F = np.column_stack([variant_series(d, sc, bm)[idx] for d in data])
            trades = np.array([d["cnt"][idx].sum() for d in data])
            print(f"\n=== costos {sc} | benchmark {bm} ===")
            print("variante         operaciones   media por vela")
            for k, n in enumerate(names):
                print(f"{n:<16} {int(trades[k]):>11}   {F[:, k].mean():>13.6f}")
            for blk in [a.block, *a.sensitivity_blocks]:
                rc = reality_check(F, n_boot=a.boot, mean_block=blk, seed=0)
                ind = [reality_check(F[:, [k]], n_boot=a.boot, mean_block=blk, seed=0)["p_value"]
                       for k in range(len(names))]
                tag = "PRIMARIO" if blk == a.block else "sensibilidad"
                print(f"bloque {blk:>5g} ({tag}): RC p = {rc['p_value']:.3f}  mejor = {names[rc['best']]}  "
                      f"| p individuales: " + "  ".join(f"{n}={q:.3f}" for n, q in zip(names, ind))
                      + f"  | Bonferroni(min) = {min(1.0, len(names) * min(ind)):.3f}")
                out["results"].append({"scenario": sc, "benchmark": bm, "block": blk,
                                       "rc_p": rc["p_value"], "best": names[rc["best"]],
                                       "individual_p": dict(zip(names, ind)),
                                       "bonferroni_min": min(1.0, len(names) * min(ind))})
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
