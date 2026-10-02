#!/usr/bin/env python
"""Rama `extendido`, paso 4. Evaluar un ENSAMBLE de checkpoints sobre una partición.

Cinco residentes leen el mismo estudio y se marca lesión donde el promedio de sus
probabilidades supera 0,5. Las lesiones verdaderas las ven los cinco y sobreviven; las
marcas dudosas son propias de cada uno y se diluyen. Con `--tta` cada residente además lee
la imagen y sus tres espejos laterales (aumento en inferencia), así que son 20 lecturas.

La métrica es la misma de siempre (petct.metrics.evaluate_study): Dice⁺, FPV, FNV por
componentes 26-conexas, con la zona borrada excluida (o cruda con --incluir-zona-borrada).
Con un solo checkpoint y sin --tta reproduce scripts/09 (misma red, mismo umbral).

Uso:
    python scripts/33_ensamble.py --modelo B --checkpoints runs/B_ens_0/ultimo.pt runs/B_ens_1/ultimo.pt ... \
        --particion val --manifest data/manifests/subconjunto_extendido.csv --etiqueta ensamble_B [--tta] [--guardar-mascaras]
Escribe results/<etiqueta>_<particion>.csv (y, con --guardar-mascaras, runs/ensambles/<etiqueta>/mascaras_<particion>/).
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.data import split_files  # noqa: E402
from petct.device import pick_device  # noqa: E402
from petct.infer import predict_probs  # noqa: E402
from petct.metrics import evaluate_study, summarize  # noqa: E402
from petct.models import build_model, needs_reference  # noqa: E402
from petct.preprocess import load_study  # noqa: E402
from petct.reference import stack_input  # noqa: E402
from petct.train import load_weights  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default="B")
    ap.add_argument("--checkpoints", nargs="+", required=True)
    ap.add_argument("--particion", default="val", choices=["val", "test", "oof"])
    ap.add_argument("--manifest", default="data/manifests/subconjunto_extendido.csv")
    ap.add_argument("--procesado", default="data/processed")
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--etiqueta", required=True)
    ap.add_argument("--salida", default=None)
    ap.add_argument("--tta", action="store_true", help="promediar también los tres espejos laterales")
    ap.add_argument("--umbral", type=float, default=0.5)
    ap.add_argument("--guardar-mascaras", action="store_true")
    ap.add_argument("--guardar-probabilidades", action="store_true", help="guarda el promedio (float16) para barrer umbrales después")
    ap.add_argument("--incluir-zona-borrada", action="store_true")
    ap.add_argument("--dispositivo", default=None)
    ap.add_argument("--small", action="store_true")
    a = ap.parse_args()
    if needs_reference(a.modelo):
        sys.exit("el ensamble no soporta modelos con referencia interna (E)")

    cfg = yaml.safe_load(open(a.config))
    device = pick_device(a.dispositivo)
    models, rois, smalls = [], set(), set()
    for ck in a.checkpoints:
        # tamaño de red y de parche salen del checkpoint, exactamente como en scripts/09, para que
        # un ensamble de un solo checkpoint reproduzca su evaluación individual (verificado)
        c = torch.load(ck, map_location="cpu", weights_only=False).get("config", {})
        small = bool(c.get("small", a.small)); smalls.add(small)
        rois.add(tuple(c.get("parche", cfg["preprocesamiento"]["parche"])))
        m = build_model(a.modelo, small=small).to(device)
        load_weights(m, Path(ck), device)
        m.eval(); models.append(m)
    if len(rois) > 1 or len(smalls) > 1:
        sys.exit(f"los checkpoints no son compatibles entre sí: parches {rois}, chica {smalls}")
    roi = rois.pop()
    print(f"ensamble de {len(models)} × {a.modelo}{' + TTA' if a.tta else ''} | partición {a.particion} | "
          f"parche {roi} | umbral {a.umbral} | dispositivo {device}", flush=True)

    files = split_files(a.manifest, a.procesado, a.particion)
    out = Path(a.salida) if a.salida else Path("results") / f"{a.etiqueta}_{a.particion}.csv"
    base = Path("runs/ensambles") / a.etiqueta
    masks_dir = base / f"mascaras_{a.particion}" if a.guardar_mascaras else None
    probs_dir = base / f"probabilidades_{a.particion}" if a.guardar_probabilidades else None
    for d in (masks_dir, probs_dir):
        if d is not None: d.mkdir(parents=True, exist_ok=True)

    rows, t0 = [], time.time()
    for i, f in enumerate(files):
        vol = load_study(f)
        x = torch.from_numpy(stack_input(vol["suv"], vol["ct"], vol["suv_top"], None))
        prob = np.zeros(vol["seg"].shape, dtype=np.float32)
        for m in models:
            prob += predict_probs(m, x, device, roi=roi, tta=a.tta)
        prob /= len(models)
        pred = prob > a.umbral
        suv_real = vol["suv"] * vol["suv_top"]
        ml = float(np.prod(vol["spacing"])) / 1000.0
        met = evaluate_study(pred, vol["seg"].astype(bool), suv_real, ml, exclude_blank=not a.incluir_zona_borrada)
        met["estudio"] = f.stem.split("__")[0]; met["variante"] = a.etiqueta
        rows.append(met)
        if masks_dir is not None:
            np.savez_compressed(masks_dir / f"{f.stem}.npz", pred=pred.astype(np.uint8))
        if probs_dir is not None:
            np.savez_compressed(probs_dir / f"{f.stem}.npz", prob=prob.astype(np.float16))
        print(f"[{i + 1}/{len(files)}] {met['estudio']} dice={met['dice']:.3f} fpv={met['fpv_ml']:.1f} fnv={met['fnv_ml']:.1f}"
              f"  ({(time.time() - t0) / 60:.1f} min)", flush=True)
    df = pd.DataFrame(rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    s = summarize(df)
    print(f"\n{a.etiqueta} ({a.particion}, n={len(df)}): Dice⁺ {s['dice_pos']:.3f}  mediana {s['dice_pos_mediana']:.3f}  "
          f"FPV {s['fpv_ml']:.2f} mL  FNV {s['fnv_ml_pos']:.2f} mL  → {out}")


if __name__ == "__main__":
    main()
