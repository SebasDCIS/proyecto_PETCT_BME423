#!/usr/bin/env python
"""Geometría de las series descargadas (PET y CT): posiciones, espaciado, medidas.

Uso:
    python scripts/06_geometria_series.py --raw data/raw --series-csv data/manifests/series_tcia.csv

Escribe results/geometria_series.csv (una fila por serie) y muestra un resumen. Es la
actividad del Laboratorio 1 ("ordene por ImagePositionPatient, mida el espaciado
efectivo y compárelo con SliceThickness") aplicada a los datos del proyecto.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.geometry import series_geometry  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--series-csv", default="data/manifests/series_tcia.csv")
    ap.add_argument("--out", default="results/geometria_series.csv")
    a = ap.parse_args()
    series = pd.read_csv(a.series_csv)
    manifest = Path("data/manifests/subconjunto.csv")
    if manifest.exists():  # solo el estudio elegido de cada paciente
        elegidos = set(pd.read_csv(manifest).study_uid.astype(str))
        series = series[series.StudyInstanceUID.astype(str).isin(elegidos)]
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    prev = pd.read_csv(out) if out.exists() else pd.DataFrame(columns=["series_uid"])
    if "series_uid" not in prev.columns:      # tabla de una versión anterior: se rehace
        prev = pd.DataFrame(columns=["series_uid"])
    hechas = set(prev["series_uid"].astype(str)) if len(prev) else set()
    rows = []
    pend = series[series.Modality.isin(["CT", "PT"]) & ~series.SeriesInstanceUID.astype(str).isin(hechas)]
    print(f"ya medidas: {len(hechas)} | pendientes: {len(pend)}", flush=True)
    for k, (_, r) in enumerate(pend.iterrows(), 1):
        folder = Path(a.raw) / str(r.SeriesInstanceUID)
        if not folder.exists():
            continue
        g = series_geometry(folder)
        g.pop("positions_sorted_mm")
        g["patient_id"] = r.PatientID
        g["series_uid"] = str(r.SeriesInstanceUID)
        rows.append(g)
        if k % 10 == 0:
            pd.concat([prev, pd.DataFrame(rows)], ignore_index=True).to_csv(out, index=False)
            print(f"  {k}/{len(pend)}", flush=True)
    df = pd.concat([prev, pd.DataFrame(rows)], ignore_index=True)
    df.to_csv(out, index=False)
    cols = ["patient_id", "modality", "n_slices", "rows", "row_spacing_mm", "slice_thickness_mm",
            "spacing_between_slices_mm", "gap_mean_mm", "gap_min_mm", "gap_max_mm", "uniform",
            "extent_mm", "order_by_name_ok", "order_by_instance_ok", "aspect_coronal"]
    print(df[cols].round(3).tail(12).to_string(index=False))
    print(f"\nseries medidas: {len(df)}")


if __name__ == "__main__":
    main()
