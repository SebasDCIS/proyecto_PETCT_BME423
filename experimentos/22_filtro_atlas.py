#!/usr/bin/env python
"""EXPERIMENTO de la rama `extendido`. Fuera del protocolo congelado de `main`.

Idea B: usar el atlas de normalidad como juez en vez de como entrada.

El modelo E le dio a la red la referencia del propio paciente y confió en que aprendiera
a usarla. Con 176 estudios no la aprendió: el canal cambia la predicción pero su efecto
es de 1,4 mL. Este script aplica el mismo conocimiento por otra puerta, la que no
necesita entrenamiento: toma las máscaras que un modelo ya predijo, mira isla por isla
en qué órgano cayó, y descarta las que no superan lo que ese órgano capta normalmente.

Es exactamente lo que hace un médico nuclear al leer: "eso brilla, pero es un riñón y
los riñones brillan". La regla se aplica siempre, no depende de que la red la aprenda.

Dos criterios, y se barre el factor k de los dos:
    absoluto  la isla sobrevive si SUVmáx >= k · p95(órgano) del atlas poblacional
    relativo  la isla sobrevive si SUVmáx/hígado_del_paciente >= k · rel_p95(órgano)

No necesita GPU ni vuelve a inferir: opera sobre `runs/<corrida>/mascaras_<particion>/`,
que ya existen. Correrlo mientras entrena otra cosa no molesta.

Uso:
    python scripts/09_evaluar.py --modelo A --checkpoint runs/A/mejor.pt --guardar-mascaras ...
    python scripts/22_filtro_atlas.py --corrida A
    python scripts/22_filtro_atlas.py --corrida A --criterio relativo
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.metrics import evaluate_study, summarize  # noqa: E402
from petct.organs import GROUP_NAMES, internal_reference  # noqa: E402

CONN = np.ones((3, 3, 3), dtype=int)
FACTORES = [0.0, 0.5, 0.7, 0.85, 1.0, 1.15, 1.3, 1.5, 2.0]     # 0.0 = sin filtro (control)
VOL_MIN_ML = 0.0        # el filtro por volumen mínimo se explora aparte, con --volumen-min


def organo_dominante(groups, isla):
    """El grupo de órganos que ocupa más vóxeles de la isla."""
    vals = groups[isla]
    if vals.size == 0:
        return "otro"
    codigo = int(np.bincount(vals).argmax())
    return GROUP_NAMES[codigo] if codigo < len(GROUP_NAMES) else "otro"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corrida", required=True, help="nombre de la carpeta en runs/, p. ej. A o E")
    ap.add_argument("--particion", default="val", choices=["train", "val"])
    ap.add_argument("--criterio", default="absoluto", choices=["absoluto", "relativo"])
    ap.add_argument("--atlas", default="controles", choices=["controles", "train"])
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--manifest", default="data/manifests/subconjunto.csv")
    ap.add_argument("--procesado", default="data/processed")
    ap.add_argument("--organos", default="data/processed_organos")
    ap.add_argument("--volumen-min", type=float, default=VOL_MIN_ML,
                    help="además, descartar islas menores que este volumen en mL")
    a = ap.parse_args()

    atlas = pd.read_csv(f"results/atlas_normalidad_{a.atlas}.csv").set_index("organo")
    columna = "p95" if a.criterio == "absoluto" else "rel_p95"
    if columna not in atlas.columns:
        sys.exit(f"El atlas no trae la columna {columna}; vuelve a correr scripts/17_atlas_normalidad.py")
    techo = atlas[columna].to_dict()

    sub = pd.read_csv(a.manifest)
    estudios = sub[sub.split == a.particion]
    mdir = Path(a.runs) / a.corrida / f"mascaras_{a.particion}"
    if not mdir.exists():
        sys.exit(f"No existe {mdir}. Genera las máscaras con 09_evaluar.py --guardar-mascaras")

    filas, descartes = [], []
    for r in estudios.itertuples():
        base = f"{r.patient_id}__{r.study_uid}"
        f_pred = mdir / f"{base}.npz"
        f_org = Path(a.organos) / f"{base}.npz"
        if not (f_pred.exists() and f_org.exists()):
            continue
        d = np.load(Path(a.procesado) / f"{base}.npz")
        suv = d["suv"].astype(np.float32) * float(d["suv_top"])
        gt = d["seg"].astype(bool)
        body = d["body"].astype(bool)
        ml = float(np.prod(d["spacing"].astype(float)) / 1000.0)
        groups = np.load(f_org)["groups"].astype(np.uint8)
        visible = suv > 0.0
        pred0 = np.load(f_pred)["pred"].astype(bool) & visible

        ref_pac, _ = internal_reference(suv, groups, body & visible)
        etiquetas, n = ndimage.label(pred0, structure=CONN)
        islas = []
        for sl, lab in zip(ndimage.find_objects(etiquetas), range(1, n + 1)):
            m = etiquetas[sl] == lab
            smax = float(suv[sl][m].max())
            org = organo_dominante(groups[sl], m)
            toca_gt = bool(gt[sl][m].any())
            islas.append({"lab": lab, "suvmax": smax, "organo": org, "falsa": not toca_gt,
                          "vol_ml": float(m.sum()) * ml,
                          "veces_higado": smax / ref_pac if ref_pac and np.isfinite(ref_pac) else np.nan})

        for k in FACTORES:
            keep = np.zeros(n + 1, dtype=bool)
            for it in islas:
                lim = techo.get(it["organo"], np.nan)
                valor = it["suvmax"] if a.criterio == "absoluto" else it["veces_higado"]
                sobrevive = True
                if k > 0 and np.isfinite(lim) and np.isfinite(valor):
                    sobrevive = valor >= k * lim
                if a.volumen_min > 0 and it["vol_ml"] < a.volumen_min:
                    sobrevive = False
                keep[it["lab"]] = sobrevive
            pred = keep[etiquetas]
            m = evaluate_study(pred, gt, suv, ml, exclude_blank=True)
            m.update({"estudio": r.patient_id, "variante": f"{a.corrida}_k{k:g}", "k": k,
                      "islas_antes": n, "islas_despues": int(keep.sum())})
            filas.append(m)
            if k == 1.0:
                for it in islas:
                    descartes.append({"estudio": r.patient_id, "organo": it["organo"],
                                      "suvmax": it["suvmax"], "vol_ml": it["vol_ml"],
                                      "veces_higado": it["veces_higado"], "falsa": it["falsa"],
                                      "sobrevive": bool(keep[it["lab"]])})

    if not filas:
        sys.exit("No se encontró ninguna máscara + mapa de órganos para esta partición.")
    df = pd.DataFrame(filas)
    suf = f"{a.corrida}_{a.criterio}"
    out = Path("experimentos/resultados") / f"filtro_atlas_{suf}_{a.particion}.csv"
    df.to_csv(out, index=False)
    pd.DataFrame(descartes).to_csv(Path("experimentos/resultados") / f"filtro_atlas_{suf}_islas_{a.particion}.csv", index=False)

    print(f"criterio {a.criterio} · atlas {a.atlas} · corrida {a.corrida}\n")
    print("   k    Dice+    FPV mL   FNV mL   islas antes -> después")
    for k, g in df.groupby("k"):
        s = summarize(g)
        print(f"{k:>4.2f}   {s['dice_pos']:6.3f}  {s['fpv_ml']:8.2f}  {s['fnv_ml_pos']:7.2f}   "
              f"{g.islas_antes.sum():5d} -> {g.islas_despues.sum():<5d}")
    print("\nk = 0 es el control sin filtro: debe reproducir exactamente la tabla original.")
    print("tabla en", out)


if __name__ == "__main__":
    main()
