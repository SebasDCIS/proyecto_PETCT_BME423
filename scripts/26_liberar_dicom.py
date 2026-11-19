#!/usr/bin/env python
"""Rama `extendido`. Borrar el DICOM de los estudios que ya están preprocesados.

`data/raw` guarda una carpeta por SERIE (nombrada con el SeriesInstanceUID), no por
paciente. Una vez que un estudio tiene su `.npz` —y su NIfTI, si se conservó— sus
series DICOM no hacen falta para nada: el preprocesamiento a cualquier resolución se
rehace desde el NIfTI.

Por defecto solo lista lo que borraría. Con --hacerlo borra de verdad.

Uso:
    python scripts/26_liberar_dicom.py              # simulacro, no borra nada
    python scripts/26_liberar_dicom.py --hacerlo
"""
import argparse
import shutil
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--nifti", default="data/interim/nifti")
    ap.add_argument("--procesado", default="data/processed")
    ap.add_argument("--hacerlo", action="store_true")
    a = ap.parse_args()

    raw = RAIZ / a.raw
    if not raw.exists():
        sys.exit(f"no existe {raw}")

    # pacientes que ya tienen .npz (y por tanto su NIfTI convertido)
    listos = {f.stem.split("__", 1)[0] for f in (RAIZ / a.procesado).glob("*.npz")}
    print(f"estudios con .npz: {len(listos)}")

    # mapa serie -> paciente, juntando todas las tablas de series que existan
    tablas = [RAIZ / "data/manifests/series_tcia.csv"]
    tablas += sorted((RAIZ / "data/manifests/_lotes").glob("series_*.csv"))
    mapa = {}
    for t in tablas:
        if t.exists():
            d = pd.read_csv(t)
            mapa.update(dict(zip(d.SeriesInstanceUID.astype(str), d.PatientID.astype(str))))
    print(f"series conocidas en las tablas: {len(mapa)}")

    carpetas = [d for d in raw.iterdir() if d.is_dir()]
    borrar, sin_mapa, en_uso = [], [], []
    for d in carpetas:
        pid = mapa.get(d.name)
        if pid is None:
            sin_mapa.append(d)
        elif pid in listos:
            borrar.append(d)
        else:
            en_uso.append(d)

    def peso(dirs):
        return sum(f.stat().st_size for d in dirs for f in d.rglob("*") if f.is_file())

    print(f"\ncarpetas de serie en {a.raw}: {len(carpetas)}")
    print(f"  de estudios ya preprocesados (BORRABLES) : {len(borrar)}")
    print(f"  de estudios aún sin .npz (se conservan)  : {len(en_uso)}")
    print(f"  sin paciente conocido (se conservan)     : {len(sin_mapa)}")
    if not borrar:
        print("\nnada que borrar.")
        return
    print("\nmidiendo... (puede tardar un minuto)", flush=True)
    gb = peso(borrar) / 1e9
    print(f"se liberarían {gb:.1f} GB")

    if not a.hacerlo:
        print("\nsimulacro: no se borró nada. Repetí con --hacerlo para borrarlo de verdad.")
        return
    for i, d in enumerate(borrar, 1):
        shutil.rmtree(d, ignore_errors=True)
        if i % 200 == 0:
            print(f"  {i}/{len(borrar)}", flush=True)
    libre = shutil.disk_usage(RAIZ).free / 1e9
    print(f"\nborradas {len(borrar)} carpetas. Disco libre ahora: {libre:.0f} GB")


if __name__ == "__main__":
    main()
