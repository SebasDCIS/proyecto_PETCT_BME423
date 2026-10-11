"""Rama `extendido`, paso 5. Postproceso: la regla del doble del hígado propio.

Cada isla predicha (componente 26-conexa) se compara con el hígado sano del MISMO paciente: si
su SUV máximo no llega a `k` veces la referencia interna, se borra. Es la lógica de Deauville
aplicada a la salida de la red, la misma regla que `experimentos/23_curva_rechazo.py` exploró en
el acto 1 (k = 2: −40 % de marcas falsas, −2,3 % de lesiones detectadas).

La referencia es `petct.organs.internal_reference` sobre el cuerpo visible: mediana del SUV del
hígado (o vasos, o bazo, en ese orden) SIN excluir la lesión anotada, porque en un estudio nuevo
no hay anotación. Así la regla se puede aplicar al test sin mirar las respuestas.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage

from .organs import internal_reference

CONN = np.ones((3, 3, 3), dtype=int)


def referencia_higado(suv: np.ndarray, groups: np.ndarray, body: np.ndarray) -> float:
    ref, _ = internal_reference(suv, groups, body.astype(bool) & (suv > 0))
    return float(ref)


def regla_higado(pred: np.ndarray, suv: np.ndarray, ref: float, k: float = 2.0) -> np.ndarray:
    """Devuelve `pred` sin las islas cuyo SUV máximo es menor que k × ref."""
    pred = pred.astype(bool)
    if not np.isfinite(ref) or ref <= 0 or not pred.any():
        return pred
    lab, n = ndimage.label(pred, CONN)
    smax = np.asarray(ndimage.maximum(suv, lab, np.arange(1, n + 1)))
    quedan = np.concatenate([[False], smax >= k * ref])
    return quedan[lab]
