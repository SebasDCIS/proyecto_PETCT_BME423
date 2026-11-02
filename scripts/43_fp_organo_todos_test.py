#!/usr/bin/env python
"""Falso positivo por órgano en la prueba para todos los brazos, no solo B y el ensamble.

`scripts/37` dejó en results/test_final/fp_por_organo.csv solo B (3 semillas), el ensamble y
el sistema final. La parcial avisó que el brazo E no aparecía en el FP por órgano porque se
agregó después; este script completa la tabla con los brazos del acto 1 (A, B, C, E), los
del extendido (A, A+, C) y la referencia clásica, sobre las máscaras ya guardadas.

Misma convención que scripts/37 (sección S4): FP = islas predichas que no tocan ninguna
lesión anotada, repartidas según el mapa de órganos de TotalSegmentator, en mL por estudio,
incluida la zona anonimizada. Con varias semillas se promedia primero por corrida y después
entre corridas. Es un análisis descriptivo, fuera del preregistro.

Reanudable: guarda un archivo por estudio y se puede cortar con --max-segundos.

Uso (desde la raíz del repositorio):
    python scripts/43_fp_organo_todos_test.py --max-segundos 130   # repetir hasta que diga "listo"
Escribe results/test_final/fp_por_organo_todos.csv y docs/figuras/fp_por_organo_test.png.
"""
import argparse
import pickle
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from petct.classical import classical_segmentation  # noqa: E402
from petct.organs import GROUP_NAMES, fp_by_organ  # noqa: E402
from petct.preprocess import load_study  # noqa: E402

BRAZOS = {
    "Clásica": [None],
    "Acto 1 · A": ["A", "A_s2", "A_s3"],
    "Acto 1 · B": ["B", "B_s2", "B_s3"],
    "Acto 1 · C": ["C", "C_s2", "C_s3"],
    "Acto 1 · E": ["E", "E_s2", "E_s3"],
    "Extendido · A": ["A_ext_largo", "A_ext_largo_s2", "A_ext_largo_s3"],
    "Extendido · A+": ["Aplus_ext_largo", "Aplus_ext_largo_s2", "Aplus_ext_largo_s3"],
    "Extendido · B": ["B_ext_largo", "B_ext_largo_s2", "B_ext_largo_s3"],
    "Extendido · C": ["C_ext_largo", "C_ext_largo_s2", "C_ext_largo_s3"],
    "Sistema final (u 0,6)": ["ensambles/ensamble_final"],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="data/manifests/subconjunto_extendido.csv")
    ap.add_argument("--max-segundos", type=float, default=1e9)
    a = ap.parse_args()
    t0 = time.time()
    sub = pd.read_csv(RAIZ / a.manifest)
    sub = sub[sub.split == "test"]
    cache = RAIZ / "results/test_final/_s43_test"
    cache.mkdir(parents=True, exist_ok=True)

    for r in sub.itertuples():
        if (cache / f"{r.patient_id}.pkl").exists():
            continue
        if time.time() - t0 > a.max_segundos:
            print("tiempo agotado; volver a correr para seguir", flush=True)
            return
        nombre = f"{r.patient_id}__{r.study_uid}.npz"
        vol = load_study(RAIZ / "data/processed" / nombre)
        seg = vol["seg"].astype(bool)
        groups = np.load(RAIZ / "data/processed_organos" / nombre)["groups"]
        ml = float(np.prod(vol["spacing"])) / 1000.0
        filas = []
        for brazo, corridas in BRAZOS.items():
            for c in corridas:
                if c is None:
                    pred = classical_segmentation(vol["suv"] * vol["suv_top"], vol["body"], ml, 2.5, 1, 0.5,
                                                  organ_masks=None, use_heuristics=False,
                                                  head_at_end=bool(vol["head_at_end"]))
                else:
                    pred = np.load(RAIZ / "runs" / c / "mascaras_test" / nombre)["pred"].astype(bool)
                fp = fp_by_organ(pred, seg, groups, ml)
                filas += [dict(estudio=r.patient_id, brazo=brazo, corrida=c or brazo, grupo=g, fp_ml=fp[g])
                          for g in GROUP_NAMES]
        pickle.dump(filas, open(cache / f"{r.patient_id}.pkl", "wb"))
        print(f"[ok] {r.patient_id}", flush=True)

    df = pd.DataFrame([f for p in sorted(cache.glob("*.pkl")) for f in pickle.load(open(p, "rb"))])
    por_corrida = df.groupby(["brazo", "corrida", "grupo"]).fp_ml.mean().reset_index()
    ancho = (por_corrida.groupby(["brazo", "grupo"]).fp_ml.mean().unstack("brazo")
             .reindex(GROUP_NAMES)[list(BRAZOS)])
    ancho.loc["TOTAL"] = ancho.sum()
    ancho.to_csv(RAIZ / "results/test_final/fp_por_organo_todos.csv")
    print(ancho.round(2).to_string())
    figura(ancho.drop(index="TOTAL"))
    print("listo", flush=True)


GRUPOS_FIG = [  # (etiqueta, grupos de TotalSegmentator que suma)
    ("hígado", ["higado"]),
    ("riñones y vejiga", ["rinones", "vejiga"]),
    ("corazón y vasos", ["corazon", "vasos"]),
    ("intestino y estómago", ["intestino", "estomago"]),
    ("bazo", ["bazo"]),
    ("hueso", ["hueso"]),
    ("tejido sin órgano asignado", ["otro"]),
    ("fuera del mapa de órganos", ["fuera"]),
    ("resto", None),
]
ETIQUETAS = {"Clásica": "Clásica", "Acto 1 · A": "A", "Acto 1 · B": "B", "Acto 1 · C": "C", "Acto 1 · E": "E",
             "Extendido · A": "A", "Extendido · A+": "A+", "Extendido · B": "B", "Extendido · C": "C",
             "Sistema final (u 0,6)": "Final"}


def figura(t):
    usados = [g for _, gs in GRUPOS_FIG if gs for g in gs]
    filas = {et: (t.loc[gs].sum() if gs else t.drop(index=usados).sum()) for et, gs in GRUPOS_FIG}
    d = pd.DataFrame(filas).T
    colores = ["#8C5A2B", "#C9A227", "#B23A48", "#6A994E", "#7B5EA7", "#9AA5B1", "#3E7CB1", "#5FB3B3", "#D9D9D9"]
    fig, (a0, a1) = plt.subplots(1, 2, figsize=(10.5, 4.2), gridspec_kw={"width_ratios": [1, 6]})
    redes = [c for c in d.columns if c != "Clásica"]
    for ax, cols in ((a0, ["Clásica"]), (a1, redes)):
        abajo = np.zeros(len(cols))
        x = np.arange(len(cols))
        for k, et in enumerate(d.index):
            v = d.loc[et, cols].values
            ax.bar(x, v, bottom=abajo, color=colores[k], width=0.7, label=et if ax is a1 else None)
            abajo += v
        for xi, tot in zip(x, abajo):
            ax.text(xi, tot, f"{tot:.1f}".replace(".", ","), ha="center", va="bottom", fontsize=8)
        ax.set_xticks(x, [ETIQUETAS[c] for c in cols])
        ax.set_ylabel("falso positivo (mL por estudio)")
        ax.grid(axis="y", alpha=.3); ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
    for xm, txt in ((1.5, "acto 1 · 176 estudios, 25 000 it."), (5.0, "extendido · 825 estudios, 100 000 it.")):
        a1.text(xm, -0.16, txt, transform=a1.get_xaxis_transform(), ha="center", fontsize=8.5, color="#444")
    a1.axvline(3.5, color="#999", lw=0.8, ls=":"); a1.axvline(7.5, color="#999", lw=0.8, ls=":")
    a0.set_title("umbral clásico", fontsize=10); a1.set_title("redes (media de 3 semillas; final = ensamble)", fontsize=10)
    a1.legend(fontsize=7.5, ncol=1, frameon=False, loc="upper right", bbox_to_anchor=(1.0, 1.0))
    fig.tight_layout()
    fig.savefig(RAIZ / "docs/figuras/fp_por_organo_test.png", dpi=170)


if __name__ == "__main__":
    main()
