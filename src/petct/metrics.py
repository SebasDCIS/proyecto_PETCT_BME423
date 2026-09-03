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
    fp_vox = 0
    for k in range(1, n + 1):
        comp = labels == k
        if not np.any(gt[comp]):
            fp_vox += int(comp.sum())
    return fp_vox * ml_per_voxel


def false_negative_volume(pred: np.ndarray, gt: np.ndarray, ml_per_voxel: float) -> float:
    """mL de lesiones anotadas que la predicción no tocó."""
    pred, gt = pred.astype(bool), gt.astype(bool)
    labels, n = ndimage.label(gt, structure=_CONN26)
    fn_vox = 0
    for k in range(1, n + 1):
        comp = labels == k
        if not np.any(pred[comp]):
            fn_vox += int(comp.sum())
    return fn_vox * ml_per_voxel


def mtv(mask: np.ndarray, ml_per_voxel: float) -> float:
    return float(mask.astype(bool).sum() * ml_per_voxel)


def suvmax(suv: np.ndarray, mask: np.ndarray) -> float:
    m = mask.astype(bool)
    return float(suv[m].max()) if m.any() else 0.0


def evaluate_study(pred: np.ndarray, gt: np.ndarray, suv: np.ndarray, ml_per_voxel: float) -> Dict[str, float]:
    """Todas las métricas de un estudio en un diccionario (una fila de la tabla final)."""
    return {
        "dice": dice(pred, gt),
        "fpv_ml": false_positive_volume(pred, gt, ml_per_voxel),
        "fnv_ml": false_negative_volume(pred, gt, ml_per_voxel),
        "mtv_pred_ml": mtv(pred, ml_per_voxel),
        "mtv_gt_ml": mtv(gt, ml_per_voxel),
        "suvmax_pred": suvmax(suv, pred),
        "suvmax_gt": suvmax(suv, gt),
    }
