#!/usr/bin/env python
"""Paso 5a. Máscaras de órganos con TotalSegmentator, llevadas a la grilla de los `.npz`.

Uso (en el Mac, con TotalSegmentator instalado en el .venv: `pip install TotalSegmentator`):
    python scripts/11_organos_totalsegmentator.py --particion val
    python scripts/11_organos_totalsegmentator.py --particion test
    python scripts/11_organos_totalsegmentator.py --particion val --solo-agrupar   # si ya corrió TS

Para cada estudio de la partición:
  1. corre TotalSegmentator sobre el CT original (`data/interim/nifti/<pid>/<uid>/CT.nii.gz`)
     con `--fast` (modelo de 3 mm, suficiente para nuestra grilla) y `--ml` (un solo archivo
     multietiqueta); deja `data/interim/organos/<pid>__<uid>.nii.gz`. Reanudable.
  2. agrupa las 117 etiquetas en los grupos del proyecto (`petct.organs.GROUPS`), lo lleva a
     la grilla del `.npz` (remuestreo sobre la SUV, 3 mm, mismo recorte) y guarda
     `data/processed_organos/<pid>__<uid>.npz` con `groups` (uint8) y `ts` (etiquetas crudas).

La primera vez TotalSegmentator descarga sus pesos (~1 GB). En `mps` tarda del orden de un
minuto por CT con `--fast`; en CPU, varios. Se corre solo sobre validación y prueba (75
estudios), que es donde se analizan los errores; no hace falta para entrenar.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import SimpleITK as sitk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.organs import GROUP_NAMES, group_labels, organs_to_grid  # noqa: E402


def dispositivo_ts() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "gpu"
        if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


def correr_ts(ct: Path, salida: Path, device: str, fast: bool = True) -> None:
    salida.parent.mkdir(parents=True, exist_ok=True)
    tmp = salida.with_suffix(".tmp.nii.gz")
    cmd = ["TotalSegmentator", "-i", str(ct), "-o", str(tmp), "--ml", "-ta", "total", "--device", device]
    if fast:
        cmd.append("--fast")
    subprocess.run(cmd, check=True)
    tmp.replace(salida)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--particion", default="val", choices=["train", "val", "test", "todas"])
    ap.add_argument("--manifest", default="data/manifests/subconjunto.csv")
    ap.add_argument("--nifti", default="data/interim/nifti")
    ap.add_argument("--procesado", default="data/processed")
    ap.add_argument("--salida-ts", default="data/interim/organos")
    ap.add_argument("--salida", default="data/processed_organos")
    ap.add_argument("--device", default=None, help="gpu | mps | cpu (por defecto el mejor disponible)")
    ap.add_argument("--sin-fast", action="store_true", help="modelo de 1,5 mm (mucho más lento)")
    ap.add_argument("--solo-agrupar", action="store_true", help="no correr TotalSegmentator; solo agrupar lo ya hecho")
    ap.add_argument("--limite", type=int, default=0)
    a = ap.parse_args()

    if shutil.which("TotalSegmentator") is None and not a.solo_agrupar:
        sys.exit("TotalSegmentator no está instalado en este entorno: pip install TotalSegmentator")
    from totalsegmentator.map_to_binary import class_map
    cmap = {int(k): v for k, v in class_map["total"].items()}

    sub = pd.read_csv(a.manifest)
    if a.particion != "todas":
        sub = sub[sub.split == a.particion]
    if a.limite:
        sub = sub.head(a.limite)
    device = a.device or dispositivo_ts()
    print(f"{len(sub)} estudios de '{a.particion}'; TotalSegmentator en {device}", flush=True)

    Path(a.salida).mkdir(parents=True, exist_ok=True)
    filas = []
    for i, r in enumerate(sub.itertuples(), 1):
        base = f"{r.patient_id}__{r.study_uid}"
        ts_file = Path(a.salida_ts) / f"{base}.nii.gz"
        out = Path(a.salida) / f"{base}.npz"
        est = Path(a.nifti) / str(r.patient_id) / str(r.study_uid)
        if out.exists():
            filas.append({"patient_id": r.patient_id, "study_uid": r.study_uid, "estado": "ya"}); continue
        try:
            if not ts_file.exists():
                if a.solo_agrupar:
                    filas.append({"patient_id": r.patient_id, "study_uid": r.study_uid, "estado": "falta TS"}); continue
                correr_ts(est / "CT.nii.gz", ts_file, device, fast=not a.sin_fast)
            npz = np.load(Path(a.procesado) / f"{base}.npz")
            ref = sitk.ReadImage(str(est / "SUV.nii.gz"))
            ts_img = sitk.ReadImage(str(ts_file))
            ts_grid = organs_to_grid(ts_img, ref, tuple(float(s) for s in npz["spacing"]), npz["bbox"])
            body = npz["body"].astype(bool)
            assert ts_grid.shape == body.shape, (ts_grid.shape, body.shape)
            groups = group_labels(ts_grid, cmap, body)
            tmp = out.with_suffix(".tmp.npz")
            np.savez_compressed(tmp, groups=groups, ts=ts_grid, group_names=np.array(GROUP_NAMES))
            tmp.replace(out)
            frac = {GROUP_NAMES[k]: round(float(v) / body.sum(), 3) for k, v in
                    zip(*np.unique(groups[body], return_counts=True)) if v / body.sum() > 0.05}
            print(f"[ok] {i}/{len(sub)} {r.patient_id} {groups.shape} fracción del cuerpo: {frac}", flush=True)
            filas.append({"patient_id": r.patient_id, "study_uid": r.study_uid, "estado": "ok"})
        except Exception as e:
            print(f"[error] {r.patient_id}: {e}", flush=True)
            filas.append({"patient_id": r.patient_id, "study_uid": r.study_uid, "estado": f"error: {e}"})
    df = pd.DataFrame(filas)
    tabla = Path("data/manifests/organos.csv")
    prev = pd.read_csv(tabla) if tabla.exists() else pd.DataFrame()
    pd.concat([prev, df]).drop_duplicates(["patient_id", "study_uid"], keep="last").to_csv(tabla, index=False)
    print(df.estado.value_counts().to_dict())


if __name__ == "__main__":
    main()
