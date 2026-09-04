"""Referencia clásica (OE1): segmentar lesiones sin ninguna red.

Es la receta que un físico médico habría usado antes del aprendizaje profundo, y es
el piso contra el que se comparan los tres modelos:

  1. umbral       SUV >= 2,5 marca todo lo "caliente".
  2. morfología   apertura con una bola de radio 1: borra puntos sueltos de ruido y
                  separa estructuras unidas por un solo vóxel.
  3. tamaño       se descartan componentes de menos de 0,5 mL.
  4. anatomía     se descartan las componentes que caen dentro de máscaras de órganos
                  con captación fisiológica (encéfalo, corazón, riñones, vejiga...).

El paso 4 es el que hace la diferencia y el que depende de tener máscaras de
órganos. Cuando existen (por ejemplo, de TotalSegmentator sobre el CT) se usan tal
cual. Mientras no existan, `heuristic_organ_masks` construye dos aproximaciones
gruesas a partir de la geometría del cuerpo (encéfalo: componente caliente más
alta del estudio; vejiga: componente caliente más baja y muy intensa). Es una
aproximación declarada como provisional en la bitácora, no un sustituto del atlas.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
from scipy import ndimage
from skimage.morphology import ball

_CONN26 = np.ones((3, 3, 3), dtype=bool)


def threshold_suv(suv: np.ndarray, thr: float = 2.5) -> np.ndarray:
    return suv >= thr


def clean_mask(mask: np.ndarray, open_radius: int = 1, min_ml: float = 0.5,
               ml_per_voxel: float = 0.027) -> np.ndarray:
    """Apertura morfológica + eliminación de componentes chicas."""
    out = ndimage.binary_opening(mask, structure=ball(open_radius)) if open_radius > 0 else mask.copy()
    labels, n = ndimage.label(out, structure=_CONN26)
    if n == 0:
        return out
    min_vox = max(1, int(round(min_ml / ml_per_voxel)))
    sizes = ndimage.sum(out, labels, range(1, n + 1))
    keep = np.zeros(n + 1, dtype=bool)
    keep[1:] = sizes >= min_vox
    return keep[labels]


def exclude_organs(mask: np.ndarray, organ_masks: Dict[str, np.ndarray],
                   overlap_frac: float = 0.5) -> np.ndarray:
    """Quita las componentes que están, en más de `overlap_frac` de su volumen, dentro
    de alguna máscara de órgano fisiológico."""
    labels, n = ndimage.label(mask, structure=_CONN26)
    if n == 0 or not organ_masks:
        return mask.copy()
    organs = np.zeros_like(mask, dtype=bool)
    for m in organ_masks.values():
        organs |= m.astype(bool)
    # fracción de cada componente que cae dentro de órganos, calculada de una vez para
    # todas las componentes (recorrerlas una a una con labels == k es cien veces más lento)
    idx = np.arange(1, n + 1)
    frac = np.asarray(ndimage.mean(organs.astype(np.float32), labels, idx))
    keep = np.ones(n + 1, dtype=bool)
    keep[0] = False
    keep[1:] = frac <= overlap_frac
    return keep[labels]


def heuristic_organ_masks(suv: np.ndarray, body: np.ndarray, ml_per_voxel: float,
                          brain_min_ml: float = 200.0, bladder_min_ml: float = 20.0,
                          bladder_suv: float = 10.0, head_at_end: bool = True) -> Dict[str, np.ndarray]:
    """Máscaras provisionales de encéfalo y vejiga a partir del propio PET.

    Encéfalo: la componente caliente (SUV >= 2,5) más grande cuyo centroide está en el
    20 % superior del cuerpo y que supera `brain_min_ml`. Vejiga: componente con SUV
    máximo >= `bladder_suv`, centroide en el 40 % inferior y volumen >= `bladder_min_ml`.
    Son reglas de andamio para poder medir algo hoy; se reemplazan por máscaras del CT.

    `head_at_end` dice hacia dónde está la cabeza en el arreglo. En los NIfTI de autoPET
    el índice 0 es el corte más inferior (z de DICOM crece hacia la cabeza), así que la
    cabeza está al final. Si se ignora, las reglas se aplican al revés: la vejiga pasa por
    encéfalo y las lesiones torácicas por vejiga. Pasó, y está en la bitácora.
    """
    hot = suv >= 2.5
    labels, n = ndimage.label(hot, structure=_CONN26)
    out: Dict[str, np.ndarray] = {}
    if n == 0:
        return out
    nz = suv.shape[0]
    zs = np.where(body.any(axis=(1, 2)))[0]
    z_top, z_bot = (zs.min(), zs.max()) if zs.size else (0, nz - 1)
    height = max(z_bot - z_top, 1)
    idx = np.arange(1, n + 1)
    vols_ml = np.asarray(ndimage.sum(hot, labels, idx)) * ml_per_voxel
    cz = np.array([c[0] for c in ndimage.center_of_mass(hot, labels, idx)])
    smax = np.asarray(ndimage.maximum(suv, labels, idx))
    head_idx = z_bot if head_at_end else z_top
    rel = np.abs(cz - head_idx) / height  # 0 = cabeza, 1 = pies
    brain_cand = np.where((rel < 0.2) & (vols_ml >= brain_min_ml))[0]
    if brain_cand.size:
        k = brain_cand[np.argmax(vols_ml[brain_cand])]
        out["encefalo"] = labels == (k + 1)
    bladder_cand = np.where((rel > 0.6) & (vols_ml >= bladder_min_ml) & (smax >= bladder_suv))[0]
    if bladder_cand.size:
        out["vejiga"] = np.isin(labels, bladder_cand + 1)
    return out


def classical_segmentation(suv: np.ndarray, body: np.ndarray, ml_per_voxel: float,
                           thr: float = 2.5, open_radius: int = 1, min_ml: float = 0.5,
                           organ_masks: Optional[Dict[str, np.ndarray]] = None,
                           use_heuristics: bool = True, head_at_end: bool = True) -> np.ndarray:
    """Receta completa. `suv` en unidades reales (no escalado a [0,1])."""
    mask = threshold_suv(suv, thr) & body.astype(bool)
    mask = clean_mask(mask, open_radius, min_ml, ml_per_voxel)
    organs = dict(organ_masks or {})
    if use_heuristics and not organs:
        organs = heuristic_organ_masks(suv, body, ml_per_voxel, head_at_end=head_at_end)
    return exclude_organs(mask, organs)
