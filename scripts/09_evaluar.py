#!/usr/bin/env python
"""Paso 3/5. Evaluar un checkpoint sobre una partición completa con ventana deslizante.

Uso:
    python scripts/09_evaluar.py --modelo A --checkpoint runs/A/mejor.pt --particion val
    python scripts/09_evaluar.py --modelo A --checkpoint runs/A/mejor.pt --particion test --guardar-mascaras

Escribe results/modelo_<modelo>_<particion>.csv con las mismas columnas que
results/referencia_clasica.csv, para comparar lado a lado. La partición `test` se
evalúa UNA vez, al final, con el checkpoint elegido en validación.
"""
import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.data import split_files  # noqa: E402
from petct.device import pick_device  # noqa: E402
from petct.infer import evaluate_files, summarize  # noqa: E402
from petct.models import build_model  # noqa: E402
from petct.train import load_weights  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default="A")
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--particion", default="val", choices=["train", "val", "test"])
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--manifest", default="data/manifests/subconjunto.csv")
    ap.add_argument("--procesado", default="data/processed")
    ap.add_argument("--dispositivo", default=None)
    ap.add_argument("--limite", type=int, default=0, help="solo los primeros N estudios (pruebas)")
    ap.add_argument("--guardar-mascaras", action="store_true")
    ap.add_argument("--etiqueta", default=None, help="nombre de la corrida en la tabla (por defecto modelo_<M>; para semillas: modelo_A_s2)")
    ap.add_argument("--salida", default=None)
    a = ap.parse_args()

    cfg = yaml.safe_load(open(a.config))
    device = pick_device(a.dispositivo)
    ck_path = Path(a.checkpoint)
    import torch
    ck = torch.load(ck_path, map_location="cpu", weights_only=False)
    small = bool(ck.get("config", {}).get("small", False))
    roi = tuple(ck.get("config", {}).get("parche", cfg["preprocesamiento"]["parche"]))
    model = build_model(a.modelo, small=small).to(device)
    load_weights(model, ck_path, device)
    print(f"checkpoint de la iteración {ck.get('iter')} (Dice val {ck.get('best_dice', float('nan')):.3f}); "
          f"red {'chica' if small else 'completa'}; parche {roi}; dispositivo {device}", flush=True)

    files = split_files(a.manifest, a.procesado, a.particion)
    if a.limite:
        files = files[: a.limite]
    etiqueta = a.etiqueta or f"modelo_{a.modelo}"
    out = Path(a.salida) if a.salida else Path("results") / f"{etiqueta}_{a.particion}.csv"
    masks = ck_path.parent / f"mascaras_{a.particion}" if a.guardar_mascaras else None
    df = evaluate_files(model, files, device, roi=roi, amp=(device.type == "cuda"),
                        variante=etiqueta, save_masks_dir=masks, verbose=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print("\nresumen:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in summarize(df).items()})
    print("tabla en", out)


if __name__ == "__main__":
    main()
