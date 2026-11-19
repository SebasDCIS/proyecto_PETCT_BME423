#!/usr/bin/env python
"""Rama `extendido`, paso 1. Añadir estudios NUEVOS al conjunto de entrenamiento.

La única regla que importa acá: **la partición original no se toca**. Los 49 estudios de
prueba y los 26 de validación siguen siendo exactamente los mismos, con el mismo paciente
en el mismo grupo. Los estudios nuevos entran todos a `train`, y ninguno de sus pacientes
aparece ya en el subconjunto (un estudio por paciente, como en el sorteo original).

El script verifica esas condiciones antes de escribir nada y aborta si alguna falla.

Uso:
    python scripts/24_ampliar_entrenamiento.py                     # todos los disponibles
    python scripts/24_ampliar_entrenamiento.py --max-negativos 200 # limitar los controles
    python scripts/24_ampliar_entrenamiento.py --n-nuevos 200      # solo 200, estratificados
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.tcia import load_clinical  # noqa: E402

DIAG_POS = ["LUNG_CANCER", "LYMPHOMA", "MELANOMA"]
DIAG_NEG = "NEGATIVE"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clinico", default="data/manifests/clinical_tcia.csv")
    ap.add_argument("--base", default="data/manifests/subconjunto.csv")
    ap.add_argument("--salida", default="data/manifests/subconjunto_extendido.csv")
    ap.add_argument("--n-nuevos", type=int, default=0, help="0 = todos los disponibles")
    ap.add_argument("--max-negativos", type=int, default=0, help="0 = sin tope")
    ap.add_argument("--semilla", type=int, default=423)
    a = ap.parse_args()

    base = pd.read_csv(a.base)
    usados = set(base.patient_id.astype(str))
    print(f"subconjunto actual: {len(base)} estudios, {len(usados)} pacientes")
    print(base.groupby(["split", "diagnosis"]).size().unstack(fill_value=0).to_string(), "\n")

    clin = load_clinical(a.clinico)
    # un estudio por paciente, igual que en el sorteo original, para no meter fugas
    uno = (clin.sort_values(["patient_id", "study_uid"])
               .drop_duplicates("patient_id", keep="first"))
    libres = uno[~uno.patient_id.astype(str).isin(usados)].copy()
    print(f"pacientes de la colección sin usar: {len(libres)}")
    print(libres.diagnosis.value_counts().to_string(), "\n")

    rng = np.random.default_rng(a.semilla)
    elegidos = []
    if a.n_nuevos > 0:
        # reparto proporcional a lo disponible, para no deformar la composición
        cupo = {d: int(round(a.n_nuevos * (libres.diagnosis == d).sum() / len(libres)))
                for d in DIAG_POS + [DIAG_NEG]}
    else:
        cupo = {d: int((libres.diagnosis == d).sum()) for d in DIAG_POS + [DIAG_NEG]}
    if a.max_negativos > 0:
        cupo[DIAG_NEG] = min(cupo[DIAG_NEG], a.max_negativos)
    for d, k in cupo.items():
        pool = libres[libres.diagnosis == d]
        k = min(k, len(pool))
        if k:
            elegidos.append(pool.iloc[rng.permutation(len(pool))[:k]])
    nuevos = pd.concat(elegidos, ignore_index=True)
    nuevos["split"] = "train"          # TODOS a entrenamiento, sin excepción
    nuevos["seed"] = a.semilla
    nuevos = nuevos[base.columns]

    ext = pd.concat([base, nuevos], ignore_index=True)

    # ------------------------------------------------------------------ verificaciones
    fallos = []
    for grupo in ("val", "test"):
        antes = set(zip(base[base.split == grupo].patient_id, base[base.split == grupo].study_uid))
        ahora = set(zip(ext[ext.split == grupo].patient_id, ext[ext.split == grupo].study_uid))
        if antes != ahora:
            fallos.append(f"el grupo '{grupo}' cambió: {len(antes)} -> {len(ahora)}")
    antes_tr = set(base[base.split == "train"].patient_id)
    if not antes_tr.issubset(set(ext[ext.split == "train"].patient_id)):
        fallos.append("algún estudio de entrenamiento original desapareció")
    if ext.patient_id.duplicated().any():
        fallos.append("hay pacientes repetidos: habría fuga entre particiones")
    cruce = set(ext[ext.split == "train"].patient_id) & (
        set(ext[ext.split == "val"].patient_id) | set(ext[ext.split == "test"].patient_id))
    if cruce:
        fallos.append(f"{len(cruce)} pacientes en entrenamiento y además en val/test")
    if fallos:
        print("NO se escribió nada. Fallaron las verificaciones:")
        for f in fallos:
            print("  -", f)
        sys.exit(1)

    Path(a.salida).parent.mkdir(parents=True, exist_ok=True)
    ext.to_csv(a.salida, index=False)
    print(f"+{len(nuevos)} estudios nuevos, todos a entrenamiento\n")
    print(ext.groupby(["split", "diagnosis"]).size().unstack(fill_value=0).to_string())
    print(f"\ntotal: {len(ext)} estudios ({ext.split.value_counts().to_dict()})")
    print("verificado: val y test intactos, un estudio por paciente, sin cruces")
    print("manifiesto en", a.salida)


if __name__ == "__main__":
    main()
