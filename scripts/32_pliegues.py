#!/usr/bin/env python
"""Rama `extendido`, paso 4. Cinco pliegues del conjunto de entrenamiento para el ensamble.

Reparte los 825 estudios de entrenamiento en cinco grupos de ~165, estratificados por
diagnóstico (pulmón, linfoma, melanoma, control) con la semilla del proyecto (423). Cada
estudio es de un paciente distinto (lo verifica scripts/24), así que el reparto por estudio
es también por paciente. Validación (26) y prueba (49) no se tocan: siguen siendo las de
siempre, en todos los pliegues.

Escribe:
  data/manifests/pliegues_extendido.csv        el manifiesto extendido + columna `pliegue` (0–4; -1 en val/test)
  data/manifests/_pliegues/pliegue_<k>.csv     uno por pliegue: los estudios del pliegue k pasan de split
                                               "train" a "oof" (out-of-fold: lo que esa corrida no ve);
                                               el resto queda igual. Con eso 07_entrenar entrena con 4/5
                                               y 09_evaluar --particion oof mide sobre el quinto.

Uso:
    python scripts/32_pliegues.py
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

K = 5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="data/manifests/subconjunto_extendido.csv")
    ap.add_argument("--salida", default="data/manifests/pliegues_extendido.csv")
    ap.add_argument("--carpeta", default="data/manifests/_pliegues")
    ap.add_argument("--semilla", type=int, default=423)
    a = ap.parse_args()

    m = pd.read_csv(a.manifest)
    assert m.patient_id.is_unique, "hay pacientes repetidos: el reparto por estudio no sería por paciente"
    rng = np.random.default_rng(a.semilla)
    m["pliegue"] = -1
    tr = m.index[m.split == "train"]
    for dx, idx in m.loc[tr].groupby("diagnosis").groups.items():
        idx = np.array(list(idx)); rng.shuffle(idx)
        for k, chunk in enumerate(np.array_split(idx, K)):
            m.loc[chunk, "pliegue"] = k
    assert (m.loc[tr, "pliegue"] >= 0).all()
    m.to_csv(a.salida, index=False)

    Path(a.carpeta).mkdir(parents=True, exist_ok=True)
    for k in range(K):
        mk = m.drop(columns="pliegue").copy()
        mk.loc[m.pliegue == k, "split"] = "oof"
        mk.to_csv(Path(a.carpeta) / f"pliegue_{k}.csv", index=False)

    tabla = m[m.split == "train"].groupby(["pliegue", "diagnosis"]).size().unstack(fill_value=0)
    tabla["total"] = tabla.sum(1)
    print(tabla.to_string())
    print(f"\nval {int((m.split == 'val').sum())}, test {int((m.split == 'test').sum())}: intactos")
    print(f"escrito {a.salida} y {K} manifiestos en {a.carpeta}/")


if __name__ == "__main__":
    main()
