#!/usr/bin/env python
"""Casos cualitativos de la prueba: cuatro estudios elegidos con una regla fija.

No entrena ni predice nada. Lee las máscaras guardadas de la prueba y las métricas por estudio
que ya están en results/, y dibuja una fila por estudio con el MIP coronal del SUV:

    experto | umbral clásico | B extendido (semilla 423) | sistema final (ensamble + TTA, u 0,6)

Regla de selección (fijada antes de mirar las imágenes; se aplica sobre las métricas del
sistema final en la métrica corregida, la misma de las tablas):

  1. Caso típico: el estudio positivo cuyo Dice está más cerca de la mediana del Dice del
     sistema final. Muestra lo que pasa en un paciente cualquiera, no el mejor.
  2. Mayor falso positivo: el estudio (positivo o control) con más FPV del sistema final.
  3. Mayor falso negativo: el estudio positivo con más FNV del sistema final.
  4. Lo que corrige el ensamble: el estudio con mayor caída de FPV entre B solo y el
     sistema final.

Si un estudio ya fue elegido por una regla anterior, se toma el siguiente de esa lista.

Colores: verde = anotación del experto (contorno en todas las columnas); azul = islas
predichas que tocan una lesión; rojo = islas predichas que no tocan ninguna (falso
positivo). Las cifras bajo cada panel son las de las tablas del informe.

Uso (desde la raíz del repositorio):
    python scripts/42_casos_prueba.py
Escribe docs/figuras/casos_test.png y results/test_final/casos_test.csv.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from scipy import ndimage

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from petct.classical import classical_segmentation  # noqa: E402
from petct.metrics import blank_region_mask  # noqa: E402
from petct.preprocess import load_study  # noqa: E402

COLUMNAS = [
    ("Experto", None),
    ("Umbral clásico (SUV 2,5)", "clasica"),
    ("B extendido · semilla 423", "B_ext_largo"),
    ("Sistema final · ensamble + TTA, u 0,6", "ensambles/ensamble_final"),
]
DX = {"LUNG_CANCER": "cáncer de pulmón", "LYMPHOMA": "linfoma", "MELANOMA": "melanoma",
      "NEGATIVE": "control sin lesión"}
CONECT = np.ones((3, 3, 3), bool)  # 26-conectividad, la misma de las métricas


def coma(t):
    return t.replace(".", ",")


def metricas():
    fin = pd.read_csv(RAIZ / "results/ensamble_final_test.csv").set_index("estudio")
    b = pd.read_csv(RAIZ / "results/modelo_B_ext_largo_ultimo_test.csv").set_index("estudio")
    cl = pd.read_csv(RAIZ / "results/test_final/clasicas_test.csv")
    cl = cl[cl.brazo == "Clásica"].set_index("estudio")
    return {"ensambles/ensamble_final": fin, "B_ext_largo": b, "clasica": cl}


def elegir(fin, b):
    elegidos, motivo = [], {}

    def tomar(orden, etiqueta):
        for est in orden:
            if est not in elegidos:
                elegidos.append(est)
                motivo[est] = etiqueta
                return

    pos = fin[fin.mtv_gt_ml > 0]
    med = pos.dice.median()
    tomar((pos.dice - med).abs().sort_values().index, f"caso típico (Dice cercano a la mediana, {coma(f'{med:.2f}')})")
    tomar(fin.fpv_ml.sort_values(ascending=False).index, "mayor falso positivo del sistema final")
    tomar(pos.fnv_ml.sort_values(ascending=False).index, "mayor falso negativo del sistema final")
    tomar((b.fpv_ml - fin.fpv_ml).dropna().sort_values(ascending=False).index,
          "mayor corrección del ensamble frente a B solo")
    return elegidos, motivo


def capas(pred, gt):
    """Separa la predicción en islas que tocan lesión (verdaderas) y las que no (falsas)."""
    lab, n = ndimage.label(pred, structure=CONECT)
    if n == 0:
        return np.zeros_like(pred), np.zeros_like(pred)
    toca = np.unique(lab[gt & (lab > 0)])
    verdad = np.isin(lab, toca[toca > 0])
    return verdad, pred & ~verdad


def mip(m, head_at_end):
    img = m.max(axis=1)  # (z, y, x) -> coronal (z, x)
    return np.flipud(img) if head_at_end else img


def main():
    M = metricas()
    fin, b = M["ensambles/ensamble_final"], M["B_ext_largo"]
    elegidos, motivo = elegir(fin, b)
    man = pd.read_csv(RAIZ / "data/manifests/subconjunto_extendido.csv").set_index("patient_id")

    filas = []
    fig, axes = plt.subplots(len(elegidos), len(COLUMNAS), figsize=(3.1 * len(COLUMNAS), 5.0 * len(elegidos)),
                             squeeze=False)
    azul = ListedColormap(["none", "#2B6CB0"])
    rojo = ListedColormap(["none", "#D1342F"])
    verde = ListedColormap(["none", "#2E9E5B"])

    for i, est in enumerate(elegidos):
        uid = man.loc[est, "study_uid"]
        nombre = f"{est}__{uid}.npz"
        vol = load_study(RAIZ / "data/processed" / nombre)
        suv = vol["suv"] * vol["suv_top"]
        blank = blank_region_mask(suv)
        gt = vol["seg"].astype(bool) & ~blank
        hae = vol["head_at_end"]
        ml = float(np.prod(vol["spacing"])) / 1000.0
        fondo = mip(np.clip(suv, 0, 10), hae)
        gt2 = mip(gt, hae)
        dx = DX.get(man.loc[est, "diagnosis"], man.loc[est, "diagnosis"])

        for j, (titulo, clave) in enumerate(COLUMNAS):
            ax = axes[i, j]
            ax.imshow(fondo, cmap="gray_r", vmin=0, vmax=10, interpolation="nearest")
            if clave is None:
                ax.imshow(gt2, cmap=verde, alpha=0.75, interpolation="nearest")
                mtv = coma(f"{fin.loc[est, 'mtv_gt_ml']:.1f}")
                pie = f"MTV {mtv} mL" if gt.any() else "sin lesión anotada"
            else:
                if clave == "clasica":
                    pred = classical_segmentation(suv, vol["body"], ml, 2.5, 1, 0.5, organ_masks=None,
                                                  use_heuristics=False, head_at_end=bool(hae))
                else:
                    pred = np.load(RAIZ / "runs" / clave / "mascaras_test" / nombre)["pred"].astype(bool)
                pred = pred & ~blank
                v, f = capas(pred, gt)
                ax.imshow(mip(v, hae), cmap=azul, alpha=0.7, interpolation="nearest")
                ax.imshow(mip(f, hae), cmap=rojo, alpha=0.7, interpolation="nearest")
                if gt.any():
                    ax.contour(gt2, levels=[0.5], colors="#2E9E5B", linewidths=0.9)
                r = M[clave].loc[est]
                dice = "no aplica" if not gt.any() else coma(f"{r.dice:.2f}")
                pie = f"Dice {dice} · FPV {coma(f'{r.fpv_ml:.1f}')} · FNV {coma(f'{r.fnv_ml:.1f}')} mL"
                filas.append(dict(estudio=est, regla=motivo[est], diagnostico=dx, metodo=titulo,
                                  dice=r.dice, fpv_ml=r.fpv_ml, fnv_ml=r.fnv_ml, mtv_gt_ml=r.mtv_gt_ml))
            ax.set_xticks([]); ax.set_yticks([])
            for s in ax.spines.values():
                s.set_visible(False)
            if i == 0:
                ax.set_title(titulo, fontsize=10, fontweight="bold")
            ax.set_xlabel(pie, fontsize=8.5)
        axes[i, 0].set_ylabel(f"{chr(65 + i)} · {dx}\n{motivo[est]}", fontsize=9)

    fig.legend(handles=[Line2D([], [], color="#2E9E5B", lw=2, label="anotación del experto"),
                        Patch(color="#2B6CB0", label="isla predicha que toca una lesión"),
                        Patch(color="#D1342F", label="isla predicha sin lesión (falso positivo)")],
               loc="lower center", ncol=3, frameon=False, fontsize=9)
    fig.suptitle("Casos de la prueba elegidos con regla fija · MIP coronal del SUV (0 a 10)", fontsize=12)
    fig.tight_layout(rect=(0, 0.025, 1, 0.98))
    salida = RAIZ / "docs/figuras/casos_test.png"
    fig.savefig(salida, dpi=150)
    pd.DataFrame(filas).to_csv(RAIZ / "results/test_final/casos_test.csv", index=False)
    print("elegidos:", [(e, motivo[e]) for e in elegidos])
    print("escrito", salida)


if __name__ == "__main__":
    main()
