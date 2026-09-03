"""Paso 2. Preprocesamiento: dejar cada estudio en la forma que la red va a mirar.

Entrada: los NIfTI del Paso 1 (SUV, CTres, SEG en la grilla del PET).
Salida: un archivo .npz por estudio con tres volúmenes alineados a 3 mm isotrópicos,
ya recortados al cuerpo y escalados a [0, 1], más la geometría necesaria para volver
a mm y a mL después.

Por qué cada operación:
  remuestreo isotrópico   la red usa convoluciones cúbicas; si un vóxel mide 2 x 2 x 3 mm
                          la "esfera" que ve la red es un elipsoide. A 3 mm parejos el
                          volumen entero cabe en memoria y las lesiones relevantes (> 1 cm)
                          siguen ocupando varios vóxeles.
  ventaneo del CT         igual que en la consola: se recorta a tejido blando (-200 a 300
                          HU) para que hueso y aire no dominen el rango.
  tope del SUV            la vejiga puede pasar de SUV 50; sin tope, todo lo demás queda
                          comprimido cerca de cero al escalar a [0, 1].
  recorte al cuerpo       fuera del paciente solo hay aire y camilla. Recortar reduce el
                          volumen a la mitad o menos sin perder nada.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import SimpleITK as sitk
from scipy import ndimage


# ---------------------------------------------------------------- remuestreo
def resample_iso(img: sitk.Image, spacing=(3.0, 3.0, 3.0), is_mask: bool = False,
                 default_value: float = 0.0) -> sitk.Image:
    """Remuestrea a vóxeles cúbicos. Máscaras con vecino más cercano (no se inventan
    valores intermedios); imágenes con interpolación lineal."""
    old_sp = np.array(img.GetSpacing())
    old_sz = np.array(img.GetSize())
    new_sz = np.maximum(1, np.round(old_sz * old_sp / np.array(spacing))).astype(int)
    interp = sitk.sitkNearestNeighbor if is_mask else sitk.sitkLinear
    return sitk.Resample(img, [int(s) for s in new_sz], sitk.Transform(), interp,
                         img.GetOrigin(), [float(s) for s in spacing], img.GetDirection(),
                         default_value, img.GetPixelID())


# ---------------------------------------------------------------- escalado a [0, 1]
def window_ct(hu: np.ndarray, lo: float = -200.0, hi: float = 300.0) -> np.ndarray:
    """Ventana de tejido blando llevada a [0, 1]. Es la operación puntual clásica del
    curso: todo bajo `lo` queda en 0, todo sobre `hi` en 1, el medio es lineal."""
    return np.clip((hu.astype(np.float32) - lo) / (hi - lo), 0.0, 1.0)


def scale_suv(suv: np.ndarray, top: float = 30.0) -> np.ndarray:
    """SUV a [0, 1] con tope. SUV 30 pasa a 1; SUV 2,5 queda en 0,083."""
    return np.clip(suv.astype(np.float32) / top, 0.0, 1.0)


# ---------------------------------------------------------------- cuerpo
def body_mask(hu: np.ndarray, threshold: float = -500.0) -> np.ndarray:
    """Máscara del paciente a partir del CT: lo que no es aire, componente más grande,
    con los huecos internos (pulmón, intestino) rellenados corte a corte."""
    raw = hu > threshold
    raw = ndimage.binary_opening(raw, iterations=1)
    labels, n = ndimage.label(raw)
    if n == 0:
        return np.zeros_like(raw, dtype=bool)
    sizes = ndimage.sum(raw, labels, range(1, n + 1))
    body = labels == (1 + int(np.argmax(sizes)))
    for z in range(body.shape[0]):  # relleno 2D: evita cerrar la "tapa" de arriba y abajo
        body[z] = ndimage.binary_fill_holes(body[z])
    return body


def bbox_of(mask: np.ndarray, margin: int = 2) -> Tuple[slice, slice, slice]:
    """Caja mínima que contiene la máscara, con un margen de vóxeles."""
    idx = np.where(mask)
    if idx[0].size == 0:
        return tuple(slice(0, s) for s in mask.shape)
    out = []
    for ax in range(3):
        lo = max(int(idx[ax].min()) - margin, 0)
        hi = min(int(idx[ax].max()) + margin + 1, mask.shape[ax])
        out.append(slice(lo, hi))
    return tuple(out)


# ---------------------------------------------------------------- estudio completo
def preprocess_study(nifti_dir: str | Path, out_file: str | Path, spacing=(3.0, 3.0, 3.0),
                     window=(-200.0, 300.0), suv_top: float = 30.0) -> Dict[str, object]:
    """Lee SUV, CTres y SEG; remuestrea; recorta al cuerpo; escala; guarda un .npz.

    El .npz contiene: suv (float16, [0,1]), ct (float16, [0,1]), seg (uint8), body (uint8),
    suv_raw_max (float, para reconstruir SUV real = suv * suv_top), spacing, origin,
    bbox (para volver a la grilla remuestreada) y shape_resampled.
    """
    nifti_dir, out_file = Path(nifti_dir), Path(out_file)
    suv_img = resample_iso(sitk.ReadImage(str(nifti_dir / "SUV.nii.gz")), spacing)
    ct_img = resample_iso(sitk.ReadImage(str(nifti_dir / "CTres.nii.gz")), spacing, default_value=-1024.0)
    seg_img = resample_iso(sitk.ReadImage(str(nifti_dir / "SEG.nii.gz")), spacing, is_mask=True)

    suv = sitk.GetArrayFromImage(suv_img).astype(np.float32)
    hu = sitk.GetArrayFromImage(ct_img).astype(np.float32)
    seg = sitk.GetArrayFromImage(seg_img).astype(np.uint8)

    body = body_mask(hu)
    box = bbox_of(body)
    suv, hu, seg, body = suv[box], hu[box], seg[box], body[box]

    out_file.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_file,
        suv=scale_suv(suv, suv_top).astype(np.float16),
        ct=window_ct(hu, *window).astype(np.float16),
        seg=seg, body=body.astype(np.uint8),
        suv_top=np.float32(suv_top),
        spacing=np.array(spacing, dtype=np.float32),
        origin=np.array(suv_img.GetOrigin(), dtype=np.float64),
        bbox=np.array([[s.start, s.stop] for s in box], dtype=np.int32),
        shape_resampled=np.array(suv_img.GetSize()[::-1], dtype=np.int32),
        # En DICOM (sistema LPS) z crece hacia la cabeza. Si la dirección z es +1, el
        # índice 0 del arreglo es el corte más inferior y la cabeza queda al FINAL.
        head_at_end=np.bool_(suv_img.GetDirection()[8] > 0),
    )
    return {"shape": suv.shape, "lesion_voxels": int(seg.sum()),
            "ml_per_voxel": float(np.prod(spacing) / 1000.0)}


def load_study(npz_file: str | Path) -> Dict[str, np.ndarray]:
    """Carga el .npz y devuelve los volúmenes en float32/uint8 listos para usar."""
    d = np.load(npz_file)
    return {"suv": d["suv"].astype(np.float32), "ct": d["ct"].astype(np.float32),
            "seg": d["seg"].astype(np.uint8), "body": d["body"].astype(bool),
            "suv_top": float(d["suv_top"]), "spacing": d["spacing"].astype(float),
            "head_at_end": bool(d["head_at_end"]) if "head_at_end" in d else True}


# ---------------------------------------------------------------- parches
def sample_patch(vol: Dict[str, np.ndarray], size=(96, 96, 96), p_lesion: float = 0.7,
                 rng: np.random.Generator | None = None) -> Dict[str, np.ndarray]:
    """Recorta un cubo del estudio. Con probabilidad `p_lesion` el centro cae sobre un
    vóxel de lesión; si no, sobre un vóxel del cuerpo. Si el volumen es más chico que el
    parche en algún eje, se rellena con ceros (aire) para completar el tamaño.

    Por qué el sesgo: las lesiones ocupan menos del 1 % del cuerpo. Con parches al azar
    la red vería casi solo fondo y aprendería a decir "nada" en todas partes.
    """
    rng = rng or np.random.default_rng()
    seg, body = vol["seg"], vol["body"]
    shape = np.array(seg.shape)
    size = np.array(size)

    use_lesion = seg.any() and rng.random() < p_lesion
    pool = np.argwhere(seg > 0) if use_lesion else np.argwhere(body)
    if pool.size == 0:
        pool = np.array([shape // 2])
    center = pool[rng.integers(len(pool))]
    start = center - size // 2
    start = np.clip(start, 0, np.maximum(shape - size, 0))
    stop = start + size

    out = {}
    for key in ("suv", "ct", "seg"):
        arr = vol[key]
        patch = np.zeros(size, dtype=arr.dtype)
        src = tuple(slice(int(a), int(min(b, s))) for a, b, s in zip(start, stop, shape))
        dst = tuple(slice(0, sl.stop - sl.start) for sl in src)
        patch[dst] = arr[src]
        out[key] = patch
    out["start"] = start
    out["with_lesion"] = bool(out["seg"].any())
    return out
