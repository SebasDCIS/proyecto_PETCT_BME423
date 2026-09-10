"""Paso 5a. Máscaras de órganos y reparto de los errores por órgano.

La pregunta del proyecto no es solo cuánto se equivoca cada fusión sino dónde. Para
responderla hace falta saber qué órgano hay debajo de cada vóxel, y eso lo da
TotalSegmentator: una red preentrenada que segmenta 117 estructuras en un CT. Sus etiquetas
son demasiado finas para el informe (cinco lóbulos pulmonares, veinticuatro vértebras...),
así que aquí se agrupan en unas pocas regiones que tienen sentido para el PET con FDG:

  higado, bazo, rinones, vejiga, corazon, estomago, intestino (duodeno, delgado, colon),
  pancreas_suprarrenales, pulmon, hueso, musculo, vasos, tiroides_esofago_traquea,
  encefalo (no existirá: el defacing borra la cabeza), otro (cuerpo sin etiqueta), fuera.

Las funciones principales:

  group_labels        TotalSegmentator (117 etiquetas) → mapa de grupos (uint8), con la
                      tabla de correspondencia.
  organs_to_grid      lleva el mapa de órganos (grilla del CT original) a la grilla de los
                      `.npz` del proyecto: remuestreo a 3 mm con vecino más cercano sobre
                      la misma referencia que usó el preprocesamiento y el mismo recorte.
  fp_by_organ         reparte los mililitros de falsos positivos de una predicción entre
                      los grupos de órganos. Un falso positivo es una componente conexa
                      predicha que no toca ninguna lesión anotada (igual que en la métrica
                      FPV); cada uno de sus vóxeles se cuenta en el grupo que tiene debajo.
  fn_by_organ         lo mismo para las lesiones anotadas que ninguna predicción tocó: en
                      qué órgano estaban las lesiones que se escaparon.

Con esto la tabla final del proyecto dice, por modelo: "de los 21 mL de falsos positivos por
paciente, 8 están en hígado, 5 en intestino, 3 en riñones...". Es lo que autoPET no midió.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import SimpleITK as sitk
from scipy import ndimage

_CONN26 = np.ones((3, 3, 3), dtype=bool)

# Grupos del proyecto → nombres de TotalSegmentator (tarea "total", v2). Los prefijos con
# "*" agrupan familias (vertebrae_*, rib_*...). El orden define el código numérico.
GROUPS: Dict[str, List[str]] = {
    "higado": ["liver"],
    "bazo": ["spleen"],
    "rinones": ["kidney_left", "kidney_right", "kidney_cyst_left", "kidney_cyst_right"],
    "vejiga": ["urinary_bladder"],
    "corazon": ["heart", "heart_myocardium", "heart_atrium_left", "heart_atrium_right",
                "heart_ventricle_left", "heart_ventricle_right"],
    "estomago": ["stomach"],
    "intestino": ["duodenum", "small_bowel", "colon"],
    "pancreas_suprarrenales": ["pancreas", "adrenal_gland_left", "adrenal_gland_right"],
    "pulmon": ["lung_upper_lobe_left", "lung_lower_lobe_left", "lung_upper_lobe_right",
               "lung_middle_lobe_right", "lung_lower_lobe_right"],
    "hueso": ["vertebrae_*", "rib_*", "sternum", "costal_cartilages", "humerus_left", "humerus_right",
              "scapula_left", "scapula_right", "clavicula_left", "clavicula_right", "femur_left",
              "femur_right", "hip_left", "hip_right", "sacrum", "skull"],
    "musculo": ["autochthon_left", "autochthon_right", "gluteus_maximus_left", "gluteus_maximus_right",
                "gluteus_medius_left", "gluteus_medius_right", "gluteus_minimus_left", "gluteus_minimus_right",
                "iliopsoas_left", "iliopsoas_right"],
    "vasos": ["aorta", "inferior_vena_cava", "portal_vein_and_splenic_vein", "iliac_artery_left",
              "iliac_artery_right", "iliac_vena_left", "iliac_vena_right", "pulmonary_vein",
              "brachiocephalic_trunk", "subclavian_artery_left", "subclavian_artery_right",
              "common_carotid_artery_left", "common_carotid_artery_right", "brachiocephalic_vein_left",
              "brachiocephalic_vein_right", "atrial_appendage_left", "superior_vena_cava"],
    "tiroides_esofago_traquea": ["thyroid_gland", "esophagus", "trachea"],
    "encefalo": ["brain"],
    "otros_organos": ["gallbladder", "prostate", "spinal_cord", "*"],   # "*" = cualquier etiqueta no asignada
}
GROUP_NAMES: List[str] = ["fuera", "otro"] + list(GROUPS.keys())   # 0 = fuera del cuerpo, 1 = cuerpo sin etiqueta
GROUP_CODE: Dict[str, int] = {n: i for i, n in enumerate(GROUP_NAMES)}


# Órganos que sirven como referencia interna del propio paciente, en orden de preferencia.
# Es la lógica de la escala de Deauville: en vez de comparar el SUV de un foco contra una
# tabla poblacional, se lo compara contra el hígado (o el fondo vascular) DEL MISMO estudio.
# Así se cancelan de un golpe la dosis inyectada, el tiempo de captación, la glicemia y el
# peso, que son las causas reales de que el "hígado normal" varíe tanto de persona a persona.
REF_INTERNA_ORDEN: List[str] = ["higado", "vasos", "bazo"]
MIN_VOXELES_REF = 500          # por debajo de esto la mediana del órgano no es fiable


def internal_reference(suv: np.ndarray, groups: np.ndarray, valid: np.ndarray) -> Tuple[float, str]:
    """Referencia interna del paciente: mediana de SUV de su propio hígado.

    `valid` debe traer ya excluidos el aire, la zona borrada por el defacing y la lesión
    anotada (con su margen). Si el hígado no está disponible o quedó demasiado chico, baja
    al fondo vascular y después al bazo; como último recurso usa la mediana de todo el
    cuerpo, que es peor pero nunca falla. Devuelve (valor, de dónde salió).
    """
    for name in REF_INTERNA_ORDEN:
        m = valid & (groups == GROUP_CODE[name])
        if int(m.sum()) >= MIN_VOXELES_REF:
            v = float(np.median(suv[m]))
            if v > 0:
                return v, name
    if int(valid.sum()) == 0:
        return float("nan"), "ninguna"
    v = float(np.median(suv[valid]))
    return (v, "cuerpo") if v > 0 else (float("nan"), "ninguna")


def _match(name: str, patterns: Iterable[str]) -> bool:
    for p in patterns:
        if p == "*":
            continue
        if p.endswith("*") and name.startswith(p[:-1]):
            return True
        if p == name:
            return True
    return False


def label_to_group_table(class_map: Dict[int, str]) -> np.ndarray:
    """Tabla de 256 entradas: etiqueta de TotalSegmentator → código de grupo."""
    table = np.zeros(256, dtype=np.uint8)          # 0 (fondo) → 'fuera'
    for lbl, name in class_map.items():
        code = GROUP_CODE["otros_organos"]
        for g, pats in GROUPS.items():
            if _match(name, pats):
                code = GROUP_CODE[g]
                break
        table[int(lbl)] = code
    return table


def group_labels(ts_labels: np.ndarray, class_map: Dict[int, str], body: np.ndarray | None = None) -> np.ndarray:
    """Mapa de TotalSegmentator (uint8, 0..117) → mapa de grupos. Donde hay cuerpo pero
    ninguna etiqueta (grasa, piel, tejido blando genérico) queda 'otro'."""
    table = label_to_group_table(class_map)
    groups = table[ts_labels.astype(np.uint8)]
    if body is not None:
        groups = np.where((groups == 0) & body.astype(bool), GROUP_CODE["otro"], groups)
    return groups.astype(np.uint8)


def organs_to_grid(organs_img: sitk.Image, reference_img: sitk.Image, spacing=(3.0, 3.0, 3.0),
                   bbox: np.ndarray | None = None) -> np.ndarray:
    """Lleva el mapa de órganos (grilla del CT original) a la grilla de los `.npz`.

    Primero se remuestrea sobre la referencia (la imagen SUV del estudio, que es la grilla
    común PET/CT), luego a 3 mm isotrópicos con vecino más cercano, exactamente como
    `preprocess.resample_iso`, y por último se recorta con la misma caja `bbox` que se
    guardó en el `.npz`. Así el mapa queda vóxel a vóxel con `suv`, `ct`, `seg` y `body`.
    """
    from .preprocess import resample_iso

    on_ref = sitk.Resample(organs_img, reference_img, sitk.Transform(), sitk.sitkNearestNeighbor, 0, sitk.sitkUInt8)
    iso = resample_iso(on_ref, spacing, is_mask=True)
    arr = sitk.GetArrayFromImage(iso).astype(np.uint8)
    if bbox is not None:
        sl = tuple(slice(int(a), int(b)) for a, b in bbox)
        arr = arr[sl]
    return arr


def _false_positive_mask(pred: np.ndarray, gt: np.ndarray) -> np.ndarray:
    """Vóxeles de las componentes predichas que no tocan ninguna lesión anotada."""
    pred, gt = pred.astype(bool), gt.astype(bool)
    labels, n = ndimage.label(pred, structure=_CONN26)
    if n == 0:
        return np.zeros_like(pred)
    idx = np.arange(1, n + 1)
    overlap = np.asarray(ndimage.sum(gt, labels, idx))
    fp_labels = idx[overlap == 0]
    return np.isin(labels, fp_labels)


def _false_negative_mask(pred: np.ndarray, gt: np.ndarray) -> np.ndarray:
    """Vóxeles de las lesiones anotadas que ninguna predicción tocó."""
    pred, gt = pred.astype(bool), gt.astype(bool)
    labels, n = ndimage.label(gt, structure=_CONN26)
    if n == 0:
        return np.zeros_like(gt)
    idx = np.arange(1, n + 1)
    overlap = np.asarray(ndimage.sum(pred, labels, idx))
    return np.isin(labels, idx[overlap == 0])


def _ml_by_group(mask: np.ndarray, groups: np.ndarray, ml_per_voxel: float) -> Dict[str, float]:
    counts = np.bincount(groups[mask.astype(bool)].ravel(), minlength=len(GROUP_NAMES))
    return {name: float(counts[i] * ml_per_voxel) for i, name in enumerate(GROUP_NAMES)}


def fp_by_organ(pred: np.ndarray, gt: np.ndarray, groups: np.ndarray, ml_per_voxel: float) -> Dict[str, float]:
    """mL de falsos positivos por grupo de órgano. La suma es el FPV del estudio."""
    return _ml_by_group(_false_positive_mask(pred, gt), groups, ml_per_voxel)


def fn_by_organ(pred: np.ndarray, gt: np.ndarray, groups: np.ndarray, ml_per_voxel: float) -> Dict[str, float]:
    """mL de lesiones no detectadas por grupo de órgano (dónde estaban las que se escaparon).
    La suma es el FNV del estudio."""
    return _ml_by_group(_false_negative_mask(pred, gt), groups, ml_per_voxel)


def lesion_by_organ(gt: np.ndarray, groups: np.ndarray, ml_per_voxel: float) -> Dict[str, float]:
    """mL de lesión anotada por grupo: el denominador natural para leer los FN."""
    return _ml_by_group(gt.astype(bool), groups, ml_per_voxel)
