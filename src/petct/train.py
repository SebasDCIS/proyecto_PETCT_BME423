"""Paso 3d. El bucle de entrenamiento, escrito para sobrevivir a Colab.

Qué hace en cada iteración: saca un lote de parches (2 cubos de 96³ con sus máscaras),
los pasa por la red, compara la salida con la máscara del experto con la pérdida
Dice + entropía cruzada, calcula gradientes y da un paso del optimizador. Cada
`val_every` iteraciones predice estudios completos de validación con la ventana
deslizante y mide Dice, FPV y FNV; si el Dice mejora guarda `mejor.pt`. Cada
`checkpoint_every` iteraciones guarda `ultimo.pt` con todo lo necesario para
continuar exactamente donde iba (pesos, optimizador, escalador, iteración, mejor
valor). Si el script se relanza y existe `ultimo.pt`, continúa solo.

Decisiones, y por qué:

  Pérdida Dice + CE   Dice empuja el solapamiento global (lo que se mide), la entropía
                      cruzada da gradientes estables por vóxel al inicio, cuando la red
                      no acierta nada. Es la combinación estándar (nnU-Net la usa).
                      El Dice se calcula solo sobre el canal lesión: el fondo ya
                      "gana" siempre y no aporta.
  AdamW, lr 3e-4      Optimizador robusto por defecto; la tasa baja de forma
                      polinómica (lr · (1 − it/max)^0.9) hasta cero, como nnU-Net.
  Precisión mixta     En CUDA, float16 con escalado de gradientes: mitad de memoria y
                      casi el doble de velocidad. En MPS y CPU se desactiva (el
                      soporte no es completo y aquí no es donde se corre el
                      presupuesto). El flag `precision_mixta` del YAML solo manda en CUDA.
  Semilla             Se fijan numpy, torch y el muestreo de parches. Dos corridas con
                      la misma semilla en la misma máquina dan la misma curva (en GPU,
                      salvo diferencias de redondeo de las convoluciones no deterministas).

Todo lo que cambia entre modelos A, B y C es `build_model(nombre)`; el resto de este
archivo es idéntico para los tres, que es la condición para comparar.
"""
from __future__ import annotations

import csv
import json
import math
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import torch
from monai.losses import DiceCELoss
from torch.utils.data import DataLoader

from .data import PatchDataset
from .infer import evaluate_files, summarize
from .models import build_model, count_parameters


@dataclass
class TrainConfig:
    modelo: str = "A"
    iteraciones: int = 25_000
    lote: int = 2
    lr: float = 3e-4
    weight_decay: float = 1e-5
    precision_mixta: bool = True
    checkpoint_cada: int = 500
    validar_cada: int = 1000
    max_estudios_val: int = 12          # validación rápida durante el entrenamiento
    parche: Sequence[int] = (96, 96, 96)
    prob_parche_con_lesion: float = 0.7
    semilla: int = 423
    workers: int = 0                    # procesos de carga; con la caché en RAM basta 0 (cada worker tendría su propia caché)
    cache_estudios: int = 256
    small: bool = False                 # red chica para pruebas y humo
    max_minutos: Optional[float] = None  # parar con gracia (sesiones de Colab)
    log_cada: int = 20

    @classmethod
    def from_yaml(cls, cfg: dict, **overrides) -> "TrainConfig":
        t = cfg.get("entrenamiento", {})
        p = cfg.get("preprocesamiento", {})
        kw = dict(
            iteraciones=t.get("iteraciones", 25_000), lote=t.get("lote", 2), lr=float(t.get("lr", 3e-4)),
            precision_mixta=t.get("precision_mixta", True), checkpoint_cada=t.get("checkpoint_cada", 500),
            validar_cada=t.get("validar_cada", 1000), max_estudios_val=t.get("max_estudios_val", 12),
            parche=tuple(p.get("parche", (96, 96, 96))),
            prob_parche_con_lesion=p.get("prob_parche_con_lesion", 0.7), semilla=cfg.get("semilla", 423),
        )
        kw.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**kw)


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def poly_lr(base_lr: float, it: int, max_it: int, power: float = 0.9) -> float:
    return base_lr * (1 - min(it, max_it - 1) / max_it) ** power


def _write_row(path: Path, row: Dict, header: List[str]) -> None:
    new = not path.exists()
    with open(path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in header})


def save_checkpoint(path: Path, model, optimizer, scaler, it: int, best: float, cfg: TrainConfig) -> None:
    tmp = path.with_suffix(".tmp")
    torch.save({"model": model.state_dict(), "optimizer": optimizer.state_dict(),
                "scaler": scaler.state_dict() if scaler is not None else None,
                "iter": it, "best_dice": best, "config": asdict(cfg)}, tmp)
    tmp.replace(path)     # atómico: nunca queda un checkpoint a medio escribir


def load_weights(model: torch.nn.Module, path: Path, device: torch.device) -> dict:
    ck = torch.load(path, map_location=device, weights_only=False)
    model.load_state_dict(ck["model"])
    return ck


def train(cfg: TrainConfig, train_files: Sequence[Path], val_files: Sequence[Path],
          out_dir: str | Path, device: torch.device, resume: bool = True,
          verbose: bool = True) -> Dict:
    """Entrena `cfg.modelo` y deja en `out_dir`: ultimo.pt, mejor.pt, log_entrenamiento.csv,
    validacion.csv y resumen.json. Devuelve el resumen."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seed_everything(cfg.semilla)
    use_amp = bool(cfg.precision_mixta and device.type == "cuda")

    model = build_model(cfg.modelo, small=cfg.small).to(device)
    n_params = count_parameters(model)
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    scaler = torch.amp.GradScaler("cuda") if use_amp else None
    loss_fn = DiceCELoss(softmax=True, to_onehot_y=True, include_background=False)

    start_it, best = 0, -1.0
    last_ck = out_dir / "ultimo.pt"
    if resume and last_ck.exists():
        ck = torch.load(last_ck, map_location=device, weights_only=False)
        model.load_state_dict(ck["model"])
        optimizer.load_state_dict(ck["optimizer"])
        if scaler is not None and ck.get("scaler"):
            scaler.load_state_dict(ck["scaler"])
        start_it, best = int(ck["iter"]), float(ck.get("best_dice", -1.0))
        if verbose:
            print(f"[reanudar] desde la iteración {start_it} (mejor Dice hasta ahora {best:.3f})", flush=True)

    ds = PatchDataset(train_files, cfg.parche, cfg.prob_parche_con_lesion,
                      length=max(cfg.iteraciones * cfg.lote, 1000), cache_size=cfg.cache_estudios,
                      augment=True, seed=cfg.semilla + start_it)
    loader = DataLoader(ds, batch_size=cfg.lote, shuffle=False, num_workers=cfg.workers,
                        pin_memory=(device.type == "cuda"), persistent_workers=cfg.workers > 0,
                        drop_last=True)
    val_subset = list(val_files)[: cfg.max_estudios_val]

    if verbose:
        print(f"modelo {cfg.modelo} ({'chico' if cfg.small else 'completo'}): {n_params / 1e6:.1f} M parámetros | "
              f"{len(train_files)} estudios de entrenamiento, {len(val_subset)} de validación rápida | "
              f"dispositivo {device} | AMP {'sí' if use_amp else 'no'} | lote {cfg.lote} | parche {tuple(cfg.parche)}", flush=True)

    log_hdr = ["iter", "loss", "lr", "seg_por_iter", "minutos"]
    val_hdr = ["iter", "n", "n_pos", "dice_pos", "dice_pos_mediana", "fpv_ml", "fnv_ml_pos", "fpv_ml_neg", "mejor"]
    t0 = time.time()
    it = start_it
    model.train()
    losses: List[float] = []
    t_it = time.time()
    stopped_by_time = False
    data_iter = iter(loader)

    while it < cfg.iteraciones:
        try:
            x, y = next(data_iter)
        except StopIteration:
            data_iter = iter(loader)
            x, y = next(data_iter)
        x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
        lr = poly_lr(cfg.lr, it, cfg.iteraciones)
        for g in optimizer.param_groups:
            g["lr"] = lr
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=use_amp):
            logits = model(x)
            loss = loss_fn(logits, y)
        if scaler is not None:
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 12.0)
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 12.0)
            optimizer.step()
        it += 1
        losses.append(float(loss.detach()))

        if it % cfg.log_cada == 0 or it == cfg.iteraciones:
            dt = (time.time() - t_it) / cfg.log_cada
            t_it = time.time()
            row = {"iter": it, "loss": float(np.mean(losses[-cfg.log_cada:])), "lr": lr,
                   "seg_por_iter": dt, "minutos": (time.time() - t0) / 60}
            _write_row(out_dir / "log_entrenamiento.csv", row, log_hdr)
            if verbose:
                print(f"it {it:6d}  loss {row['loss']:.4f}  lr {lr:.2e}  {dt:.2f} s/it", flush=True)

        if val_subset and (it % cfg.validar_cada == 0 or it == cfg.iteraciones):
            df = evaluate_files(model, val_subset, device, roi=cfg.parche, amp=use_amp, variante=cfg.modelo)
            s = summarize(df)
            improved = not math.isnan(s["dice_pos"]) and s["dice_pos"] > best
            if improved:
                best = s["dice_pos"]
                save_checkpoint(out_dir / "mejor.pt", model, optimizer, scaler, it, best, cfg)
            _write_row(out_dir / "validacion.csv", {**s, "iter": it, "mejor": int(improved)}, val_hdr)
            if verbose:
                print(f"  [val it {it}] Dice(pos) {s['dice_pos']:.3f}  FPV {s['fpv_ml']:.0f} mL  FNV {s['fnv_ml_pos']:.1f} mL"
                      + ("  ← mejor" if improved else ""), flush=True)
            model.train()

        if it % cfg.checkpoint_cada == 0 or it == cfg.iteraciones:
            save_checkpoint(last_ck, model, optimizer, scaler, it, best, cfg)

        if cfg.max_minutos is not None and (time.time() - t0) / 60 > cfg.max_minutos:
            save_checkpoint(last_ck, model, optimizer, scaler, it, best, cfg)
            stopped_by_time = True
            if verbose:
                print(f"[tiempo] se alcanzó el límite de {cfg.max_minutos} min en la iteración {it}; checkpoint guardado", flush=True)
            break

    resumen = {"modelo": cfg.modelo, "parametros": n_params, "iteraciones_hechas": it,
               "iteraciones_objetivo": cfg.iteraciones, "mejor_dice_val": best,
               "loss_final": float(np.mean(losses[-50:])) if losses else float("nan"),
               "minutos": (time.time() - t0) / 60, "dispositivo": str(device), "amp": use_amp,
               "detenido_por_tiempo": stopped_by_time, "config": asdict(cfg)}
    with open(out_dir / "resumen.json", "w") as fh:
        json.dump(resumen, fh, indent=2, default=str)
    return resumen
