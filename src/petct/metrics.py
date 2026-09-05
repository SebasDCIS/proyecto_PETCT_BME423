"""Métricas del proyecto, con las mismas definiciones que usa el reto autoPET.

Las tres oficiales:
  Dice   2 |A ∩ B| / (|A| + |B|). Solapamiento entre predicción y verdad. Solo se
         calcula en estudios con lesión anotada (en un negativo perfecto sería 0/0).
  FPV    volumen, en mL, de las componentes conexas predichas que no tocan ninguna
         lesión anotada. Lo que la red "inventó".
  FNV    volumen, en mL, de las lesiones anotadas que la predicción no tocó ni con
         un vóxel. Lo que la red "no vio".

Y dos clínicas:
  MTV    volumen tumoral metabólico: vóxeles de la máscara por mL/vóxel.
  SUVmax el SUV más alto dentro de la máscara.

Las componentes conexas se calculan con vecindad 3D completa (26 vecinos), como en
el script oficial (scipy.ndimage.label con estructura de 3x3x3).
"""
from __future__ import annotations

from typing import Dict

import pandas as pd

import numpy as np
from scipy import ndimage

_CONN26 = np.ones((3, 3, 3), dtype=bool)


def dice(pred: np.ndarray, gt: np.ndarray) -> float:
    pred, gt = pred.astype(bool), gt.astype(bool)
    denom = pred.sum() + gt.sum()
    if denom == 0:
        return float("nan")
    return float(2.0 * np.logical_and(pred, gt).sum() / denom)


def false_positive_volume(pred: np.ndarray, gt: np.ndarray, ml_per_voxel: float) -> float:
    """mL de componentes predichas sin ningún vóxel de verdad debajo."""
    pred, gt = pred.astype(bool), gt.astype(bool)
    labels, n = ndimage.label(pred, structure=_CONN26)
    if n == 0:
        return 0.0
    idx = np.arange(1, n + 1)
    overlap = np.asarray(ndimage.sum(gt, labels, idx))       # vóxeles de verdad bajo cada isla
    sizes = np.asarray(ndimage.sum(pred, labels, idx))
    return float(sizes[overlap == 0].sum() * ml_per_voxel)


def false_negative_volume(pred: np.ndarray, gt: np.ndarray, ml_per_voxel: float) -> float:
    """mL de lesiones anotadas que la predicción no tocó."""
    pred, gt = pred.astype(bool), gt.astype(bool)
    labels, n = ndimage.label(gt, structure=_CONN26)
    if n == 0:
        return 0.0
    idx = np.arange(1, n + 1)
    overlap = np.asarray(ndimage.sum(pred, labels, idx))
    sizes = np.asarray(ndimage.sum(gt, labels, idx))
    return float(sizes[overlap == 0].sum() * ml_per_voxel)


def mtv(mask: np.ndarray, ml_per_voxel: float) -> float:
    return float(mask.astype(bool).sum() * ml_per_voxel)


def suvmax(suv: np.ndarray, mask: np.ndarray) -> float:
    m = mask.astype(bool)
    return float(suv[m].max()) if m.any() else 0.0


def blank_region_mask(suv: np.ndarray) -> np.ndarray:
    """Vóxeles SIN imagen: donde el PET vale exactamente 0. En autoPET es la caja que el
    defacing borró (toda la cabeza). La anotación del experto se hizo sobre la imagen
    original y conserva lesiones dentro de esa caja; como ahí no queda señal, ningún
    método puede encontrarlas, y evaluarlas sería medir el defacing y no el modelo."""
    return suv <= 0.0


def evaluate_study(pred: np.ndarray, gt: np.ndarray, suv: np.ndarray, ml_per_voxel: float,
                   exclude_blank: bool = True) -> Dict[str, float]:
    """Todas las métricas de un estudio en un diccionario (una fila de la tabla final).

    Con `exclude_blank` (por defecto) se descartan, en la predicción y en la verdad, los
    vóxeles de la zona sin imagen (SUV = 0). `gt_excluido_ml` deja constancia de cuánta
    lesión anotada quedó fuera de la evaluación por ese motivo. Con `exclude_blank=False`
    se obtiene exactamente la métrica del reto, sin corrección."""
    pred, gt = pred.astype(bool), gt.astype(bool)
    excluido = 0.0
    if exclude_blank:
        blank = blank_region_mask(suv)
        excluido = float((gt & blank).sum() * ml_per_voxel)
        pred, gt = pred & ~blank, gt & ~blank
    return {
        "gt_excluido_ml": excluido,
        "dice": dice(pred, gt),
        "fpv_ml": false_positive_volume(pred, gt, ml_per_voxel),
        "fnv_ml": false_negative_volume(pred, gt, ml_per_voxel),
        "mtv_pred_ml": mtv(pred, ml_per_voxel),
        "mtv_gt_ml": mtv(gt, ml_per_voxel),
        "suvmax_pred": suvmax(suv, pred),
        "suvmax_gt": suvmax(suv, gt),
    }


def summarize(df: pd.DataFrame) -> Dict[str, float]:
    """Resumen como en el reto: Dice solo en positivos; FPV en todos; FNV en positivos."""
    pos = df[df.mtv_gt_ml > 0]
    neg = df[df.mtv_gt_ml == 0]
    return {
        "n": int(len(df)), "n_pos": int(len(pos)),
        "dice_pos": float(pos.dice.mean()) if len(pos) else float("nan"),
        "dice_pos_mediana": float(pos.dice.median()) if len(pos) else float("nan"),
        "fpv_ml": float(df.fpv_ml.mean()),
        "fnv_ml_pos": float(pos.fnv_ml.mean()) if len(pos) else float("nan"),
        "fpv_ml_neg": float(neg.fpv_ml.mean()) if len(neg) else float("nan"),
    }
