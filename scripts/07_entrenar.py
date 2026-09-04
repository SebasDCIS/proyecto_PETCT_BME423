#!/usr/bin/env python
"""Paso 3. Entrenar un modelo (A, y en el Paso 4 también B y C) con el mismo bucle.

Uso típico:
    # prueba de humo en el Mac (red chica, parches de 64, 200 iteraciones)
    python scripts/07_entrenar.py --modelo A --small --parche 64 --iteraciones 200 --validar-cada 100 --salida runs/humo_A

    # entrenamiento completo (Colab con GPU, o el Mac si el benchmark lo justifica)
    python scripts/07_entrenar.py --modelo A --salida runs/A

Si en `--salida` ya existe `ultimo.pt`, continúa desde ahí (pensado para Colab, cuya
sesión se corta). `--max-minutos` detiene con gracia y guarda el checkpoint.
"""
import argparse
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.data import split_files  # noqa: E402
from petct.device import describe_device, pick_device  # noqa: E402
from petct.train import TrainConfig, train  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default="A")
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--manifest", default="data/manifests/subconjunto.csv")
    ap.add_argument("--procesado", default="data/processed")
    ap.add_argument("--salida", default=None, help="carpeta de la corrida (por defecto runs/<modelo>)")
    ap.add_argument("--dispositivo", default=None, help="cuda | mps | cpu (por defecto el mejor disponible)")
    ap.add_argument("--iteraciones", type=int, default=None)
    ap.add_argument("--lote", type=int, default=None)
    ap.add_argument("--lr", type=float, default=None)
    ap.add_argument("--parche", type=int, default=None, help="lado del cubo (96 por defecto)")
    ap.add_argument("--validar-cada", type=int, default=None)
    ap.add_argument("--checkpoint-cada", type=int, default=None)
    ap.add_argument("--max-estudios-val", type=int, default=None)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--cache-estudios", type=int, default=None, help="estudios en RAM (bajar en Colab)")
    ap.add_argument("--max-minutos", type=float, default=None)
    ap.add_argument("--small", action="store_true", help="red chica (solo pruebas)")
    ap.add_argument("--sin-reanudar", action="store_true")
    a = ap.parse_args()

    cfg_yaml = yaml.safe_load(open(a.config))
    cfg = TrainConfig.from_yaml(
        cfg_yaml, modelo=a.modelo, iteraciones=a.iteraciones, lote=a.lote, lr=a.lr,
        parche=(a.parche,) * 3 if a.parche else None, validar_cada=a.validar_cada,
        checkpoint_cada=a.checkpoint_cada, max_estudios_val=a.max_estudios_val, workers=a.workers,
        cache_estudios=a.cache_estudios, max_minutos=a.max_minutos, small=a.small or None)
    device = pick_device(a.dispositivo)
    print("dispositivo:", describe_device() if a.dispositivo is None else device, flush=True)

    splits = split_files(a.manifest, a.procesado)
    out = Path(a.salida) if a.salida else Path("runs") / a.modelo
    resumen = train(cfg, splits["train"], splits.get("val", []), out, device, resume=not a.sin_reanudar)
    print("\nresumen:", {k: v for k, v in resumen.items() if k != "config"})


if __name__ == "__main__":
    main()
