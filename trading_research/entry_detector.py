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
  2. Re-entrada por condición (independiente para cada condición; señales
     de condiciones distintas nunca se filtran entre sí):
     - modo "fixed": una señal en t se acepta sólo si
       t - t_ultima_aceptada >= MIN_BARS_BETWEEN_SAME_CONDITION_ENTRIES.
     - modo "until_exit": una señal en t se acepta sólo si la operación
       anterior ya cerró: t >= x, donde x es la vela en la que salió
       (toque de TP/SL o fin del horizonte). La nueva entrada es Open[t+1],
       posterior al cierre. Saber si la operación anterior cerró en una vela
       <= t no es look-ahead: es información disponible en t.

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


def trade_intervals(entry_idx: np.ndarray, holding_bars: int,
                    exit_offset: np.ndarray | None = None) -> dict[str, np.ndarray]:
    """
    Intervalos temporales de cada operación (posiciones enteras en el DataFrame):
      signal_idx   t        vela de confirmación (la señal sólo usa datos <= t)
      entry_idx    e = t+1  precio de entrada = Open[e]
      exit_idx     e+k      vela en la que sale (TP/SL/tiempo); sólo si se pasa exit_offset
      info_end_idx e+H-1    ÚLTIMA vela que toca el resultado de la operación. Es la que
                            decide purga/embargo: MFE/MAE y las métricas "favorables" miran
                            todo el horizonte aunque TP/SL cierren antes, así que el
                            intervalo de información es [t, e+H-1], no [t, exit].
    Una operación puede evaluarse en un segmento [start, end) sin filtrar información de
    otro segmento si y sólo si start <= t y info_end_idx <= end-1 (ver `fits_in_segment`).
    """
    e = np.asarray(entry_idx, dtype=np.int64)
    out = {"signal_idx": e - 1, "entry_idx": e, "info_end_idx": e + holding_bars - 1}
    if exit_offset is not None:
        out["exit_idx"] = e + exit_offset[e].astype(np.int64)
    return out


def fits_in_segment(entry_idx: np.ndarray, holding_bars: int, segment: Segment) -> np.ndarray:
    """Máscara: el intervalo [t, e+H-1] de la operación cae entero dentro del segmento."""
    iv = trade_intervals(entry_idx, holding_bars)
    return (iv["signal_idx"] >= segment.start) & (iv["info_end_idx"] <= segment.end - 1)


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


def apply_until_exit(candidates: np.ndarray, exit_offset: np.ndarray) -> np.ndarray:
    """
    Acepta una señal y salta todas las siguientes hasta que la operación cierre.
    exit_offset[e] = k  =>  la operación que entra en e sale en la vela e+k.
    """
    accepted = []
    i, n = 0, len(candidates)
    while i < n:
        t = int(candidates[i])
        accepted.append(t)
        e = t + 1
        exit_bar = e + int(exit_offset[e])
        i = int(np.searchsorted(candidates, exit_bar, side="left"))
    return np.asarray(accepted, dtype=np.int64)


def detect_entries(signal: np.ndarray, segment: Segment, holding_bars: int,
                   cooldown: int, mode: str = "fixed",
                   exit_offset: np.ndarray | None = None) -> EntryDetection:
    seg_sig = signal[segment.start:segment.end]
    raw = np.flatnonzero(seg_sig) + segment.start
    # Última confirmación válida: e + H - 1 <= end - 1  =>  t <= end - 1 - H
    last_ok = segment.end - 1 - holding_bars
    ok = raw[raw <= last_ok]
    if mode == "until_exit":
        if exit_offset is None:
            raise ValueError("El modo 'until_exit' requiere exit_offset.")
        kept = apply_until_exit(ok, exit_offset)
    else:
        kept = apply_cooldown(ok, cooldown)
    return EntryDetection(
        confirm_idx=kept,
        entry_idx=kept + 1,
        n_raw_signals=int(len(raw)),
        n_dropped_horizon=int(len(raw) - len(ok)),
        n_dropped_cooldown=int(len(ok) - len(kept)),
    )
