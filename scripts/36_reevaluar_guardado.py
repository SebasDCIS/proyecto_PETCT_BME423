#!/usr/bin/env python
"""Rama `extendido`, paso 5. Medir desde máscaras o probabilidades ya guardadas, sin volver a
correr ninguna red.

Sirve para dos cosas del test: la métrica cruda del reto (sin excluir la zona borrada) a partir
de las máscaras que dejó scripts/09, y el umbral secundario declarado (0,7) a partir de las
probabilidades promedio que dejó scripts/33. Usa la misma función de métrica que todo el
proyecto (petct.metrics.evaluate_study), así que los números son comparables.

Uso:
    python scripts/36_reevaluar_guardado.py --mascaras runs/B_ext_largo/mascaras_test \
        --etiqueta modelo_B_ext_largo_ultimo_crudo --particion test --incluir-zona-borrada
    python scripts/36_reevaluar_guardado.py --probabilidades runs/ensambles/ensamble_B_ens_tta/probabilidades_test \
        --umbral 0.7 --etiqueta ensamble_B_ens_tta_u07 --particion test
Escribe results/<etiqueta>_<particion>.csv.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.metrics import evaluate_study, summarize  # noqa: E402
from petct.preprocess import load_study  # noqa: E402


def split_files(manifest, procesado, particion):
    """Lo mismo que petct.data.split_files, sin importar torch (este script corre sin GPU)."""
    sub = pd.read_csv(manifest)
    sub = sub[sub.split == particion]
    fs = [Path(procesado) / f"{r.patient_id}__{r.study_uid}.npz" for r in sub.itertuples()]
    return sorted(f for f in fs if f.exists())


def main():
    ap = argparse.ArgumentParser()
    fuente = ap.add_mutually_exclusive_group(required=True)
    fuente.add_argument("--mascaras", help="carpeta con <estudio>.npz (clave pred)")
    fuente.add_argument("--probabilidades", help="carpeta con <estudio>.npz (clave prob)")
    ap.add_argument("--umbral", type=float, default=0.5, help="solo con --probabilidades")
    ap.add_argument("--particion", default="test", choices=["val", "test", "oof"])
    ap.add_argument("--manifest", default="data/manifests/subconjunto_extendido.csv")
    ap.add_argument("--procesado", default="data/processed")
    ap.add_argument("--etiqueta", required=True)
    ap.add_argument("--incluir-zona-borrada", action="store_true")
    a = ap.parse_args()

    carpeta = Path(a.mascaras or a.probabilidades)
    files = split_files(a.manifest, a.procesado, a.particion)
    faltan = [f.name for f in files if not (carpeta / f.name).exists()]
    if faltan:
        sys.exit(f"faltan {len(faltan)} de {len(files)} estudios en {carpeta} (p. ej. {faltan[0]})")
    rows = []
    for f in files:
        vol = load_study(f)
        z = np.load(carpeta / f.name)
        pred = z["pred"].astype(bool) if a.mascaras else (z["prob"].astype(np.float32) > a.umbral)
        m = evaluate_study(pred, vol["seg"].astype(bool), vol["suv"] * vol["suv_top"],
                           float(np.prod(vol["spacing"])) / 1000.0, exclude_blank=not a.incluir_zona_borrada)
        m["estudio"] = f.stem.split("__")[0]; m["variante"] = a.etiqueta
        rows.append(m)
    df = pd.DataFrame(rows)
    out = Path("results") / f"{a.etiqueta}_{a.particion}.csv"
    df.to_csv(out, index=False)
    s = summarize(df)
    print(f"{a.etiqueta} ({a.particion}, n={len(df)}): Dice⁺ {s['dice_pos']:.3f}  FPV {s['fpv_ml']:.2f} mL  "
          f"FNV {s['fnv_ml_pos']:.2f} mL  → {out}")


if __name__ == "__main__":
    main()
