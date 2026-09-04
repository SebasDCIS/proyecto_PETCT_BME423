"""Paso 3c. Inferencia sobre estudios completos con ventana deslizante, y evaluación.

La red se entrenó con cubos de 96³, así que no puede tragarse un estudio de
316 × 126 × 147 de una vez (ni cabría en memoria). La ventana deslizante recorre el
volumen con cubos solapados (50 %), predice cada uno y promedia las predicciones en
las zonas de solape con un peso gaussiano (más confianza al centro del cubo que a sus
bordes, donde la red tiene menos contexto). Es exactamente `sliding_window_inference`
de MONAI; la misma función se usa para validar durante el entrenamiento y para la
prueba final, así los números son comparables.

`evaluate_files` devuelve una tabla con las mismas columnas que la referencia clásica
(`results/referencia_clasica.csv`), para poder ponerlas lado a lado.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
import torch
from monai.inferers import sliding_window_inference

from .metrics import evaluate_study
from .preprocess import load_study


@torch.no_grad()
def predict_volume(model: torch.nn.Module, x: torch.Tensor, device: torch.device,
                   roi=(96, 96, 96), overlap: float = 0.5, sw_batch_size: int = 2,
                   amp: bool = False) -> np.ndarray:
    """x: (2, D, H, W) float32 en CPU. Devuelve máscara binaria (D, H, W) uint8."""
    model.eval()
    xb = x[None].to(device)
    with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=amp and device.type == "cuda"):
        logits = sliding_window_inference(xb, roi_size=tuple(roi), sw_batch_size=sw_batch_size,
                                          predictor=model, overlap=overlap, mode="gaussian")
    mask = logits.argmax(dim=1)[0].to("cpu").numpy().astype(np.uint8)
    return mask


def evaluate_files(model: torch.nn.Module, files: Sequence[Path], device: torch.device,
                   roi=(96, 96, 96), overlap: float = 0.5, amp: bool = False,
                   variante: str = "modelo", save_masks_dir: Optional[Path] = None,
                   verbose: bool = False) -> pd.DataFrame:
    """Predice y mide cada estudio; una fila por estudio, columnas como la referencia clásica."""
    rows: List[Dict] = []
    for i, f in enumerate(files):
        f = Path(f)
        vol = load_study(f)
        x = torch.from_numpy(np.stack([vol["suv"], vol["ct"]]).astype(np.float32))
        pred = predict_volume(model, x, device, roi, overlap, amp=amp)
        suv_real = vol["suv"] * vol["suv_top"]
        ml = float(np.prod(vol["spacing"])) / 1000.0
        m = evaluate_study(pred.astype(bool), vol["seg"].astype(bool), suv_real, ml)
        m["estudio"] = f.stem.split("__")[0]
        m["variante"] = variante
        rows.append(m)
        if save_masks_dir is not None:
            save_masks_dir.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(save_masks_dir / f"{f.stem}.npz", pred=pred)
        if verbose:
            print(f"[{i + 1}/{len(files)}] {m['estudio']} dice={m['dice']:.3f} fpv={m['fpv_ml']:.0f} fnv={m['fnv_ml']:.1f}", flush=True)
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame) -> Dict[str, float]:
    """Resumen como en el reto: Dice solo en positivos; FPV en todos; FNV en positivos."""
    pos = df[df.mtv_gt_ml > 0]
    neg = df[df.mtv_gt_ml == 0]
    return {
        "n": int(len(df)), "n_pos": int(len(pos)),
        "dice_pos": float(pos.dice.mean()) if len(pos) else float("nan"),
        "dice_pos_mediana": float(pos.dice.median()) if len(pos) else float("nan"),
        "fpv_ml": float(df.fpv_ml.mean()),
        "fnv_ml_pos": float(pos.fnv_ml.mean()) if len(pos) else float("nan"),
        "fpv_ml_neg": float(neg.fpv_ml.mean()) if len(neg) else float("nan"),
    }
