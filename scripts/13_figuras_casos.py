#!/usr/bin/env python
"""Paso 5c. Ver los casos: MIP coronal con la máscara del experto y la de cada modelo.

Uso:
    python scripts/13_figuras_casos.py --particion val --estudios PETCT_1a90052cb2 PETCT_e03b96666f PETCT_f6295a93a6
    python scripts/13_figuras_casos.py --particion val --peores 4      # los 4 con más FPV del modelo A

Para cada estudio dibuja una fila: el MIP coronal del SUV con el contorno del experto (verde)
y, en cada columna, el contorno predicho por una corrida (rojo) con su Dice, FPV y FNV. Si
existe el mapa de órganos, colorea los falsos positivos según el órgano en que caen. Es la
figura que responde "¿dónde se equivoca?" con los ojos, antes que con la tabla.
Escribe docs/figuras/casos_<particion>.png.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.metrics import evaluate_study  # noqa: E402
from petct.preprocess import load_study  # noqa: E402

try:
    from petct.organs import GROUP_NAMES, _false_positive_mask
except Exception:  # pragma: no cover
    GROUP_NAMES, _false_positive_mask = None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--particion", default="val")
    ap.add_argument("--estudios", nargs="*", default=None)
    ap.add_argument("--peores", type=int, default=0, help="elegir los N con más FPV en results/modelo_A_<particion>.csv")
    ap.add_argument("--corridas", nargs="*", default=None, help="por defecto todas las que tengan máscaras")
    ap.add_argument("--salida", default=None)
    a = ap.parse_args()

    sub = pd.read_csv("data/manifests/subconjunto.csv").set_index("patient_id")
    if a.peores:
        t = pd.read_csv(f"results/modelo_A_{a.particion}.csv").sort_values("fpv_ml", ascending=False)
        estudios = list(t.estudio.head(a.peores))
    else:
        estudios = a.estudios or []
    if not estudios:
        sys.exit("indica --estudios o --peores N")
    corridas = a.corridas or sorted(d.name for d in Path("runs").glob("*/") if (d / f"mascaras_{a.particion}").exists() and not (d.name.startswith("humo") or "piloto" in d.name))
    print("estudios:", estudios, "| corridas:", corridas)

    fig, axes = plt.subplots(len(estudios), 1 + len(corridas), figsize=(3.2 * (1 + len(corridas)), 4.6 * len(estudios)), squeeze=False)
    cmap_org = plt.get_cmap("tab20")
    for i, pid in enumerate(estudios):
        uid = sub.loc[pid, "study_uid"]; base = f"{pid}__{uid}"
        vol = load_study(f"data/processed/{base}.npz")
        suv = vol["suv"] * vol["suv_top"]; valid = suv > 0
        gt_raw = vol["seg"].astype(bool); gt = gt_raw & valid     # la lesión anotada en la zona borrada se dibuja aparte
        ml = float(np.prod(vol["spacing"])) / 1000.0
        origin = "lower" if vol["head_at_end"] else "upper"
        mip = suv.max(axis=1)
        org_file = Path(f"data/processed_organos/{base}.npz")
        groups = np.load(org_file)["groups"] if org_file.exists() else None

        ax = axes[i, 0]
        ax.imshow(mip, cmap="gray_r", vmin=0, vmax=8, origin=origin)
        if gt.any():
            ax.contour(gt.max(axis=1), levels=[0.5], colors="lime", linewidths=0.9, origin=origin)
        borrada = gt_raw & ~valid
        if borrada.any():
            ax.contour(borrada.max(axis=1), levels=[0.5], colors="orange", linewidths=0.9, linestyles="dashed", origin=origin)
        ax.set_title(f"{pid}\n{sub.loc[pid, 'diagnosis']} · lesión {gt.sum() * ml:.0f} mL"
                     + (f" (+{borrada.sum() * ml:.0f} en zona borrada)" if borrada.any() else ""), fontsize=9)
        ax.axis("off")
        for j, corrida in enumerate(corridas, 1):
            ax = axes[i, j]
            f = Path("runs") / corrida / f"mascaras_{a.particion}" / f"{base}.npz"
            ax.imshow(mip, cmap="gray_r", vmin=0, vmax=8, origin=origin); ax.axis("off")
            if not f.exists():
                ax.set_title(f"{corrida}: sin máscara", fontsize=9); continue
            pred = np.load(f)["pred"].astype(bool)
            m = evaluate_study(pred, gt_raw, suv, ml)          # excluye la zona borrada por defecto
            pred = pred & valid
            if gt.any():
                ax.contour(gt.max(axis=1), levels=[0.5], colors="lime", linewidths=0.7, origin=origin)
            if pred.any():
                ax.contour(pred.max(axis=1), levels=[0.5], colors="red", linewidths=0.7, origin=origin)
            if groups is not None and _false_positive_mask is not None:
                fp = _false_positive_mask(pred, gt)
                if fp.any():
                    # color por órgano dominante en la proyección
                    proj = np.zeros(mip.shape, dtype=np.uint8)
                    for g in np.unique(groups[fp]):
                        proj[np.any(fp & (groups == g), axis=1)] = g
                    rgba = np.zeros(mip.shape + (4,))
                    for g in np.unique(proj):
                        if g == 0: continue
                        rgba[proj == g] = (*cmap_org(int(g) % 20)[:3], 0.55)
                    ax.imshow(rgba, origin=origin)
                    top = pd.Series({GROUP_NAMES[g]: (fp & (groups == g)).sum() * ml for g in np.unique(groups[fp])}).sort_values(ascending=False).head(3)
                    txt = "FP: " + ", ".join(f"{k} {v:.0f}" for k, v in top.items())
                else:
                    txt = "sin FP"
            else:
                txt = ""
            ax.set_title(f"{corrida}  Dice {m['dice']:.2f}\nFPV {m['fpv_ml']:.0f} mL · FNV {m['fnv_ml']:.0f} mL\n{txt}", fontsize=8)
    plt.tight_layout()
    out = Path(a.salida) if a.salida else Path("docs/figuras") / f"casos_{a.particion}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=110); plt.close()
    print("figura:", out)


if __name__ == "__main__":
    main()
