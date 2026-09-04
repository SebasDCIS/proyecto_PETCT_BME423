#!/usr/bin/env python
"""Paso 2a. Preprocesar todos los estudios convertidos: 3 mm, ventana, recorte, .npz.

Uso:
    python scripts/04_preprocesar.py --nifti data/interim/nifti --out data/processed --config configs/default.yaml

Escribe data/processed/<paciente>__<estudio>.npz y una tabla resumen
data/manifests/procesados.csv (forma, vóxeles de lesión, mL de lesión).
"""
import argparse
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.preprocess import preprocess_study  # noqa: E402


def _uno(args):
    study_dir, out, cfg = args
    pid, study = study_dir.parent.name, study_dir.name
    try:
        info = preprocess_study(study_dir, out, tuple(cfg["espaciado_mm"]),
                                tuple(cfg["ventana_hu"]), cfg["suv_clip"][1])
        return {"patient_id": pid, "study_uid": study, "shape": str(info["shape"]),
                "lesion_voxels": info["lesion_voxels"],
                "lesion_ml": info["lesion_voxels"] * info["ml_per_voxel"], "error": ""}
    except Exception as e:
        return {"patient_id": pid, "study_uid": study, "error": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nifti", default="data/interim/nifti")
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--config", default="configs/default.yaml")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config))["preprocesamiento"]

    ap_workers = 3
    tareas = []
    for suv_file in sorted(Path(a.nifti).glob("*/*/SUV.nii.gz")):
        study_dir = suv_file.parent
        if study_dir.name.endswith(".tmp"):
            continue
        out = Path(a.out) / f"{study_dir.parent.name}__{study_dir.name}.npz"
        if not out.exists():
            tareas.append((study_dir, out, cfg))
    print(f"pendientes: {len(tareas)}", flush=True)
    rows = []
    with ProcessPoolExecutor(max_workers=ap_workers) as ex:
        for fut in as_completed([ex.submit(_uno, t) for t in tareas]):
            r = fut.result(); rows.append(r)
            print(("[error] " if r["error"] else "[ok] ") + r["patient_id"] + (f" {r['shape']} lesión {r['lesion_ml']:.1f} mL" if not r["error"] else " " + r["error"]), flush=True)
    if rows:
        tabla = Path("data/manifests/procesados.csv")
        prev = pd.read_csv(tabla) if tabla.exists() else pd.DataFrame()
        df = pd.concat([prev, pd.DataFrame(rows)], ignore_index=True).drop_duplicates(["patient_id", "study_uid"], keep="last")
        df.to_csv(tabla, index=False)
        print(f"{len(rows)} estudios procesados ahora; tabla en {tabla} ({len(df)} filas)")


if __name__ == "__main__":
    main()
