"""
De señales booleanas a eventos de entrada.

Convenciones de índices (posiciones enteras en el DataFrame completo):
  t   = vela de CONFIRMACIÓN: la condición es verdadera al cierre de t
  e   = t + 1 = vela de ENTRADA; precio de entrada = Open[e]
  ventana de evaluación = velas e, e+1, …, e+H-1   (H = MAX_HOLDING_BARS)

Reglas:
  1. Segmento: t, e y toda la ventana deben caer dentro del mismo segmento
     (TRAIN, VALIDATION o TEST). Una entrada cuyo horizonte "se sale" del
     segmento se descarta (purga): si no, el resultado de una entrada de TRAIN
     dependería de precios de VALIDATION. Se reporta cuántas se descartan.
  2. Cooldown por condición: una señal en t se acepta sólo si
     t - t_ultima_aceptada >= MIN_BARS_BETWEEN_SAME_CONDITION_ENTRIES.
     Se aplica de manera independiente a cada condición; señales de
     condiciones distintas nunca se filtran entre sí.

Nada de este módulo mira datos posteriores a t para decidir si hubo señal:
la señal ya viene calculada (causalmente) por conditions.py. La única
información "futura" que se usa es si existen suficientes velas para medir
el resultado, lo cual no depende de los precios.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Segment:
    name: str
    start: int   # inclusive
    end: int     # exclusive

    @property
    def n_bars(self) -> int:
        return self.end - self.start

    @property
    def slice(self) -> slice:
        return slice(self.start, self.end)


@dataclass
class EntryDetection:
    confirm_idx: np.ndarray      # t
    entry_idx: np.ndarray        # t + 1
    n_raw_signals: int           # señales verdaderas dentro del segmento
    n_dropped_horizon: int       # señales descartadas por horizonte fuera del segmento
    n_dropped_cooldown: int      # señales descartadas por cooldown


def apply_cooldown(candidates: np.ndarray, cooldown: int) -> np.ndarray:
    """Filtro greedy: acepta la primera señal y salta las siguientes `cooldown`-1 velas."""
    if cooldown <= 1 or len(candidates) == 0:
        return candidates
    accepted = []
    i = 0
    n = len(candidates)
    while i < n:
        t = candidates[i]
        accepted.append(t)
        i = int(np.searchsorted(candidates, t + cooldown, side="left"))
    return np.asarray(accepted, dtype=np.int64)


def detect_entries(signal: np.ndarray, segment: Segment, holding_bars: int,
                   cooldown: int) -> EntryDetection:
    seg_sig = signal[segment.start:segment.end]
    raw = np.flatnonzero(seg_sig) + segment.start
    # Última confirmación válida: e + H - 1 <= end - 1  =>  t <= end - 1 - H
    last_ok = segment.end - 1 - holding_bars
    ok = raw[raw <= last_ok]
    kept = apply_cooldown(ok, cooldown)
    return EntryDetection(
        confirm_idx=kept,
        entry_idx=kept + 1,
        n_raw_signals=int(len(raw)),
        n_dropped_horizon=int(len(raw) - len(ok)),
        n_dropped_cooldown=int(len(ok) - len(kept)),
    )
