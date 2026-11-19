#!/usr/bin/env python
"""EXPERIMENTO de la rama `extendido`. Fuera del protocolo congelado de `main`.

Idea A: convertir el punto de operación en una curva.

Hoy la decisión de cada vóxel se toma con `argmax` sobre los dos logits, que es un umbral
de 0,5 que nadie eligió. Este script hace una sola pasada de inferencia por estudio,
guarda la probabilidad de la clase "lesión" y mide las métricas del reto para muchos
umbrales a la vez. Con eso se puede:

  · reportar cada arquitectura en su mejor punto y no en uno arbitrario;
  · comparar arquitecturas a FPV igualado ("a 10 mL de falso positivo por estudio,
    ¿cuál encuentra más lesión?"), que es la comparación que un clínico entiende;
  · dibujar la curva FROC del paso 7 sin volver a inferir.

No modifica nada del pipeline: importa lo mismo que 09_evaluar.py y escribe su propia
tabla. Correrlo no cambia ningún resultado ya publicado.

Uso:
    python scripts/21_barrido_umbral.py --modelo A --checkpoint runs/A/mejor.pt --etiqueta A
    python scripts/21_barrido_umbral.py --modelo E --checkpoint runs/E/ultimo.pt --etiqueta E_ultimo
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml
from monai.inferers import sliding_window_inference
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.data import split_files  # noqa: E402
from petct.device import pick_device  # noqa: E402
from petct.metrics import evaluate_study  # noqa: E402
from petct.models import build_model, needs_reference  # noqa: E402
from petct.preprocess import load_study  # noqa: E402
from petct.reference import load_reference_table, reference_for, stack_input  # noqa: E402
from petct.train import load_weights  # noqa: E402

CONN = np.ones((3, 3, 3), dtype=int)          # 26-conexas, igual que el reto
UMBRALES = [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95]


@torch.no_grad()
def probabilidad_lesion(model, x, device, roi, overlap=0.5, sw_batch_size=2):
    """Igual que predict_volume, pero devuelve la probabilidad en vez del argmax."""
    model.eval()
    logits = sliding_window_inference(x[None].to(device), roi_size=tuple(roi),
                                      sw_batch_size=sw_batch_size, predictor=model,
                                      overlap=overlap, mode="gaussian")
    return torch.softmax(logits, dim=1)[0, 1].to("cpu").numpy().astype(np.float32)


def deteccion_por_lesion(pred, gt):
    """Cuenta, con la definición del reto: cuántas lesiones anotadas toca la predicción
    (aunque sea por un vóxel) y cuántas islas predichas no tocan ninguna."""
    lg, n_gt = ndimage.label(gt, structure=CONN)
    lp, n_pred = ndimage.label(pred, structure=CONN)
    if n_gt:
        tocadas = len(set(np.unique(lg[pred & gt])) - {0})
    else:
        tocadas = 0
    if n_pred:
        falsas = n_pred - len(set(np.unique(lp[pred & gt])) - {0})
    else:
        falsas = 0
    return n_gt, tocadas, n_pred, falsas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default="A")
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--particion", default="val", choices=["train", "val"])
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--manifest", default="data/manifests/subconjunto.csv")
    ap.add_argument("--procesado", default="data/processed")
    ap.add_argument("--referencias", default="data/manifests/referencias_internas.csv")
    ap.add_argument("--etiqueta", required=True)
    ap.add_argument("--dispositivo", default=None)
    ap.add_argument("--limite", type=int, default=0)
    a = ap.parse_args()

    if a.particion == "test":
        sys.exit("El conjunto de prueba no se abre desde un script de exploración.")

    cfg = yaml.safe_load(open(a.config))
    device = pick_device(a.dispositivo)
    ck = torch.load(a.checkpoint, map_location="cpu", weights_only=False)
    small = bool(ck.get("config", {}).get("small", False))
    roi = tuple(ck.get("config", {}).get("parche", cfg["preprocesamiento"]["parche"]))
    model = build_model(a.modelo, small=small).to(device)
    load_weights(model, Path(a.checkpoint), device)
    refs = load_reference_table(a.referencias) if needs_reference(a.modelo) else None
    print(f"checkpoint de la iteración {ck.get('iter')}; {len(UMBRALES)} umbrales; "
          f"dispositivo {device}", flush=True)

    files = split_files(a.manifest, a.procesado, a.particion)
    if a.limite:
        files = files[: a.limite]

    filas = []
    for i, f in enumerate(files):
        f = Path(f)
        vol = load_study(f)
        ref = None if refs is None else reference_for(refs, f.stem)
        x = torch.from_numpy(stack_input(vol["suv"], vol["ct"], vol["suv_top"], ref))
        prob = probabilidad_lesion(model, x, device, roi)          # una sola inferencia
        suv_real = vol["suv"] * vol["suv_top"]
        gt = vol["seg"].astype(bool)
        ml = float(np.prod(vol["spacing"])) / 1000.0
        visible = suv_real > 0.0
        for u in UMBRALES:
            pred = (prob >= u) & visible
            m = evaluate_study(pred, gt, suv_real, ml, exclude_blank=True)
            n_gt, tocadas, n_pred, falsas = deteccion_por_lesion(pred, gt & visible)
            m.update({"estudio": f.stem.split("__")[0], "variante": a.etiqueta, "umbral": u,
                      "lesiones_gt": n_gt, "lesiones_detectadas": tocadas,
                      "islas_pred": n_pred, "islas_falsas": falsas})
            filas.append(m)
        print(f"[{i + 1}/{len(files)}] {f.stem.split('__')[0]}", flush=True)

    df = pd.DataFrame(filas)
    out = Path("experimentos/resultados") / f"barrido_umbral_{a.etiqueta}_{a.particion}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)

    print("\numbral   Dice+   FPV mL   FNV mL   sensibilidad   islas falsas/estudio")
    for u, g in df.groupby("umbral"):
        pos = g[g.mtv_gt_ml > 0]
        sens = g.lesiones_detectadas.sum() / max(1, g.lesiones_gt.sum())
        print(f"{u:>6.2f}  {pos.dice.mean():6.3f}  {g.fpv_ml.mean():7.2f}  "
              f"{pos.fnv_ml.mean():7.2f}   {sens:11.3f}   {g.islas_falsas.mean():8.1f}")
    print("\ntabla en", out)


if __name__ == "__main__":
    main()
