#!/usr/bin/env python
"""Paso 2b. Correr la referencia clásica sobre los estudios procesados y medirla.

Uso:
    python scripts/05_referencia_clasica.py --processed data/processed --out results/referencia_clasica.csv

Por cada estudio: umbral SUV, apertura, tamaño mínimo, exclusión de órganos
(heurística mientras no haya máscaras del CT) y las métricas de autoPET.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.preprocess import load_study  # noqa: E402
from petct.classical import classical_segmentation  # noqa: E402
from petct.metrics import evaluate_study  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--processed", default="data/processed")
    ap.add_argument("--out", default="results/referencia_clasica.csv")
    ap.add_argument("--config", default="configs/default.yaml")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config))["referencia_clasica"]

    rows = []
    for f in sorted(Path(a.processed).glob("*.npz")):
        vol = load_study(f)
        ml = float(np.prod(vol["spacing"]) / 1000.0)
        suv = vol["suv"] * vol["suv_top"]
        # dos variantes: solo umbral + morfología, y con la exclusión heurística de órganos.
        # Se reportan las dos porque la heurística puede borrar lesiones reales (ver bitácora).
        for variante, heur in (("umbral+morfologia", False), ("con_exclusion_heuristica", True)):
            pred = classical_segmentation(suv, vol["body"], ml, cfg["umbral_suv"],
                                          cfg["apertura_radio_vox"], cfg["volumen_min_ml"],
                                          use_heuristics=heur, head_at_end=vol["head_at_end"])
            m = evaluate_study(pred, vol["seg"], suv, ml)
            m["estudio"], m["variante"] = f.stem[:16], variante
            rows.append(m)
            print(f"{f.stem[:16]} {variante:26s} dice={m['dice']:.3f} FPV={m['fpv_ml']:7.1f} FNV={m['fnv_ml']:6.1f}")
    df = pd.DataFrame(rows)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False)
    print("\nPromedios por variante:")
    print(df.groupby("variante")[["dice", "fpv_ml", "fnv_ml"]].mean().round(3).to_string())


if __name__ == "__main__":
    main()
