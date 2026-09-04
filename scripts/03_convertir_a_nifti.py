#!/usr/bin/env python
"""Paso 1c. Convertir cada estudio DICOM (CT + PT + SEG) a NIfTI con SUV y CTres.

Uso:
    python scripts/03_convertir_a_nifti.py --raw data/raw --series-csv data/manifests/series_tcia.csv --out data/interim/nifti

Agrupa las series por StudyInstanceUID (usando la tabla de series de TCIA),
arma una carpeta temporal por estudio con enlaces a las carpetas CT/PT/SEG y
llama a petct.convert.convert_study.
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.convert import convert_study  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--series-csv", default="data/manifests/series_tcia.csv")
    ap.add_argument("--out", default="data/interim/nifti")
    ap.add_argument("--manifest", default="data/manifests/subconjunto.csv",
                    help="solo convierte los estudios elegidos (uno por paciente); '' para convertir todo")
    a = ap.parse_args()

    series = pd.read_csv(a.series_csv)
    if a.manifest:
        # el cruce con el manifiesto trae TODOS los estudios de cada paciente (hay
        # pacientes con hasta 5); el proyecto usa uno por paciente, el del sorteo
        elegidos = set(pd.read_csv(a.manifest).study_uid.astype(str))
        series = series[series.StudyInstanceUID.astype(str).isin(elegidos)]
        print(f"{series.StudyInstanceUID.nunique()} estudios del subconjunto")
    raw = Path(a.raw)
    ok, bad = 0, []
    for (pid, study_uid), grp in series.groupby(["PatientID", "StudyInstanceUID"]):
        out_dir = Path(a.out) / str(pid) / str(study_uid)
        if (out_dir / "SUV.nii.gz").exists() and (out_dir / "SEG.nii.gz").exists():
            ok += 1
            continue
        with tempfile.TemporaryDirectory() as tmp:
            for _, row in grp.iterrows():
                src = raw / str(row["SeriesInstanceUID"])
                if src.exists():
                    os.symlink(src.resolve(), Path(tmp) / f"{row['Modality']}_{row['SeriesInstanceUID']}")
            try:
                convert_study(tmp, out_dir)
                ok += 1
                print(f"[ok] {pid} / {study_uid[-8:]}")
            except Exception as e:  # seguir con el resto y reportar al final
                bad.append((pid, study_uid, str(e)))
                print(f"[error] {pid}: {e}")
    print(f"\nConvertidos: {ok}   con error: {len(bad)}")
    if bad:
        pd.DataFrame(bad, columns=["patient_id", "study_uid", "error"]).to_csv(
            Path(a.out) / "errores_conversion.csv", index=False)


if __name__ == "__main__":
    main()
