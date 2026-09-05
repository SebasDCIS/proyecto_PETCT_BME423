#!/usr/bin/env python
"""Recalcular las métricas de corridas ya evaluadas a partir de sus máscaras guardadas.

Uso:
    python scripts/14_reevaluar_desde_mascaras.py --particion val

Sirve cuando cambia la regla de evaluación (aquí: excluir la zona borrada por el defacing)
y no hace falta volver a correr la red: `scripts/09 --guardar-mascaras` dejó las máscaras
predichas en `runs/<corrida>/mascaras_<particion>/`. Sobrescribe
`results/modelo_<corrida>_<particion>.csv` y guarda la versión anterior en
`results/sin_exclusion/`.
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.metrics import evaluate_study, summarize  # noqa: E402
from petct.preprocess import load_study  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--particion", default="val")
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--incluir-zona-borrada", action="store_true")
    a = ap.parse_args()
    sub = pd.read_csv("data/manifests/subconjunto.csv")
    sub = sub[sub.split == a.particion]
    Path("results/sin_exclusion").mkdir(parents=True, exist_ok=True)
    for d in sorted(Path(a.runs).glob("*/")):
        mdir = d / f"mascaras_{a.particion}"
        if not mdir.exists() or d.name.startswith("humo"):
            continue
        modelo = re.match(r"([A-Z]\+?)", d.name).group(1)
        etiqueta = f"modelo_{d.name}"
        rows = []
        for r in sub.itertuples():
            base = f"{r.patient_id}__{r.study_uid}"
            f = mdir / f"{base}.npz"
            if not f.exists():
                continue
            vol = load_study(f"data/processed/{base}.npz")
            pred = np.load(f)["pred"].astype(bool)
            m = evaluate_study(pred, vol["seg"].astype(bool), vol["suv"] * vol["suv_top"],
                               float(np.prod(vol["spacing"])) / 1000.0, exclude_blank=not a.incluir_zona_borrada)
            m["estudio"], m["variante"] = r.patient_id, etiqueta
            rows.append(m)
        if not rows:
            continue
        df = pd.DataFrame(rows)
        out = Path("results") / f"{etiqueta}_{a.particion}.csv"
        if out.exists() and not (Path("results/sin_exclusion") / out.name).exists():
            shutil.copy(out, Path("results/sin_exclusion") / out.name)
        df.to_csv(out, index=False)
        s = summarize(df)
        print(f"{etiqueta}: {len(df)} estudios | Dice(pos) {s['dice_pos']:.3f} med {s['dice_pos_mediana']:.3f} | "
              f"FPV {s['fpv_ml']:.1f} | FNV {s['fnv_ml_pos']:.1f} | excluido {df.gt_excluido_ml.sum():.0f} mL")


if __name__ == "__main__":
    main()
