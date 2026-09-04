#!/usr/bin/env python
"""Paso 3. ¿Cuánto tarda una iteración de entrenamiento en cada dispositivo?

Uso:
    python scripts/08_benchmark_dispositivo.py                 # todos los dispositivos disponibles
    python scripts/08_benchmark_dispositivo.py --dispositivos mps cpu --parche 96 --lote 2 --iteraciones 10

Mide, con datos sintéticos (no hace falta tener los .npz), segundos por iteración de
ida y vuelta (forward + backward + paso del optimizador) de la U-Net completa con el
lote y el parche del proyecto. Con eso se decide dónde correr las 25 000 iteraciones:
    horas = iteraciones × s/it / 3600
Escribe results/benchmark_dispositivo.csv (una fila por dispositivo y configuración).
"""
import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.device import pick_device  # noqa: E402
from petct.models import build_model, count_parameters  # noqa: E402
from monai.losses import DiceCELoss  # noqa: E402


def disponibles():
    out = []
    if torch.cuda.is_available():
        out.append("cuda")
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        out.append("mps")
    out.append("cpu")
    return out


def medir(dev_name: str, parche: int, lote: int, iteraciones: int, small: bool, amp: bool):
    device = pick_device(dev_name)
    torch.manual_seed(0)
    model = build_model("A", small=small).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4)
    loss_fn = DiceCELoss(softmax=True, to_onehot_y=True, include_background=False)
    use_amp = amp and device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda") if use_amp else None
    x = torch.rand(lote, 2, parche, parche, parche, device=device)
    y = (torch.rand(lote, 1, parche, parche, parche, device=device) > 0.98).long()

    def paso():
        opt.zero_grad(set_to_none=True)
        with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=use_amp):
            loss = loss_fn(model(x), y)
        if scaler:
            scaler.scale(loss).backward(); scaler.step(opt); scaler.update()
        else:
            loss.backward(); opt.step()
        return float(loss.detach())

    def sync():
        if device.type == "cuda":
            torch.cuda.synchronize()
        elif device.type == "mps":
            torch.mps.synchronize()

    for _ in range(2):        # calentamiento: la primera iteración compila kernels
        paso()
    sync()
    t = time.time()
    for _ in range(iteraciones):
        paso()
    sync()
    s_it = (time.time() - t) / iteraciones
    mem = ""
    if device.type == "cuda":
        mem = f"{torch.cuda.max_memory_allocated() / 2**30:.1f} GB"
    elif device.type == "mps":
        mem = f"{torch.mps.driver_allocated_memory() / 2**30:.1f} GB"
    return {"dispositivo": dev_name, "parche": parche, "lote": lote, "red": "chica" if small else "completa",
            "amp": use_amp, "parametros_M": round(count_parameters(model) / 1e6, 1),
            "seg_por_iter": round(s_it, 3), "horas_25000_it": round(25000 * s_it / 3600, 1), "memoria_pico": mem}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dispositivos", nargs="*", default=None)
    ap.add_argument("--parche", type=int, default=96)
    ap.add_argument("--lote", type=int, default=2)
    ap.add_argument("--iteraciones", type=int, default=10)
    ap.add_argument("--small", action="store_true")
    ap.add_argument("--sin-amp", action="store_true")
    ap.add_argument("--salida", default="results/benchmark_dispositivo.csv")
    a = ap.parse_args()
    filas = []
    for d in (a.dispositivos or disponibles()):
        print(f"midiendo en {d}...", flush=True)
        try:
            r = medir(d, a.parche, a.lote, a.iteraciones, a.small, not a.sin_amp)
        except Exception as e:  # p. ej. memoria insuficiente
            r = {"dispositivo": d, "parche": a.parche, "lote": a.lote, "error": str(e)[:120]}
        print("  ", r, flush=True)
        filas.append(r)
    df = pd.DataFrame(filas)
    out = Path(a.salida)
    out.parent.mkdir(parents=True, exist_ok=True)
    prev = pd.read_csv(out) if out.exists() else pd.DataFrame()
    pd.concat([prev, df], ignore_index=True).to_csv(out, index=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
