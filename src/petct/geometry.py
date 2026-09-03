"""Geometría de una serie DICOM: posiciones de corte, espaciado y medidas.

Es el tema del Laboratorio 1 ("construya el volumen ordenando por
ImagePositionPatient, determine el espaciado efectivo, compárelo con SliceThickness,
corrija la relación de aspecto") aplicado a los datos del proyecto. Todo sale del
módulo "Image Plane" del estándar (Parte 3, C.7.6.2):

  ImagePositionPatient   (x, y, z) en mm del CENTRO del primer píxel (fila 0, columna 0)
                         de cada corte, en el sistema del paciente (LPS: +x izquierda,
                         +y posterior, +z cabeza).
  ImageOrientationPatient seis cosenos: dirección de las columnas (hacia dónde avanza
                         x del píxel) y dirección de las filas (hacia dónde avanza y).
  PixelSpacing           (entre filas, entre columnas) en mm. Ojo con el orden.
  SliceThickness         grosor nominal del corte reconstruido. NO es la distancia
                         entre cortes; puede haber solapamiento o hueco.
  SpacingBetweenSlices   distancia declarada entre cortes (opcional; a veces falta).

La distancia real entre cortes se mide: se proyecta cada ImagePositionPatient sobre
la normal al plano (producto cruz de los dos cosenos) y se ordenan; las diferencias
consecutivas son el espaciado efectivo. Si son todas iguales, el muestreo es uniforme.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np


def _read_headers(folder: str | Path) -> List:
    import pydicom

    out = []
    for p in sorted(Path(folder).iterdir()):
        if p.is_file() and not p.name.startswith("."):
            try:
                out.append((p.name, pydicom.dcmread(str(p), stop_before_pixels=True)))
            except Exception:
                pass
    if not out:
        raise FileNotFoundError(folder)
    return out


def series_geometry(folder: str | Path) -> Dict[str, object]:
    """Resume la geometría de una serie de cortes 2D (CT o PT). No sirve para SEG."""
    hdrs = _read_headers(folder)
    ds0 = hdrs[0][1]
    iop = np.array([float(v) for v in ds0.ImageOrientationPatient])
    col_dir, row_dir = iop[:3], iop[3:]
    normal = np.cross(col_dir, row_dir)            # normal al plano de corte
    row_sp, col_sp = (float(v) for v in ds0.PixelSpacing)

    names, ipps, inst = [], [], []
    for name, ds in hdrs:
        names.append(name)
        ipps.append([float(v) for v in ds.ImagePositionPatient])
        inst.append(int(getattr(ds, "InstanceNumber", 0)))
    ipps = np.array(ipps)
    proj = ipps @ normal                            # coordenada a lo largo de la normal
    order = np.argsort(proj)                        # orden anatómico real
    proj_sorted = proj[order]
    gaps = np.diff(proj_sorted)

    by_name = np.arange(len(names))                 # orden alfabético (ya vienen sorted)
    by_instance = np.argsort(inst)
    thickness = float(getattr(ds0, "SliceThickness", np.nan) or np.nan)
    sbs = getattr(ds0, "SpacingBetweenSlices", None)
    sbs = float(sbs) if sbs not in (None, "") else np.nan

    return {
        "modality": str(ds0.Modality),
        "patient_position": str(getattr(ds0, "PatientPosition", "")),
        "n_slices": len(names),
        "rows": int(ds0.Rows), "cols": int(ds0.Columns),
        "row_spacing_mm": row_sp, "col_spacing_mm": col_sp,
        "fov_rows_mm": row_sp * int(ds0.Rows), "fov_cols_mm": col_sp * int(ds0.Columns),
        "iop": iop.round(4).tolist(), "normal": normal.round(4).tolist(),
        "slice_thickness_mm": thickness, "spacing_between_slices_mm": sbs,
        "gap_mean_mm": float(gaps.mean()) if gaps.size else np.nan,
        "gap_min_mm": float(gaps.min()) if gaps.size else np.nan,
        "gap_max_mm": float(gaps.max()) if gaps.size else np.nan,
        "gap_std_mm": float(gaps.std()) if gaps.size else np.nan,
        "uniform": bool(gaps.size and np.allclose(gaps, gaps[0], atol=0.01)),
        "z_first_mm": float(proj_sorted[0]), "z_last_mm": float(proj_sorted[-1]),
        "extent_mm": float(proj_sorted[-1] - proj_sorted[0]) + (thickness if np.isfinite(thickness) else 0.0),
        "order_by_name_ok": bool(np.array_equal(order, by_name)),
        "order_by_instance_ok": bool(np.array_equal(order, by_instance) or np.array_equal(order, by_instance[::-1])),
        "origin_first_slice": ipps[order[0]].round(3).tolist(),
        "aspect_coronal": (float(gaps.mean()) / row_sp) if gaps.size else np.nan,
        "positions_sorted_mm": proj_sorted.round(3).tolist(),
    }


def index_to_mm(i: int, j: int, k: int, origin, row_sp: float, col_sp: float,
                col_dir, row_dir, normal, slice_sp: float) -> np.ndarray:
    """Ecuación del módulo Image Plane: de índices (fila i, columna j, corte k) a mm.

        P = origen + j * col_sp * col_dir + i * row_sp * row_dir + k * slice_sp * normal

    Es la misma matriz afín que guardan NIfTI y SimpleITK (origen, espaciado, dirección).
    """
    return (np.asarray(origin, float) + j * col_sp * np.asarray(col_dir)
            + i * row_sp * np.asarray(row_dir) + k * slice_sp * np.asarray(normal))


def measurement_error_if_aspect_ignored(true_len_mm: float, angle_deg: float,
                                        in_plane_mm: float, slice_mm: float) -> float:
    """Error al medir un segmento oblicuo en un corte coronal/sagital dibujado como si
    los vóxeles fueran cuadrados. El segmento tiene componentes (h horizontal, v
    vertical) en mm; en píxeles cuadrados la componente vertical se acorta o alarga por
    el factor in_plane/slice. Devuelve el error relativo (fracción)."""
    a = np.deg2rad(angle_deg)
    h, v = true_len_mm * np.cos(a), true_len_mm * np.sin(a)
    v_px_as_mm = v * (in_plane_mm / slice_mm)   # lo que "mide" si se ignora el aspecto
    apparent = np.hypot(h, v_px_as_mm)
    return float(apparent / true_len_mm - 1.0)
