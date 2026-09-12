#!/usr/bin/env python
"""Rama `extendido`, paso 1b. Traer los estudios nuevos por lotes, sin llenar el disco.

Por cada lote: descarga el DICOM, lo convierte a NIfTI, lo preprocesa a .npz, comprueba
que el .npz existe y recién entonces borra el DICOM y el NIfTI de ese lote. El pico de
disco queda en el tamaño de un lote (unos 15 GB con 20 estudios) en vez de los ~280 GB
que ocuparía bajarlo todo junto.

Es reanudable: al relanzarlo salta todo lo que ya tiene .npz. Se puede cortar con Ctrl-C
entre lotes sin perder nada.

NUNCA toca el DICOM ni el NIfTI de los 251 estudios originales.

Uso:
    python scripts/25_traer_por_lotes.py                    # todo lo que falte
    python scripts/25_traer_por_lotes.py --lote 10          # lotes más chicos
    python scripts/25_traer_por_lotes.py --conservar-nifti  # no borra el NIfTI
    python scripts/25_traer_por_lotes.py --max-lotes 2      # prueba corta
"""
import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]


def corre(cmd, etiqueta):
    print(f"\n  → {etiqueta}", flush=True)
    r = subprocess.run(cmd, cwd=RAIZ)
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="data/manifests/subconjunto_extendido.csv")
    ap.add_argument("--base", default="data/manifests/subconjunto.csv",
                    help="subconjunto original: sus archivos nunca se borran")
    ap.add_argument("--tcia-manifest", default="data/manifests/FDG-PET-CT-Lesions_defaced.tcia")
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--nifti", default="data/interim/nifti")
    ap.add_argument("--procesado", default="data/processed")
    ap.add_argument("--lote", type=int, default=20)
    ap.add_argument("--max-lotes", type=int, default=0, help="0 = sin límite")
    ap.add_argument("--conservar-nifti", action="store_true")
    ap.add_argument("--conservar-dicom", action="store_true")
    a = ap.parse_args()

    sub = pd.read_csv(RAIZ / a.manifest)
    protegidos = set(pd.read_csv(RAIZ / a.base).patient_id.astype(str))
    proc = RAIZ / a.procesado
    pend = [r for r in sub.itertuples()
            if not (proc / f"{r.patient_id}__{r.study_uid}.npz").exists()]
    print(f"manifiesto: {len(sub)} estudios · ya procesados: {len(sub) - len(pend)} · "
          f"pendientes: {len(pend)}")
    if not pend:
        print("no hay nada que traer.")
        return

    lotes = [pend[i:i + a.lote] for i in range(0, len(pend), a.lote)]
    if a.max_lotes:
        lotes = lotes[: a.max_lotes]
    print(f"{len(lotes)} lotes de hasta {a.lote} estudios\n")

    tmp_dir = RAIZ / "data/manifests/_lotes"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fallidos, t0 = [], time.time()

    for i, lote in enumerate(lotes, 1):
        ids = [r.patient_id for r in lote]
        print("=" * 70)
        print(f"LOTE {i}/{len(lotes)} · {len(lote)} estudios · "
              f"{(time.time() - t0) / 60:.0f} min transcurridos", flush=True)
        man = tmp_dir / f"lote_{i:03d}.csv"
        ser = tmp_dir / f"series_{i:03d}.csv"
        pd.DataFrame([r._asdict() for r in lote]).drop(columns=["Index"]).to_csv(man, index=False)

        ok = corre([sys.executable, "scripts/02_descargar_tcia.py", "--manifest", str(man),
                    "--tcia-manifest", a.tcia_manifest, "--descargar",
                    "--series-csv", str(ser),
                    "--salida-tcia", str(tmp_dir / f"lote_{i:03d}.tcia")], "descarga")
        if ok:
            ok = corre([sys.executable, "scripts/03_convertir_a_nifti.py", "--manifest", str(man),
                        "--series-csv", str(ser)], "conversión a NIfTI")
        if ok:
            ok = corre([sys.executable, "scripts/04_preprocesar.py"], "preprocesamiento")

        listos = [r for r in lote if (proc / f"{r.patient_id}__{r.study_uid}.npz").exists()]
        print(f"\n  lote {i}: {len(listos)}/{len(lote)} con .npz", flush=True)
        for r in lote:
            if r not in listos:
                fallidos.append(r.patient_id)

        # limpieza: solo de los pacientes de este lote que ya tienen su .npz,
        # y nunca de los 251 originales
        liberado = 0
        for r in listos:
            pid = str(r.patient_id)
            if pid in protegidos:
                continue
            for base, borrar in ((a.raw, not a.conservar_dicom), (a.nifti, not a.conservar_nifti)):
                d = RAIZ / base / pid
                if borrar and d.exists():
                    liberado += sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
                    shutil.rmtree(d, ignore_errors=True)
        if liberado:
            print(f"  liberados {liberado / 1e9:.1f} GB", flush=True)
        libre = shutil.disk_usage(RAIZ).free / 1e9
        print(f"  disco libre: {libre:.0f} GB", flush=True)
        if libre < 30:
            print("\n  MENOS DE 30 GB LIBRES: me detengo acá para no llenar el disco.")
            break

    n = len(list(proc.glob("*.npz")))
    print("\n" + "=" * 70)
    print(f"listo. {n} estudios procesados en total · {(time.time() - t0) / 60:.0f} min")
    if fallidos:
        print(f"{len(fallidos)} sin .npz (relanzá el script y lo reintenta): {fallidos[:10]}")


if __name__ == "__main__":
    main()
