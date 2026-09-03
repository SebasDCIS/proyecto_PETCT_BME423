#!/usr/bin/env python
"""Paso 1b — Descargar desde TCIA las series CT, PT y SEG del subconjunto.

Uso (en tu computador, con red):
    pip install tcia_utils
    python scripts/02_descargar_tcia.py --manifest data/manifests/subconjunto.csv --raw data/raw --limit 5

Descarga una carpeta por serie en data/raw/<SeriesInstanceUID>/ y guarda la tabla
de series en data/manifests/series_tcia.csv. Con --limit puedes probar con pocos
pacientes antes de lanzar la descarga completa (~400 MB por estudio).
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.tcia import download_series, fetch_series_table  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="data/manifests/subconjunto.csv")
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--limit", type=int, default=0, help="descargar solo los primeros N pacientes")
    ap.add_argument("--series-csv", default="data/manifests/series_tcia.csv")
    a = ap.parse_args()

    sub = pd.read_csv(a.manifest)
    pids = sub.patient_id.astype(str).tolist()
    if a.limit:
        pids = pids[: a.limit]
    print(f"Consultando NBIA por {len(pids)} pacientes…")
    series = fetch_series_table(pids)
    series.to_csv(a.series_csv, index=False)
    print(series.groupby("Modality").size().to_string())
    print("Descargando…")
    download_series(series, a.raw)
    print("Listo. Ahora: python scripts/03_convertir_a_nifti.py")


if __name__ == "__main__":
    main()
