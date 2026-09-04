#!/usr/bin/env python
"""Paso 3/5. Resumir todas las corridas de entrenamiento y sus evaluaciones.

Uso:
    python scripts/10_resumir_corridas.py                # lee runs/*/ y results/modelo_*_{val,test}.csv

Produce:
  results/corridas.csv            una fila por corrida: modelo, semilla, iteraciones, mejor Dice de
                                  validación rápida, s/it, minutos.
  results/comparacion_modelos.csv media ± desviación por modelo (sobre semillas) de Dice, FPV y FNV
                                  en cada partición evaluada con scripts/09, junto a la referencia clásica.
  docs/figuras/curvas_entrenamiento.png   pérdida y Dice de validación rápida contra la iteración.

La convención de nombres: la carpeta de la corrida es runs/<modelo>[_s<semilla>] y la
evaluación results/modelo_<modelo>[_s<semilla>]_<particion>.csv. La semilla se lee del
resumen.json, no del nombre.
"""
import argparse
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def resumen_corridas(runs: Path) -> pd.DataFrame:
    filas = []
    for d in sorted(runs.glob("*/")):
        rj = d / "resumen.json"
        if not rj.exists() or d.name.startswith("humo"):
            continue
        r = json.load(open(rj))
        cfg = r.get("config", {})
        log = pd.read_csv(d / "log_entrenamiento.csv") if (d / "log_entrenamiento.csv").exists() else None
        val = pd.read_csv(d / "validacion.csv") if (d / "validacion.csv").exists() else None
        filas.append({
            "corrida": d.name, "modelo": r.get("modelo"), "semilla": cfg.get("semilla"),
            "small": cfg.get("small", False), "iteraciones": r.get("iteraciones_hechas"),
            "mejor_dice_val_rapida": r.get("mejor_dice_val"),
            "iter_mejor": int(val.loc[val.mejor == 1, "iter"].max()) if val is not None and (val.mejor == 1).any() else None,
            "loss_final": r.get("loss_final"),
            "seg_por_iter": float(log.seg_por_iter.median()) if log is not None else None,
            "minutos": r.get("minutos"), "dispositivo": r.get("dispositivo"),
        })
    return pd.DataFrame(filas)


def resumen_evaluaciones(results: Path) -> pd.DataFrame:
    """Una fila por (etiqueta, partición) con Dice en positivos, FPV y FNV; más la referencia clásica."""
    filas = []
    for f in sorted(results.glob("modelo_*_*.csv")):
        m = re.match(r"modelo_([A-Z])(?:_s(\d+))?_(train|val|test)\.csv", f.name)
        if not m:
            continue
        df = pd.read_csv(f)
        pos = df[df.mtv_gt_ml > 0]
        filas.append({"modelo": m.group(1), "semilla": m.group(2) or "yaml", "particion": m.group(3),
                      "n": len(df), "dice_pos": pos.dice.mean(), "fpv_ml": df.fpv_ml.mean(),
                      "fnv_ml": pos.fnv_ml.mean(), "fpv_ml_neg": df[df.mtv_gt_ml == 0].fpv_ml.mean()})
    ev = pd.DataFrame(filas)
    ref = results / "referencia_clasica.csv"
    if ref.exists():
        r = pd.read_csv(ref)
        sub = pd.read_csv("data/manifests/subconjunto.csv")[["patient_id", "split"]]
        r = r.merge(sub, left_on="estudio", right_on="patient_id")
        r = r[r.variante == "umbral+morfologia"]
        for part, g in r.groupby("split"):
            pos = g[g.mtv_gt_ml > 0]
            filas.append({"modelo": "clasica", "semilla": "-", "particion": part, "n": len(g),
                          "dice_pos": pos.dice.mean(), "fpv_ml": g.fpv_ml.mean(), "fnv_ml": pos.fnv_ml.mean(),
                          "fpv_ml_neg": g[g.mtv_gt_ml == 0].fpv_ml.mean()})
        ev = pd.DataFrame(filas)
    if ev.empty:
        return ev
    agg = ev.groupby(["modelo", "particion"]).agg(
        n_corridas=("semilla", "size"), dice_pos=("dice_pos", "mean"), dice_pos_sd=("dice_pos", "std"),
        fpv_ml=("fpv_ml", "mean"), fpv_ml_sd=("fpv_ml", "std"), fnv_ml=("fnv_ml", "mean"), fnv_ml_sd=("fnv_ml", "std"),
        fpv_ml_neg=("fpv_ml_neg", "mean")).reset_index()
    return agg.round(3)


def figura_curvas(runs: Path, out: Path):
    dirs = [d for d in sorted(runs.glob("*/")) if (d / "log_entrenamiento.csv").exists() and not d.name.startswith("humo")]
    if not dirs:
        return
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    for d in dirs:
        log = pd.read_csv(d / "log_entrenamiento.csv")
        ax[0].plot(log.iter, log.loss.rolling(10, min_periods=1).mean(), label=d.name, lw=1)
        vf = d / "validacion.csv"
        if vf.exists():
            val = pd.read_csv(vf)
            ax[1].plot(val.iter, val.dice_pos, "o-", ms=3, lw=1, label=d.name)
    ax[0].set_xlabel("iteración"); ax[0].set_ylabel("pérdida Dice + CE (media móvil)"); ax[0].set_title("entrenamiento")
    ax[1].set_xlabel("iteración"); ax[1].set_ylabel("Dice en positivos (validación rápida)"); ax[1].set_title("validación")
    ax[1].axhline(0.179, ls="--", c="gray", lw=1); ax[1].text(0, 0.185, "referencia clásica (0,18)", color="gray", fontsize=8)
    for a in ax:
        a.legend(fontsize=7); a.grid(alpha=.3)
    plt.tight_layout(); out.parent.mkdir(parents=True, exist_ok=True); plt.savefig(out, dpi=130); plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--results", default="results")
    a = ap.parse_args()
    runs, results = Path(a.runs), Path(a.results)
    corridas = resumen_corridas(runs)
    if not corridas.empty:
        corridas.to_csv(results / "corridas.csv", index=False)
        print("Corridas:\n", corridas.to_string(index=False))
    comp = resumen_evaluaciones(results)
    if not comp.empty:
        comp.to_csv(results / "comparacion_modelos.csv", index=False)
        print("\nComparación (media ± sd sobre semillas):\n", comp.to_string(index=False))
    figura_curvas(runs, Path("docs/figuras/curvas_entrenamiento.png"))
    print("\nfigura: docs/figuras/curvas_entrenamiento.png")


if __name__ == "__main__":
    main()
