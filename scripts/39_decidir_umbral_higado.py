#!/usr/bin/env python
"""Rama `extendido`, paso 5. Decidir el umbral y la regla del hígado con los 825 estudios fuera de
pliegue, con una regla de decisión fijada en docs/TEST_PREREGISTRO.md ANTES de ver los números.

Fuente: las probabilidades que dejó scripts/38 (cada estudio de entrenamiento predicho, con TTA,
por el único miembro del ensamble que no lo vio). Es un sustituto del ensamble: en un estudio de
entrenamiento solo un miembro es "ciego", así que no se puede promediar a los cinco.

Para cada umbral de la grilla, con y sin la regla del doble del hígado, mide Dice⁺, FPV, FNV,
lesiones detectadas y marcas falsas por estudio. Después aplica la regla de decisión (ver
`decidir`) y escribe results/<particion>_umbral/decision.json, que scripts/35 lee para el test.

    python scripts/39_decidir_umbral_higado.py --particion oof                     # la decisión
    python scripts/39_decidir_umbral_higado.py --particion val \
        --probabilidades runs/ensambles/ensamble_B_ens_tta/probabilidades_val    # comprobación, no decide
No necesita torch.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.metrics import evaluate_study, summarize  # noqa: E402
from petct.postproc import referencia_higado, regla_higado  # noqa: E402
from petct.preprocess import load_study  # noqa: E402

GRILLA = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
K_HIGADO = 2.0
CONN = np.ones((3, 3, 3), dtype=int)
# regla de decisión (docs/TEST_PREREGISTRO.md, sección "Umbral y regla del hígado")
MAX_PERDIDA_SENS = 0.02      # el umbral elegido no puede detectar más de 2 puntos menos de lesiones que 0,5
MIN_BAJA_MARCAS = 0.25       # la regla del hígado se adopta si baja ≥ 25 % las marcas falsas por estudio...
MAX_PERDIDA_LES = 0.03       # ...perdiendo ≤ 3 % (relativo) de las lesiones detectadas...
MAX_PERDIDA_DICE = 0.005     # ...y sin bajar el Dice⁺ más de 0,005


def estudios(particion, probs):
    if particion == "oof":
        for k in range(5):
            m = pd.read_csv(f"data/manifests/_pliegues/pliegue_{k}.csv"); m = m[m.split == "oof"]
            d = Path(f"runs/ensambles/oof_B_ens_{k}/probabilidades_oof")
            for r in m.itertuples():
                yield f"{r.patient_id}__{r.study_uid}.npz", d
    else:
        m = pd.read_csv("data/manifests/subconjunto_extendido.csv"); m = m[m.split == particion]
        for r in m.itertuples():
            yield f"{r.patient_id}__{r.study_uid}.npz", Path(probs)


def lesiones_y_marcas(pred, seg, valid):
    lab, n = ndimage.label(seg & valid, CONN)
    pv = pred & valid
    det = len(set(np.unique(lab[pv & (lab > 0)]).tolist()) - {0})
    pl, pn = ndimage.label(pv, CONN)
    toca = np.asarray(ndimage.maximum(seg.astype(np.uint8), pl, np.arange(1, pn + 1))) if pn else np.array([])
    return det, n, int((toca == 0).sum())


def decidir(t):
    base = t[(t.u == 0.5) & (~t.higado)].iloc[0]
    sin = t[~t.higado].copy()
    ok = sin[sin.sens >= base.sens - MAX_PERDIDA_SENS]
    best = ok.sort_values(["dice", "u"], ascending=[False, False]).iloc[0]       # empate → umbral más alto
    u = float(best.u)
    con = t[(t.u == u) & (t.higado)].iloc[0]
    baja_marcas = 1 - con.marcas / best.marcas if best.marcas > 0 else 0.0
    perdida_les = 1 - con.detectadas / best.detectadas if best.detectadas > 0 else 0.0
    adopta = bool(baja_marcas >= MIN_BAJA_MARCAS and perdida_les <= MAX_PERDIDA_LES and best.dice - con.dice <= MAX_PERDIDA_DICE)
    return dict(umbral=u, regla_higado=adopta, k_higado=K_HIGADO,
                motivo=dict(sens_u05=round(float(base.sens), 4), sens_u=round(float(best.sens), 4), dice_u=round(float(best.dice), 4),
                            dice_u05=round(float(base.dice), 4), baja_marcas_higado=round(float(baja_marcas), 4),
                            perdida_lesiones_higado=round(float(perdida_les), 4), dice_con_higado=round(float(con.dice), 4)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--particion", default="oof", choices=["oof", "val"])
    ap.add_argument("--probabilidades", default=None, help="solo con --particion val")
    ap.add_argument("--limite", type=int, default=0, help="solo para pruebas")
    a = ap.parse_args()
    out = Path("results") / f"{a.particion}_umbral"; out.mkdir(parents=True, exist_ok=True)

    filas = {(u, h): [] for u in GRILLA for h in (False, True)}
    cont = {(u, h): [0, 0, 0] for u in GRILLA for h in (False, True)}           # detectadas, total, marcas
    lista = list(estudios(a.particion, a.probabilidades))
    if a.limite:
        lista = lista[: a.limite]
    faltan = [n for n, d in lista if not (d / n).exists()]
    if faltan:
        sys.exit(f"faltan {len(faltan)} probabilidades (p. ej. {faltan[0]}); corre antes scripts/38")
    for i, (nombre, d) in enumerate(lista, 1):
        v = load_study(Path("data/processed") / nombre)
        suv = v["suv"] * v["suv_top"]; seg = v["seg"].astype(bool); valid = suv > 0
        ml = float(np.prod(v["spacing"])) / 1000.0
        groups = np.load(Path("data/processed_organos") / nombre)["groups"]
        ref = referencia_higado(suv, groups, v["body"])
        prob = np.load(d / nombre)["prob"].astype(np.float32)
        for u in GRILLA:
            p0 = prob > u
            for h in (False, True):
                p = regla_higado(p0, suv, ref, K_HIGADO) if h else p0
                m = evaluate_study(p, seg, suv, ml, exclude_blank=True)
                filas[(u, h)].append(m)
                det, tot, mar = lesiones_y_marcas(p, seg, valid)
                c = cont[(u, h)]; c[0] += det; c[1] += tot; c[2] += mar
        if i % 50 == 0:
            print(f"[{i}/{len(lista)}]", flush=True)
    rows = []
    for (u, h), ms in filas.items():
        s = summarize(pd.DataFrame(ms)); det, tot, mar = cont[(u, h)]
        rows.append(dict(u=u, higado=h, n=s["n"], dice=s["dice_pos"], dice_med=s["dice_pos_mediana"], fpv=s["fpv_ml"],
                         fnv=s["fnv_ml_pos"], detectadas=det, lesiones=tot, sens=det / tot if tot else np.nan, marcas=mar / len(lista)))
    t = pd.DataFrame(rows).sort_values(["higado", "u"])
    t.to_csv(out / "barrido.csv", index=False)
    print(t.round(3).to_string(index=False))
    if a.particion == "oof" and not a.limite:
        dec = decidir(t)
        json.dump(dec, open(out / "decision.json", "w"), indent=2)
        print("\nDECISIÓN:", json.dumps(dec, ensure_ascii=False))
    elif a.particion == "val":
        print("\n(validación: solo comprobación; la decisión sale de los 825 fuera de pliegue)", decidir(t))


if __name__ == "__main__":
    main()
