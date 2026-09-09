#!/usr/bin/env python
"""Paso 6. Traducir los resultados a lenguaje clínico, sin entrenar nada.

Uso:
    python scripts/16_analisis_clinico.py --particion val

Trabaja solo con las máscaras ya guardadas (`runs/*/mascaras_<particion>/`) y la anotación del
experto. Regla de cierre del proyecto: solo preguntas que la anotación puede contestar por sí
sola, comparando la máscara del experto con la del modelo. Todo respeta la regla de exclusión
de la zona borrada por el defacing (SUV = 0 fuera de pred y de gt).

Produce cuatro cosas:

1. Detección lesión por lesión. Cada componente 26-conexa de la anotación es una lesión; se
   considera detectada si la predicción la toca. Responde "¿a partir de qué tamaño el modelo
   encuentra la lesión?", que es una pregunta clínica y no un promedio de Dice.
2. Carga de corrección. Mililitros que habría que borrar (falso positivo) y que habría que
   añadir (falso negativo) para dejar la máscara del modelo igual a la del experto, frente a
   los mililitros que habría que dibujar desde cero. Es la utilidad real de una propuesta
   automática.
3. Concordancia de carga tumoral metabólica (MTV): predicha contra anotada, por estudio, con
   los números que hacen falta para un Bland-Altman.
4. Ensamble de las tres semillas por voto mayoritario (2 de 3), con el mapa de desacuerdo como
   medida de incertidumbre: dónde las tres semillas no se ponen de acuerdo es donde un médico
   debería mirar.

Además calcula intervalos de confianza por bootstrap sobre los estudios.

Escribe en results/: deteccion_lesiones_<particion>.csv, correccion_<particion>.csv,
ensamble_<particion>.csv, resumen_clinico_<particion>.csv; y las figuras en docs/figuras/.
"""
import argparse
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.metrics import evaluate_study, summarize  # noqa: E402
from petct.preprocess import load_study  # noqa: E402

CONN = np.ones((3, 3, 3), dtype=bool)          # 26 vecinos, como en autoPET


def corridas_de(runs: Path, particion: str):
    """{modelo: {corrida: carpeta de máscaras}}, ignorando humo y pilotos."""
    out = {}
    for d in sorted(runs.glob("*/")):
        m = d / f"mascaras_{particion}"
        if not m.exists() or d.name.startswith("humo") or "piloto" in d.name:
            continue
        modelo = re.match(r"([A-Z]\+?)", d.name).group(1)
        out.setdefault(modelo, {})[d.name] = m
    return out


def lesiones(gt: np.ndarray, pred: np.ndarray, suv: np.ndarray, ml: float):
    """Una fila por lesión anotada: volumen, SUVmax y si la predicción la toca."""
    lab, n = ndi.label(gt, CONN)
    filas = []
    for i in range(1, n + 1):
        m = lab == i
        filas.append({"lesion_ml": float(m.sum() * ml),
                      "suvmax": float(suv[m].max()),
                      "detectada": bool((pred & m).any()),
                      "solape_frac": float((pred & m).sum() / m.sum())})
    return filas


def boot_ci(valores, n=2000, seed=0):
    """Intervalo de confianza del 95 % de la media, por bootstrap sobre los estudios."""
    v = np.asarray([x for x in valores if np.isfinite(x)], dtype=float)
    if len(v) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    medias = v[rng.integers(0, len(v), size=(n, len(v)))].mean(axis=1)
    return (float(np.percentile(medias, 2.5)), float(np.percentile(medias, 97.5)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--particion", default="val", choices=["val", "test"])
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--procesado", default="data/processed")
    ap.add_argument("--manifest", default="data/manifests/subconjunto.csv")
    a = ap.parse_args()

    sub = pd.read_csv(a.manifest)
    sub = sub[sub.split == a.particion]
    corridas = corridas_de(Path(a.runs), a.particion)
    print(f"{len(sub)} estudios · modelos: { {k: list(v) for k, v in corridas.items()} }", flush=True)

    f_les, f_cor, f_ens = [], [], []

    for r in sub.itertuples():
        base = f"{r.patient_id}__{r.study_uid}"
        vol = load_study(Path(a.procesado) / f"{base}.npz")
        suv = vol["suv"] * vol["suv_top"]
        ml = float(np.prod(vol["spacing"])) / 1000.0
        valido = suv > 0                                  # fuera de la caja del defacing
        gt = vol["seg"].astype(bool) & valido

        for modelo, runs_m in corridas.items():
            masks = []
            for corrida, mdir in runs_m.items():
                f = mdir / f"{base}.npz"
                if not f.exists():
                    continue
                pred = np.load(f)["pred"].astype(bool) & valido
                masks.append(pred)

                for L in lesiones(gt, pred, suv, ml):
                    f_les.append({"estudio": r.patient_id, "diagnosis": r.diagnosis,
                                  "modelo": modelo, "corrida": corrida, **L})

                # carga de corrección: componentes predichas que no tocan lesión (borrar)
                # y lesiones que la predicción no toca ni parcialmente (añadir entero),
                # más el borde que falta dentro de las lesiones sí detectadas
                lab_p, np_ = ndi.label(pred, CONN)
                borrar = 0.0
                if np_:
                    toca = np.zeros(np_ + 1, dtype=bool)
                    idx = lab_p[gt & pred]
                    toca[np.unique(idx)] = True
                    borrar = float(np.isin(lab_p, np.nonzero(~toca)[0][1:]).sum() * ml) if (~toca[1:]).any() else 0.0
                anadir = float((gt & ~pred).sum() * ml)
                f_cor.append({"estudio": r.patient_id, "diagnosis": r.diagnosis,
                              "modelo": modelo, "corrida": corrida,
                              "borrar_ml": borrar, "anadir_ml": anadir,
                              "corregir_ml": borrar + anadir,
                              "desde_cero_ml": float(gt.sum() * ml),
                              "mtv_pred_ml": float(pred.sum() * ml),
                              "mtv_gt_ml": float(gt.sum() * ml)})

            # ensamble: voto mayoritario de las semillas disponibles
            if len(masks) >= 2:
                suma = np.sum(masks, axis=0)
                voto = suma >= (len(masks) + 1) // 2 + (1 if len(masks) % 2 == 0 else 0)
                voto = suma > len(masks) / 2.0
                desacuerdo = (suma > 0) & (suma < len(masks))
                m = evaluate_study(voto, vol["seg"].astype(bool), suv, ml, exclude_blank=True)
                m.update({"estudio": r.patient_id, "diagnosis": r.diagnosis,
                          "modelo": modelo, "variante": f"{modelo}_ensamble",
                          "desacuerdo_ml": float(desacuerdo.sum() * ml),
                          "n_semillas": len(masks)})
                f_ens.append(m)
        print(f"[ok] {r.patient_id}", flush=True)

    Path("results").mkdir(exist_ok=True)
    les = pd.DataFrame(f_les); cor = pd.DataFrame(f_cor); ens = pd.DataFrame(f_ens)
    les.to_csv(f"results/deteccion_lesiones_{a.particion}.csv", index=False)
    cor.to_csv(f"results/correccion_{a.particion}.csv", index=False)
    ens.to_csv(f"results/ensamble_{a.particion}.csv", index=False)

    # ---------------------------------------------------------------- detección por tamaño
    cortes = [0, 1, 3, 10, 30, 100, np.inf]
    etiq = ["<1 mL", "1–3", "3–10", "10–30", "30–100", "≥100 mL"]
    les["tramo"] = pd.cut(les.lesion_ml, cortes, labels=etiq, right=False)
    tab = les.groupby(["modelo", "tramo"], observed=True).agg(
        lesiones=("detectada", "size"), detectadas=("detectada", "sum")).reset_index()
    tab["sensibilidad"] = tab.detectadas / tab.lesiones
    print("\n=== Detección lesión por lesión, por tamaño ===")
    piv = tab.pivot(index="tramo", columns="modelo", values="sensibilidad")
    n_por_tramo = les.groupby("tramo", observed=True).size() // max(1, les.corrida.nunique())
    piv.insert(0, "lesiones (por corrida)", n_por_tramo)
    print(piv.round(3).to_string())
    tab.to_csv(f"results/deteccion_por_tamano_{a.particion}.csv", index=False)

    # ---------------------------------------------------------------- carga de corrección
    print("\n=== Carga de corrección (mL por estudio, media sobre semillas) ===")
    pc = cor.groupby(["modelo", "corrida"])[["borrar_ml", "anadir_ml", "corregir_ml", "desde_cero_ml"]].mean()
    res = pc.groupby("modelo").mean()
    res["ahorro_%"] = 100 * (1 - res.corregir_ml / res.desde_cero_ml)
    print(res.round(1).to_string())
    res.to_csv(f"results/resumen_clinico_{a.particion}.csv")

    # ---------------------------------------------------------------- ensamble
    if not ens.empty:
        print("\n=== Ensamble por voto mayoritario (2 de 3) ===")
        for modelo, g in ens.groupby("modelo"):
            s = summarize(g)
            ic = boot_ci(g[g.mtv_gt_ml > 0].dice.values)
            print(f"  {modelo}: Dice {s['dice_pos']:.3f} (IC95 {ic[0]:.3f}–{ic[1]:.3f}) · "
                  f"FPV {s['fpv_ml']:.1f} · FNV {s['fnv_ml_pos']:.1f} · "
                  f"desacuerdo entre semillas {g.desacuerdo_ml.mean():.1f} mL/estudio")

    # ---------------------------------------------------------------- figura
    fig, ax = plt.subplots(1, 3, figsize=(14, 4.2))
    for modelo, g in tab.groupby("modelo"):
        ax[0].plot(range(len(etiq)), [g[g.tramo == e].sensibilidad.mean() if (g.tramo == e).any() else np.nan for e in etiq],
                   marker="o", label=modelo)
    ax[0].set_xticks(range(len(etiq))); ax[0].set_xticklabels(etiq, rotation=30, ha="right")
    ax[0].set_ylim(0, 1.03); ax[0].set_ylabel("lesiones detectadas"); ax[0].grid(alpha=.3)
    ax[0].set_title("Detección por tamaño de lesión"); ax[0].legend(fontsize=8)

    m0 = cor.modelo.iloc[0]
    c0 = cor[cor.modelo == m0].groupby("estudio")[["corregir_ml", "desde_cero_ml"]].mean()
    ax[1].scatter(c0.desde_cero_ml, c0.corregir_ml, s=22, alpha=.75, color="#D9601C")
    lim = max(1.0, c0.max().max())
    ax[1].plot([0, lim], [0, lim], "k--", lw=1, label="dibujar desde cero")
    ax[1].set_xscale("symlog"); ax[1].set_yscale("symlog")
    ax[1].set_xlabel("lesión anotada (mL)"); ax[1].set_ylabel("mL a corregir")
    ax[1].set_title(f"Carga de corrección · modelo {m0}"); ax[1].grid(alpha=.3); ax[1].legend(fontsize=8)

    d = cor[cor.modelo == m0].groupby("estudio")[["mtv_pred_ml", "mtv_gt_ml"]].mean()
    d = d[d.mtv_gt_ml > 0]
    prom = (d.mtv_pred_ml + d.mtv_gt_ml) / 2; dif = d.mtv_pred_ml - d.mtv_gt_ml
    ax[2].scatter(prom, dif, s=22, alpha=.75, color="#4E6B8C")
    ax[2].axhline(dif.mean(), color="k", lw=1)
    ax[2].axhline(dif.mean() + 1.96 * dif.std(), color="k", ls="--", lw=1)
    ax[2].axhline(dif.mean() - 1.96 * dif.std(), color="k", ls="--", lw=1)
    ax[2].set_xscale("symlog")
    ax[2].set_xlabel("MTV medio (mL)"); ax[2].set_ylabel("predicho − anotado (mL)")
    ax[2].set_title(f"Concordancia de MTV · modelo {m0}"); ax[2].grid(alpha=.3)
    plt.tight_layout()
    Path("docs/figuras").mkdir(parents=True, exist_ok=True)
    plt.savefig(f"docs/figuras/clinico_{a.particion}.png", dpi=130); plt.close()
    print(f"\nfigura: docs/figuras/clinico_{a.particion}.png")

    print("\nsesgo de MTV (predicho − anotado, mL): "
          f"media {dif.mean():.1f}, límites de concordancia {dif.mean() - 1.96 * dif.std():.1f} a "
          f"{dif.mean() + 1.96 * dif.std():.1f}")


if __name__ == "__main__":
    main()
