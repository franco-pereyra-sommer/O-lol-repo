"""
División temporal de los datos y filtros de candidatos.

  pasado ------------------------------------------------> futuro
  [        TRAIN        ][   VALIDATION   ][     TEST     ]

  TRAIN       : generar y explorar condiciones (incluye el cálculo de umbrales
                por cuantiles y la elección del pool de la etapa 2).
  VALIDATION  : re-evaluar sólo las condiciones que pasaron en TRAIN.
  TEST        : evaluar UNA vez, al final, sólo las que pasaron VALIDATION.
                Nunca se usa para decidir qué condiciones son interesantes.

Los indicadores se calculan sobre la serie completa: como son causales, el
valor en t no depende de velas posteriores, y así el comienzo de VALIDATION
no sufre un período de calentamiento artificial. Lo que sí se impide es que
una entrada de un segmento use precios del segmento siguiente para medir su
resultado (ver entry_detector).
"""
from __future__ import annotations

from typing import Any, Iterator

from .config import ResearchConfig
from .entry_detector import Segment
from .statistics import min_cases_required


def chronological_split(n_bars: int, cfg: ResearchConfig) -> dict[str, Segment]:
    a = int(round(n_bars * cfg.TRAIN_FRACTION))
    b = int(round(n_bars * (cfg.TRAIN_FRACTION + cfg.VALIDATION_FRACTION)))
    return {"TRAIN": Segment("TRAIN", 0, a),
            "VALIDATION": Segment("VALIDATION", a, b),
            "TEST": Segment("TEST", b, n_bars)}


def walk_forward_segments(n_bars: int, train_bars: int, test_bars: int,
                          step: int | None = None, anchored: bool = False
                          ) -> Iterator[tuple[Segment, Segment]]:
    """
    Preparado para walk-forward (no se usa todavía en el pipeline):
      TRAIN_1 → TEST_1, TRAIN_2 → TEST_2, …  siempre respetando el orden temporal.
    anchored=True: el train siempre empieza en 0 (ventana expansiva).
    """
    step = step or test_bars
    start, k = 0, 1
    while start + train_bars + test_bars <= n_bars:
        tr0 = 0 if anchored else start
        tr = Segment(f"WF{k}_TRAIN", tr0, start + train_bars)
        te = Segment(f"WF{k}_TEST", start + train_bars, start + train_bars + test_bars)
        yield tr, te
        start += step
        k += 1


def passes_filters(stats: dict[str, Any], cfg: ResearchConfig, n_segment_bars: int
                   ) -> tuple[bool, list[str]]:
    """
    Filtros (sección 25). Devuelve (pasa, motivos de rechazo).

    El mínimo de casos se exige siempre. Después, según cfg.FILTER_MODE:
      absolute : P(TP) >= MIN_P_TP_FIRST  y  retorno > MIN_EXPECTED_RETURN
      lift     : P(TP) - P_base >= MIN_LIFT_P_TP_FIRST
                 y retorno - ret_base > MIN_LIFT_EXPECTED_RETURN
      both     : los dos criterios
    Los lifts deben venir calculados en `stats` (statistics.add_lift) contra
    la línea base del MISMO segmento.
    """
    reasons = []
    need = min_cases_required(cfg, n_segment_bars)
    if stats["n_entries"] < need:
        reasons.append(f"n<{need}")
    basis = "net" if cfg.EXPECTED_RETURN_BASIS == "net" else "gross"
    ret_key = f"mean_{basis}_return"

    def ok(x, thr, strict):
        return x is not None and x == x and (x > thr if strict else x >= thr)

    if cfg.FILTER_MODE in ("absolute", "both"):
        if not ok(stats.get("P_TP_FIRST"), cfg.MIN_P_TP_FIRST, False):
            reasons.append(f"P_TP<{cfg.MIN_P_TP_FIRST}")
        if not ok(stats.get(ret_key), cfg.MIN_EXPECTED_RETURN, True):
            reasons.append(f"{ret_key}<={cfg.MIN_EXPECTED_RETURN}")
    if cfg.FILTER_MODE in ("lift", "both"):
        if not ok(stats.get("lift_P_TP_FIRST"), cfg.MIN_LIFT_P_TP_FIRST, False):
            reasons.append(f"lift_P_TP<{cfg.MIN_LIFT_P_TP_FIRST}")
        if not ok(stats.get(f"lift_{ret_key}"), cfg.MIN_LIFT_EXPECTED_RETURN, True):
            reasons.append(f"lift_{ret_key}<={cfg.MIN_LIFT_EXPECTED_RETURN}")
    return (not reasons, reasons)
