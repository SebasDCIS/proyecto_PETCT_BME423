"""Conversión de un estudio PET/CT de TCIA (DICOM) a los NIfTI que usa el proyecto.

Salidas por estudio (misma convención que autoPET):
    CT.nii.gz     CT en unidades Hounsfield, en su grilla nativa (~0.98 mm, cortes 2–3 mm)
    PET.nii.gz    PET en Bq/mL, grilla nativa (2.04 × 2.04 × 3 mm)
    SUV.nii.gz    PET convertido a SUVbw (ver suv.py)
    CTres.nii.gz  CT remuestreado a la grilla del PET (interpolación lineal)
    SEG.nii.gz    máscara binaria de lesiones en la grilla del PET (desde el DICOM SEG)

Analogía: el CT y el PET son dos fotos del mismo paisaje tomadas con cámaras
de distinta resolución. Para superponerlas hay que "re-fotografiar" el CT con
la cámara del PET (CTres). La máscara SEG viene dibujada sobre la foto del PET.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import numpy as np
import SimpleITK as sitk

from .suv import suv_params_from_dataset


# ---------------------------------------------------------------- lectura de series
def read_dicom_series(folder: str | Path) -> sitk.Image:
    """Lee una carpeta con una serie DICOM y devuelve un volumen SimpleITK.

    SimpleITK ordena los cortes por posición y aplica RescaleSlope/Intercept,
    de modo que el CT sale en HU y el PET en las unidades declaradas (Bq/mL).
    """
    reader = sitk.ImageSeriesReader()
    ids = reader.GetGDCMSeriesIDs(str(folder))
    if not ids:
        raise FileNotFoundError(f"No hay series DICOM en {folder}")
    if len(ids) > 1:
        raise ValueError(f"{folder} contiene {len(ids)} series; se esperaba una")
    files = reader.GetGDCMSeriesFileNames(str(folder), ids[0])
    reader.SetFileNames(files)
    img = reader.Execute()
    if img.GetNumberOfComponentsPerPixel() != 1:
        raise ValueError("Se esperaba imagen escalar")
    return img


def _first_dicom_file(folder: str | Path) -> Path:
    for p in sorted(Path(folder).iterdir()):
        if p.is_file() and not p.name.startswith("."):
            return p
    raise FileNotFoundError(folder)


# ---------------------------------------------------------------- PET → SUV
def pet_to_suv(pet_img: sitk.Image, pet_folder: str | Path) -> sitk.Image:
    """Escala un PET (Bq/mL) a SUVbw usando las etiquetas de la primera lámina."""
    import pydicom

    ds = pydicom.dcmread(str(_first_dicom_file(pet_folder)), stop_before_pixels=True)
    params = suv_params_from_dataset(ds)
    arr = sitk.GetArrayFromImage(pet_img).astype(np.float32)
    suv = sitk.GetImageFromArray(arr * np.float32(params.scale_factor))
    suv.CopyInformation(pet_img)
    return suv


# ---------------------------------------------------------------- CT → grilla PET
def resample_to_reference(img: sitk.Image, ref: sitk.Image, interpolator=sitk.sitkLinear,
                          default_value: float = -1024.0) -> sitk.Image:
    """Remuestrea `img` sobre la grilla (origen, espaciado, dirección, tamaño) de `ref`."""
    return sitk.Resample(img, ref, sitk.Transform(), interpolator, default_value, img.GetPixelID())


# ---------------------------------------------------------------- DICOM SEG → máscara
def _frame_geometry(ds, fg):
    """Orientación (cosenos de columna y fila) y espaciado de un frame del SEG.
    Pueden venir por frame o compartidos por todos los frames."""
    shared = ds.SharedFunctionalGroupsSequence[0] if "SharedFunctionalGroupsSequence" in ds else None
    src = fg if "PlaneOrientationSequence" in fg else shared
    iop = [float(v) for v in src.PlaneOrientationSequence[0].ImageOrientationPatient]
    src = fg if "PixelMeasuresSequence" in fg else shared
    pm = src.PixelMeasuresSequence[0]
    row_sp, col_sp = (float(v) for v in pm.PixelSpacing)  # (entre filas, entre columnas)
    return np.array(iop[0:3]), np.array(iop[3:6]), row_sp, col_sp


def seg_to_mask(seg_file: str | Path, ref: sitk.Image) -> sitk.Image:
    """Convierte un objeto DICOM SEG (multiframe) en una máscara binaria sobre `ref`.

    Cada frame trae su posición (ImagePositionPatient, la esquina del primer píxel) y su
    orientación (ImageOrientationPatient). En autoPET los frames vienen con las filas
    recorridas en sentido contrario al PET (orientación 1,0,0,0,-1,0 frente a 1,0,0,0,1,0),
    así que no basta con apilarlos: hay que ubicar físicamente las dos esquinas de cada
    frame en la grilla de referencia y voltear filas o columnas cuando corresponda. Si se
    ignora, la máscara queda reflejada y cae fuera de las lesiones.
    """
    import pydicom

    ds = pydicom.dcmread(str(seg_file))
    frames = ds.pixel_array  # (n, rows, cols) uint8 0/1
    if frames.ndim == 2:
        frames = frames[None]
    rows, cols = int(ds.Rows), int(ds.Columns)
    size = ref.GetSize()  # (x, y, z)
    mask = np.zeros((size[2], size[1], size[0]), dtype=np.uint8)
    n_out = 0
    for k, fg in enumerate(ds.PerFrameFunctionalGroupsSequence):
        ipp = np.array([float(v) for v in fg.PlanePositionSequence[0].ImagePositionPatient])
        col_dir, row_dir, row_sp, col_sp = _frame_geometry(ds, fg)
        # esquinas físicas: primer píxel y último píxel del frame
        p_first = ipp
        p_last = ipp + row_dir * row_sp * (rows - 1) + col_dir * col_sp * (cols - 1)
        i_first = np.array(ref.TransformPhysicalPointToContinuousIndex([float(v) for v in p_first]))
        i_last = np.array(ref.TransformPhysicalPointToContinuousIndex([float(v) for v in p_last]))
        z = int(round(i_first[2]))
        if not (0 <= z < size[2]):
            n_out += 1
            continue
        frame = frames[k].astype(np.uint8)
        # si el último píxel queda "antes" que el primero en un eje, el frame va reflejado
        if i_last[1] < i_first[1]:
            frame = frame[::-1, :]
        if i_last[0] < i_first[0]:
            frame = frame[:, ::-1]
        y0 = int(round(min(i_first[1], i_last[1])))
        x0 = int(round(min(i_first[0], i_last[0])))
        if (y0, x0) != (0, 0) or (rows, cols) != (size[1], size[0]):
            # frame desplazado o de otro tamaño: se pega donde corresponde, recortando bordes
            ys = slice(max(y0, 0), min(y0 + rows, size[1]))
            xs = slice(max(x0, 0), min(x0 + cols, size[0]))
            fy = slice(ys.start - y0, ys.stop - y0)
            fx = slice(xs.start - x0, xs.stop - x0)
            mask[z, ys, xs] |= frame[fy, fx]
        else:
            mask[z] |= frame
    if n_out:
        print(f"[seg_to_mask] aviso: {n_out} frames fuera de la grilla de referencia")
    out = sitk.GetImageFromArray(mask)
    out.CopyInformation(ref)
    return out


# ---------------------------------------------------------------- estudio completo
def find_series_folders(study_dir: str | Path) -> Dict[str, Path]:
    """Clasifica las subcarpetas de un estudio por modalidad (CT, PT, SEG) leyendo un archivo de cada una."""
    import pydicom

    found: Dict[str, Path] = {}
    for sub in sorted(Path(study_dir).iterdir()):
        if not sub.is_dir():
            continue
        try:
            ds = pydicom.dcmread(str(_first_dicom_file(sub)), stop_before_pixels=True)
        except Exception:
            continue
        mod = str(getattr(ds, "Modality", "")).upper()
        if mod in ("CT", "PT", "SEG") and mod not in found:
            found[mod] = sub
    return found


def convert_study(study_dir: str | Path, out_dir: str | Path, with_seg: bool = True) -> Dict[str, Path]:
    """Convierte un estudio completo y escribe los cinco NIfTI en `out_dir`."""
    study_dir, out_dir = Path(study_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    series = find_series_folders(study_dir)
    if "CT" not in series or "PT" not in series:
        raise FileNotFoundError(f"Faltan series CT/PT en {study_dir}: {list(series)}")

    ct = read_dicom_series(series["CT"])
    pet = read_dicom_series(series["PT"])
    suv = pet_to_suv(pet, series["PT"])
    ctres = resample_to_reference(sitk.Cast(ct, sitk.sitkFloat32), pet, sitk.sitkLinear, -1024.0)

    written: Dict[str, Path] = {}
    for name, img in (("CT", ct), ("PET", pet), ("SUV", suv), ("CTres", ctres)):
        p = out_dir / f"{name}.nii.gz"
        sitk.WriteImage(img, str(p), useCompression=True)
        written[name] = p

    if with_seg:
        if "SEG" in series:
            seg_file = _first_dicom_file(series["SEG"])
            mask = seg_to_mask(seg_file, pet)
        else:  # controles negativos: máscara vacía
            mask = sitk.Image(pet.GetSize(), sitk.sitkUInt8)
            mask.CopyInformation(pet)
        p = out_dir / "SEG.nii.gz"
        sitk.WriteImage(mask, str(p), useCompression=True)
        written["SEG"] = p
    return written
