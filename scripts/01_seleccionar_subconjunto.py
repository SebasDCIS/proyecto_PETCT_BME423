#!/usr/bin/env python
"""Paso 1a — Elegir el subconjunto de 250 estudios con semilla fija.

Uso:
    python scripts/01_seleccionar_subconjunto.py data/manifests/clinical_tcia.csv

Entrada: el CSV clínico de la colección FDG-PET-CT-Lesions (descargar desde la
página de TCIA, "Clinical data", 1.3 MB).
Salida:  data/manifests/subconjunto.csv  (patient_id, study_uid, diagnosis, split, seed)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.tcia import load_clinical, select_subset  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clinical_csv")
    ap.add_argument("--out", default="data/manifests/subconjunto.csv")
    ap.add_argument("--n-positive", type=int, default=200)
    ap.add_argument("--n-negative", type=int, default=50)
    ap.add_argument("--seed", type=int, default=423)
    a = ap.parse_args()

    clin = load_clinical(a.clinical_csv)
    print("Diagnósticos en el CSV clínico:")
    print(clin.diagnosis.value_counts().to_string())
    sub = select_subset(clin, a.n_positive, a.n_negative, a.seed)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    sub.to_csv(a.out, index=False)
    print(f"\nSubconjunto: {len(sub)} estudios → {a.out}")
    print(sub.groupby(["split", "diagnosis"]).size().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()
