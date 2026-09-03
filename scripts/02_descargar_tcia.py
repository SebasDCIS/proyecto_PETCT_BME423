#!/usr/bin/env python
"""Paso 1b. Obtener las series CT, PT y SEG del subconjunto desde TCIA.

Hay dos formas de saber qué series bajar:

  A) con el manifiesto oficial de la versión "defaced" (acceso abierto), que se
     descarga desde la página de la colección. Es la forma recomendada, porque
     garantiza que las series son las de libre acceso:
        python scripts/02_descargar_tcia.py --tcia-manifest data/manifests/FDG-PET-CT-Lesions_defaced.tcia --limit 3

  B) consultando la API por paciente (sin manifiesto):
        python scripts/02_descargar_tcia.py --limit 3

En ambos casos el script escribe data/manifests/series_tcia.csv (qué series son de
quién) y data/manifests/subconjunto.tcia (manifiesto reducido, por si prefieres bajar
con el NBIA Data Retriever). Con --descargar baja las series a data/raw con tcia_utils;
sin esa opción solo prepara los manifiestos. --limit N restringe a los primeros N
pacientes del subconjunto para probar.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.tcia import (download_series, fetch_series_table, series_from_manifest,  # noqa: E402
                        write_tcia_manifest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="data/manifests/subconjunto.csv", help="salida del script 01")
    ap.add_argument("--tcia-manifest", default="", help="manifiesto .tcia oficial (versión defaced)")
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--limit", type=int, default=0, help="solo los primeros N pacientes")
    ap.add_argument("--descargar", action="store_true", help="bajar las series con tcia_utils")
    ap.add_argument("--series-csv", default="data/manifests/series_tcia.csv")
    ap.add_argument("--salida-tcia", default="data/manifests/subconjunto.tcia")
    a = ap.parse_args()

    sub = pd.read_csv(a.manifest)
    pids = sub.patient_id.astype(str).tolist()
    if a.limit:
        pids = pids[: a.limit]
    print(f"{len(pids)} pacientes del subconjunto")

    if a.tcia_manifest:
        print(f"Cruzando con el manifiesto oficial {a.tcia_manifest} (consulta a NBIA por bloques)…")
        series = series_from_manifest(a.tcia_manifest, pids)
    else:
        print("Consultando NBIA por paciente…")
        series = fetch_series_table(pids)

    series.to_csv(a.series_csv, index=False)
    print(series.groupby("Modality").size().to_string())
    faltan = set(pids) - set(series.PatientID)
    if faltan:
        print(f"Aviso: {len(faltan)} pacientes sin series: {sorted(faltan)[:10]}…")
    write_tcia_manifest(series.SeriesInstanceUID.tolist(), a.salida_tcia)
    print(f"Manifiesto reducido: {a.salida_tcia} ({len(series)} series)")

    if a.descargar:
        print("Descargando con tcia_utils…")
        download_series(series, a.raw)
        print("Listo. Ahora: python scripts/03_convertir_a_nifti.py")
    else:
        print("No se descargó nada (usa --descargar, o abre el .tcia con NBIA Data Retriever).")


if __name__ == "__main__":
    main()
