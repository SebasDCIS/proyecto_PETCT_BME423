#!/usr/bin/env python
"""Paso 5b. ¿En qué órganos se equivoca cada modelo?

Uso:
    python scripts/12_analisis_por_organo.py --particion val
    python scripts/12_analisis_por_organo.py --particion test        # al final, una vez

Toma las máscaras predichas guardadas por scripts/09 (`runs/<corrida>/mascaras_<particion>/`),
la máscara del experto y el mapa de órganos (`data/processed_organos/`), y reparte por grupo
de órgano los mililitros de falsos positivos (componentes predichas que no tocan lesión) y de
falsos negativos (lesiones que ninguna predicción tocó). También lo hace para la referencia
clásica (umbral + morfología), para tener el punto de partida: dónde inventa el umbral su
litro.

Escribe:
  results/fp_por_organo_<particion>.csv          largo: corrida, modelo, estudio, grupo, fp_ml, fn_ml, lesion_ml
  results/fp_por_organo_<particion>_resumen.csv  ancho: modelo × grupo, media por estudio (promediando semillas)
  docs/figuras/fp_por_organo_<particion>.png     barras apiladas por modelo
"""
import argparse
import json
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.classical import classical_segmentation  # noqa: E402
from petct.organs import GROUP_NAMES, fn_by_organ, fp_by_organ, lesion_by_organ  # noqa: E402
from petct.preprocess import load_study  # noqa: E402


def corridas_con_mascaras(runs: Path, particion: str):
    out = {}
    for d in sorted(runs.glob("*/")):
        m = d / f"mascaras_{particion}"
        if m.exists() and not d.name.startswith("humo"):
            modelo = re.match(r"([A-Z]\+?)", d.name).group(1)
            out[d.name] = (modelo, m)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--particion", default="val", choices=["val", "test"])
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--procesado", default="data/processed")
    ap.add_argument("--organos", default="data/processed_organos")
    ap.add_argument("--manifest", default="data/manifests/subconjunto.csv")
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--sin-clasica", action="store_true")
    a = ap.parse_args()

    import yaml
    cfg = yaml.safe_load(open(a.config))["referencia_clasica"]
    sub = pd.read_csv(a.manifest)
    sub = sub[sub.split == a.particion]
    corridas = corridas_con_mascaras(Path(a.runs), a.particion)
    print(f"{len(sub)} estudios; corridas con máscaras: {list(corridas)}", flush=True)

    filas = []
    faltan = []
    for r in sub.itertuples():
        base = f"{r.patient_id}__{r.study_uid}"
        org_file = Path(a.organos) / f"{base}.npz"
        if not org_file.exists():
            faltan.append(r.patient_id); continue
        vol = load_study(Path(a.procesado) / f"{base}.npz")
        groups = np.load(org_file)["groups"]
        ml = float(np.prod(vol["spacing"])) / 1000.0
        valid = vol["suv"] > 0                      # fuera de la caja borrada por el defacing
        gt = vol["seg"].astype(bool) & valid
        les = lesion_by_organ(gt, groups, ml)

        preds = {}
        for nombre, (modelo, mdir) in corridas.items():
            f = mdir / f"{base}.npz"
            if f.exists():
                preds[(nombre, modelo)] = np.load(f)["pred"].astype(bool) & valid
        if not a.sin_clasica:
            suv_real = vol["suv"] * vol["suv_top"]
            preds[("clasica", "clasica")] = classical_segmentation(
                suv_real, vol["body"], ml, thr=cfg["umbral_suv"], open_radius=cfg["apertura_radio_vox"],
                min_ml=cfg["volumen_min_ml"], use_heuristics=False) & valid
        for (nombre, modelo), pred in preds.items():
            fp = fp_by_organ(pred, gt, groups, ml)
            fn = fn_by_organ(pred, gt, groups, ml)
            for g in GROUP_NAMES:
                filas.append({"corrida": nombre, "modelo": modelo, "estudio": r.patient_id, "diagnosis": r.diagnosis,
                              "grupo": g, "fp_ml": fp[g], "fn_ml": fn[g], "lesion_ml": les[g]})
        print(f"[ok] {r.patient_id}", flush=True)
    if faltan:
        print(f"sin mapa de órganos ({len(faltan)}): {faltan[:6]}... → correr scripts/11 primero")

    df = pd.DataFrame(filas)
    if df.empty:
        sys.exit("nada que analizar")
    Path("results").mkdir(exist_ok=True)
    df.to_csv(f"results/fp_por_organo_{a.particion}.csv", index=False)

    # media por estudio dentro de cada corrida, luego media entre corridas del mismo modelo
    por_corrida = df.groupby(["modelo", "corrida", "grupo"])[["fp_ml", "fn_ml", "lesion_ml"]].mean().reset_index()
    resumen = por_corrida.groupby(["modelo", "grupo"])[["fp_ml", "fn_ml", "lesion_ml"]].mean().reset_index()
    ancho = resumen.pivot(index="grupo", columns="modelo", values="fp_ml").reindex(GROUP_NAMES).fillna(0)
    ancho.loc["TOTAL"] = ancho.sum()
    ancho.round(1).to_csv(f"results/fp_por_organo_{a.particion}_resumen.csv")
    print("\nFalsos positivos por órgano (mL por estudio, media):\n", ancho.round(1).to_string())
    fn_ancho = resumen.pivot(index="grupo", columns="modelo", values="fn_ml").reindex(GROUP_NAMES).fillna(0)
    print("\nLesiones no detectadas por órgano (mL por estudio, media):\n", fn_ancho[fn_ancho.sum(axis=1) > 0].round(1).to_string())
    print("\nLesión anotada por órgano (mL por estudio):\n",
          resumen[resumen.modelo == resumen.modelo.iloc[0]].set_index("grupo").lesion_ml.reindex(GROUP_NAMES).round(1)[lambda s: s > 0].to_string())

    # figura: barras apiladas, un modelo por barra, solo grupos con algo
    modelos = [m for m in ["clasica", "A", "A+", "B", "C"] if m in ancho.columns]
    datos = ancho.drop(index="TOTAL")[modelos]
    datos = datos[datos.sum(axis=1) > 0.01 * datos.sum().sum()]
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [1, 2.2]})
    cmap = plt.get_cmap("tab20")
    for panel, cols in ((ax[0], [m for m in modelos if m == "clasica"]), (ax[1], [m for m in modelos if m != "clasica"])):
        if not cols:
            continue
        bottom = np.zeros(len(cols))
        for k, g in enumerate(datos.index):
            vals = datos.loc[g, cols].values
            panel.bar(cols, vals, bottom=bottom, color=cmap(k % 20), label=g if panel is ax[1] or len(ax) == 1 else None)
            bottom += vals
        panel.set_ylabel("falsos positivos (mL por estudio)")
        panel.grid(axis="y", alpha=.3)
    ax[0].set_title("referencia clásica"); ax[1].set_title("modelos (media sobre semillas)")
    ax[1].legend(fontsize=7, ncol=2)
    plt.suptitle(f"Dónde se inventan los falsos positivos ({a.particion}, {sub.patient_id.nunique()} estudios)")
    plt.tight_layout(); Path("docs/figuras").mkdir(parents=True, exist_ok=True)
    plt.savefig(f"docs/figuras/fp_por_organo_{a.particion}.png", dpi=130); plt.close()
    print(f"\nfigura: docs/figuras/fp_por_organo_{a.particion}.png")


if __name__ == "__main__":
    main()
