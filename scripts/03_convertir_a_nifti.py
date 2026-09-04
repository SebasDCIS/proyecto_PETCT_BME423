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
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.convert import convert_study  # noqa: E402


def _convertir_uno(args):
    """Convierte un estudio; corre en un proceso hijo."""
    pid, study_uid, filas, raw, out = args
    out_dir = Path(out) / str(pid) / str(study_uid)
    with tempfile.TemporaryDirectory() as tmp:
        for mod, uid in filas:
            src = Path(raw) / str(uid)
            if src.exists():
                os.symlink(src.resolve(), Path(tmp) / f"{mod}_{uid}")
        try:
            convert_study(tmp, out_dir)
            return pid, study_uid, ""
        except Exception as e:  # se informa y se sigue con el resto
            return pid, study_uid, str(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--series-csv", default="data/manifests/series_tcia.csv")
    ap.add_argument("--out", default="data/interim/nifti")
    ap.add_argument("--manifest", default="data/manifests/subconjunto.csv",
                    help="solo convierte los estudios elegidos (uno por paciente); '' para convertir todo")
    ap.add_argument("--workers", type=int, default=3, help="procesos en paralelo")
    a = ap.parse_args()

    series = pd.read_csv(a.series_csv)
    if a.manifest:
        # el cruce con el manifiesto trae TODOS los estudios de cada paciente (hay
        # pacientes con hasta 5); el proyecto usa uno por paciente, el del sorteo
        elegidos = set(pd.read_csv(a.manifest).study_uid.astype(str))
        series = series[series.StudyInstanceUID.astype(str).isin(elegidos)]
        print(f"{series.StudyInstanceUID.nunique()} estudios del subconjunto")
    raw = Path(a.raw)
    pendientes = []
    ya = 0
    for (pid, study_uid), grp in series.groupby(["PatientID", "StudyInstanceUID"]):
        out_dir = Path(a.out) / str(pid) / str(study_uid)
        if (out_dir / "SUV.nii.gz").exists() and (out_dir / "SEG.nii.gz").exists():
            ya += 1
            continue
        filas = [(r["Modality"], r["SeriesInstanceUID"]) for _, r in grp.iterrows()]
        pendientes.append((pid, study_uid, filas, str(raw), a.out))
    print(f"ya convertidos: {ya} | pendientes: {len(pendientes)} | workers: {a.workers}", flush=True)

    ok, bad = 0, []
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for fut in as_completed([ex.submit(_convertir_uno, t) for t in pendientes]):
            pid, study_uid, err = fut.result()
            if err:
                bad.append((pid, study_uid, err))
                print(f"[error] {pid}: {err}", flush=True)
            else:
                ok += 1
                print(f"[ok] {pid} ({ya + ok}/{ya + len(pendientes)})", flush=True)
    print(f"\nConvertidos ahora: {ok}   con error: {len(bad)}   total listos: {ya + ok}")
    if bad:
        pd.DataFrame(bad, columns=["patient_id", "study_uid", "error"]).to_csv(
            Path(a.out) / "errores_conversion.csv", index=False)


if __name__ == "__main__":
    main()
