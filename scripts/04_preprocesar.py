#!/usr/bin/env python
"""Paso 2a. Preprocesar todos los estudios convertidos: 3 mm, ventana, recorte, .npz.

Uso:
    python scripts/04_preprocesar.py --nifti data/interim/nifti --out data/processed --config configs/default.yaml

Escribe data/processed/<paciente>__<estudio>.npz y una tabla resumen
data/manifests/procesados.csv (forma, vóxeles de lesión, mL de lesión).
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.preprocess import preprocess_study  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nifti", default="data/interim/nifti")
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--config", default="configs/default.yaml")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config))["preprocesamiento"]

    rows = []
    for suv_file in sorted(Path(a.nifti).glob("*/*/SUV.nii.gz")):
        study_dir = suv_file.parent
        pid, study = study_dir.parent.name, study_dir.name
        out = Path(a.out) / f"{pid}__{study}.npz"
        if out.exists():
            continue
        try:
            info = preprocess_study(study_dir, out, tuple(cfg["espaciado_mm"]),
                                    tuple(cfg["ventana_hu"]), cfg["suv_clip"][1])
            rows.append({"patient_id": pid, "study_uid": study, "shape": info["shape"],
                         "lesion_voxels": info["lesion_voxels"],
                         "lesion_ml": info["lesion_voxels"] * info["ml_per_voxel"], "error": ""})
            print(f"[ok] {pid} {info['shape']} lesión {rows[-1]['lesion_ml']:.1f} mL")
        except Exception as e:
            rows.append({"patient_id": pid, "study_uid": study, "error": str(e)})
            print(f"[error] {pid}: {e}")
    if rows:
        tabla = Path("data/manifests/procesados.csv")
        prev = pd.read_csv(tabla) if tabla.exists() else pd.DataFrame()
        pd.concat([prev, pd.DataFrame(rows)], ignore_index=True).to_csv(tabla, index=False)
        print(f"{len(rows)} estudios; tabla en {tabla}")


if __name__ == "__main__":
    main()
