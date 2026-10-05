"""
Lenguaje de condiciones de entrada como ÁRBOL DE EXPRESIÓN.

Nodos hoja (condiciones simples):
  Compare(A, op, B)          op ∈ {>, >=, <, <=}            -> ESTADO
  Cross(A, B, "above")       A[t-1] <  B[t-1] y A[t] >= B[t] -> EVENTO
  Cross(A, B, "below")       A[t-1] >  B[t-1] y A[t] <= B[t] -> EVENTO

Nodos compuestos:
  And(X, Y), Or(X, Y), Not(X)
  Then(X, Y, n)              X ocurre en t1, Y en t2, t1 < t2 <= t1+n;
                             se confirma en t2.
  ContextTrigger(C, T)       C (ESTADO) y T (EVENTO) en la misma vela t (EXP-009).
  OccurredWithin(X, n)       X fue verdadera en alguna vela de [t-n, t-1].

Garantía anti look-ahead: cada nodo, al evaluarse en t, sólo usa valores de
sus hijos en t, t-1, …  (nunca shift negativo). Los operandos también son
causales (ver features.py). tests/test_core.py lo verifica empíricamente
truncando los datos.

Cada nodo evalúa a un par (valor, definido): `definido` es False mientras
algún operando necesario es NaN (p. ej. período de calentamiento de un
indicador). La señal final es valor & definido; así NOT no se vuelve
verdadero por accidente en zonas sin datos.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

import numpy as np

from .features import FeatureStore, Operand, operand_from_dict


class Kind(str, Enum):
    STATE = "STATE"   # puede permanecer verdadera muchas velas
    EVENT = "EVENT"   # ocurre en velas puntuales


Pair = tuple[np.ndarray, np.ndarray]  # (valor bool, definido bool)


def _shift(a: np.ndarray, k: int, fill=False) -> np.ndarray:
    """a desplazado k velas hacia el PASADO (out[t] = a[t-k]); k >= 1."""
    out = np.empty_like(a)
    out[:k] = fill
    out[k:] = a[:-k]
    return out


def _any_in_previous(a: np.ndarray, n: int) -> np.ndarray:
    """out[t] = any(a[t-n .. t-1]). Sólo pasado estricto."""
    cs = np.concatenate(([0], np.cumsum(a.astype(np.int64))))   # cs[i] = sum(a[:i])
    t = np.arange(len(a))
    hi = t              # suma hasta t-1 inclusive -> cs[t]
    lo = np.maximum(t - n, 0)
    return (cs[hi] - cs[lo]) > 0


class Condition(ABC):
    @abstractmethod
    def _eval(self, store: FeatureStore) -> Pair: ...

    @property
    @abstractmethod
    def key(self) -> str:
        """Clave canónica (dedupe/caché). Equivalentes conmutativos comparten clave."""

    @abstractmethod
    def describe(self) -> str: ...

    @property
    @abstractmethod
    def depth(self) -> int: ...

    @property
    @abstractmethod
    def kind(self) -> Kind: ...

    @abstractmethod
    def to_dict(self) -> dict[str, Any]: ...

    @abstractmethod
    def leaves(self) -> list["Condition"]: ...

    def evaluate_pair(self, store: FeatureStore) -> Pair:
        cached = store.get_bool(self.key)
        if cached is not None:
            return cached
        res = self._eval(store)
        store.put_bool(self.key, res)
        return res

    def evaluate(self, store: FeatureStore) -> np.ndarray:
        """Señal booleana: True en t si la condición se CONFIRMA al cierre de t."""
        v, d = self.evaluate_pair(store)
        return v & d

    def __str__(self) -> str:
        return self.describe()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.describe()}>"


# ---------------------------------------------------------------------- #
# Hojas
# ---------------------------------------------------------------------- #
_OPS = {">": np.greater, ">=": np.greater_equal, "<": np.less, "<=": np.less_equal}


class Compare(Condition):
    def __init__(self, left: Operand, op: str, right: Operand):
        if op not in _OPS:
            raise ValueError(f"Operador no soportado: {op}")
        self.left, self.op, self.right = left, op, right

    def _eval(self, store):
        a, b = store.get(self.left), store.get(self.right)
        d = ~(np.isnan(a) | np.isnan(b))
        with np.errstate(invalid="ignore"):
            v = _OPS[self.op](a, b)
        return v & d, d

    @property
    def key(self): return f"({self.left.key}{self.op}{self.right.key})"
    def describe(self): return f"{self.left.label} {self.op} {self.right.label}"
    @property
    def depth(self): return 1
    @property
    def kind(self): return Kind.STATE
    def leaves(self): return [self]

    def to_dict(self):
        return {"node": "compare", "left": self.left.to_dict(), "op": self.op,
                "right": self.right.to_dict()}


class Cross(Condition):
    def __init__(self, left: Operand, right: Operand, direction: str):
        if direction not in ("above", "below"):
            raise ValueError("direction debe ser 'above' o 'below'")
        self.left, self.right, self.direction = left, right, direction

    def _eval(self, store):
        a, b = store.get(self.left), store.get(self.right)
        a1, b1 = _shift(a, 1, np.nan), _shift(b, 1, np.nan)
        d = ~(np.isnan(a) | np.isnan(b) | np.isnan(a1) | np.isnan(b1))
        with np.errstate(invalid="ignore"):
            if self.direction == "above":
                v = (a1 < b1) & (a >= b)
            else:
                v = (a1 > b1) & (a <= b)
        return v & d, d

    @property
    def key(self): return f"(X{self.direction}:{self.left.key}|{self.right.key})"
    def describe(self): return f"{self.left.label} crosses {self.direction} {self.right.label}"
    @property
    def depth(self): return 1
    @property
    def kind(self): return Kind.EVENT
    def leaves(self): return [self]

    def to_dict(self):
        return {"node": "cross", "left": self.left.to_dict(), "right": self.right.to_dict(),
                "direction": self.direction}


# ---------------------------------------------------------------------- #
# Compuestos
# ---------------------------------------------------------------------- #
class And(Condition):
    def __init__(self, a: Condition, b: Condition):
        self.a, self.b = a, b

    def _eval(self, store):
        va, da = self.a.evaluate_pair(store)
        vb, db = self.b.evaluate_pair(store)
        d = da & db
        return va & vb & d, d

    @property
    def key(self): return "AND[" + "&".join(sorted((self.a.key, self.b.key))) + "]"
    def describe(self): return f"({self.a.describe()} AND {self.b.describe()})"
    @property
    def depth(self): return 1 + max(self.a.depth, self.b.depth)
    @property
    def kind(self):
        return Kind.EVENT if Kind.EVENT in (self.a.kind, self.b.kind) else Kind.STATE
    def leaves(self): return self.a.leaves() + self.b.leaves()
    def to_dict(self): return {"node": "and", "a": self.a.to_dict(), "b": self.b.to_dict()}


class Or(Condition):
    def __init__(self, a: Condition, b: Condition):
        self.a, self.b = a, b

    def _eval(self, store):
        va, da = self.a.evaluate_pair(store)
        vb, db = self.b.evaluate_pair(store)
        # Definida si ambos lados lo están (criterio conservador y simétrico).
        d = da & db
        return (va | vb) & d, d

    @property
    def key(self): return "OR[" + "|".join(sorted((self.a.key, self.b.key))) + "]"
    def describe(self): return f"({self.a.describe()} OR {self.b.describe()})"
    @property
    def depth(self): return 1 + max(self.a.depth, self.b.depth)
    @property
    def kind(self):
        return Kind.EVENT if self.a.kind == self.b.kind == Kind.EVENT else Kind.STATE
    def leaves(self): return self.a.leaves() + self.b.leaves()
    def to_dict(self): return {"node": "or", "a": self.a.to_dict(), "b": self.b.to_dict()}


class Not(Condition):
    def __init__(self, a: Condition):
        self.a = a

    def _eval(self, store):
        va, da = self.a.evaluate_pair(store)
        return (~va) & da, da

    @property
    def key(self): return f"NOT[{self.a.key}]"
    def describe(self): return f"NOT ({self.a.describe()})"
    @property
    def depth(self): return 1 + self.a.depth
    @property
    def kind(self): return Kind.STATE   # la negación de un evento es casi siempre verdadera
    def leaves(self): return self.a.leaves()
    def to_dict(self): return {"node": "not", "a": self.a.to_dict()}


class OccurredWithin(Condition):
    """
    X fue verdadera en alguna vela de [t-n, t-1] (pasado estricto, no incluye t).
    Es un MODIFICADOR temporal de X: no suma profundidad.
    """

    def __init__(self, a: Condition, n: int):
        if n < 1:
            raise ValueError("n >= 1")
        self.a, self.n = a, int(n)

    def _eval(self, store):
        sig = self.a.evaluate(store)
        _, da = self.a.evaluate_pair(store)
        v = _any_in_previous(sig, self.n)
        d = _shift(da, 1, False)
        return v & d, d

    @property
    def key(self): return f"WITHIN{self.n}[{self.a.key}]"
    def describe(self): return f"[{self.a.describe()}] occurred within previous {self.n} bars"
    @property
    def depth(self): return self.a.depth
    @property
    def kind(self): return Kind.STATE
    def leaves(self): return self.a.leaves()
    def to_dict(self): return {"node": "within", "a": self.a.to_dict(), "n": self.n}


class Then(Condition):
    """
    X THEN Y within n bars: existe t1 con X[t1], y Y[t2] con t1 < t2 <= t1+n.
    Se evalúa (y se confirma) en t2:  Then[t] = Y[t] AND any(X[t-n .. t-1]).

    Nota: es matemáticamente equivalente a  Y AND OccurredWithin(X, n);
    se mantiene como nodo propio por legibilidad y porque refleja la
    intención secuencial.
    """

    def __init__(self, a: Condition, b: Condition, n: int):
        if n < 1:
            raise ValueError("n >= 1")
        self.a, self.b, self.n = a, b, int(n)

    def _eval(self, store):
        sa = self.a.evaluate(store)
        _, da = self.a.evaluate_pair(store)
        vb, db = self.b.evaluate_pair(store)
        prev = _any_in_previous(sa, self.n)
        d = db & _shift(da, 1, False)
        return vb & prev & d, d

    @property
    def key(self): return f"THEN{self.n}[{self.a.key}>>{self.b.key}]"
    def describe(self):
        return f"({self.a.describe()} THEN {self.b.describe()} within {self.n} bars)"
    @property
    def depth(self): return 1 + max(self.a.depth, self.b.depth)
    @property
    def kind(self): return self.b.kind
    def leaves(self): return self.a.leaves() + self.b.leaves()
    def to_dict(self):
        return {"node": "then", "a": self.a.to_dict(), "b": self.b.to_dict(), "n": self.n}


class ContextTrigger(Condition):
    """
    Condición estructurada (EXP-009):   CONTEXT(...)  AND  TRIGGER(...)

    La separación es parte del tipo, no una etiqueta: el constructor exige que el CONTEXTO sea un
    ESTADO (puede seguir verdadero muchas velas) y que el DISPARADOR sea un EVENTO (ocurre en velas
    puntuales). Se confirma en la vela t sólo si, al cierre de t, el contexto es verdadero Y el
    disparador ocurre en esa misma vela; la entrada sigue siendo Open[t+1]. Como el disparador es un
    evento, un contexto verdadero durante 50 velas produce entradas sólo en las velas del evento y
    no una por vela. Equivale a And(contexto, disparador) para la evaluación; la diferencia es que
    la estructura queda registrada y validada (describe(), to_dict(), leaves del contexto vs. del
    disparador) y el generador sólo puede construirla con esta forma.
    """

    def __init__(self, context: Condition, trigger: Condition):
        if context.kind != Kind.STATE:
            raise ValueError(f"El contexto debe ser un ESTADO, no {context.kind.value}: {context.describe()}")
        if trigger.kind != Kind.EVENT:
            raise ValueError(f"El disparador debe ser un EVENTO, no {trigger.kind.value}: {trigger.describe()}")
        self.context, self.trigger = context, trigger

    def _eval(self, store):
        vc, dc = self.context.evaluate_pair(store)
        vt, dt = self.trigger.evaluate_pair(store)
        d = dc & dt
        return vc & vt & d, d

    @property
    def key(self): return f"CTX[{self.context.key}]&TRG[{self.trigger.key}]"
    def describe(self): return f"CONTEXT[{self.context.describe()}] AND TRIGGER[{self.trigger.describe()}]"
    @property
    def depth(self): return 1 + max(self.context.depth, self.trigger.depth)
    @property
    def kind(self): return Kind.EVENT
    def leaves(self): return self.context.leaves() + self.trigger.leaves()
    def to_dict(self):
        return {"node": "structured", "context": self.context.to_dict(), "trigger": self.trigger.to_dict()}


def condition_from_dict(d: dict[str, Any]) -> Condition:
    n = d["node"]
    if n == "compare":
        return Compare(operand_from_dict(d["left"]), d["op"], operand_from_dict(d["right"]))
    if n == "cross":
        return Cross(operand_from_dict(d["left"]), operand_from_dict(d["right"]), d["direction"])
    if n == "and":
        return And(condition_from_dict(d["a"]), condition_from_dict(d["b"]))
    if n == "or":
        return Or(condition_from_dict(d["a"]), condition_from_dict(d["b"]))
    if n == "not":
        return Not(condition_from_dict(d["a"]))
    if n == "within":
        return OccurredWithin(condition_from_dict(d["a"]), d["n"])
    if n == "structured":
        return ContextTrigger(condition_from_dict(d["context"]), condition_from_dict(d["trigger"]))
    if n == "then":
        return Then(condition_from_dict(d["a"]), condition_from_dict(d["b"]), d["n"])
    raise ValueError(f"Nodo desconocido: {n}")


def condition_id(cond: Condition) -> str:
    """ID corto y estable derivado de la clave canónica."""
    import hashlib
    return hashlib.sha1(cond.key.encode()).hexdigest()[:12]
