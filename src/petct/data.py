"""Paso 3a. De los `.npz` preprocesados a parches que PyTorch pueda comer.

Tres piezas:

  split_files    cruza `subconjunto.csv` (quién está en train/val/test) con los `.npz`
                 que existen en `data/processed`, y devuelve la lista de archivos de
                 cada partición. La partición es por paciente y viene del sorteo con
                 semilla; aquí no se decide nada, solo se lee.

  PatchDataset   un Dataset de PyTorch que, cada vez que se le pide un elemento, elige
                 un estudio, recorta un cubo de 96³ (sesgado a lesiones, como en
                 `sample_patch`) y lo entrega como tensores: entrada de 2 canales
                 (SUV escalado, CT ventaneado) y etiqueta de 1 canal (0 fondo, 1 lesión).
                 Es "infinito": no recorre los estudios en orden, los muestrea. Eso
                 encaja con entrenar por iteraciones (25 000) en vez de por épocas.

  VolumeDataset  entrega estudios completos, uno a uno, para validar y probar con la
                 ventana deslizante. Sin parches ni aumentos.

Sobre la memoria. Un estudio a 3 mm ocupa unos 35 MB descomprimido (float16). Con
251 estudios serían ~9 GB: cabe en el Mac (24 GB) pero no en Colab gratuito. Por eso el
dataset guarda en RAM como máximo `cache_size` estudios (LRU: cuando entra uno nuevo
sale el que lleva más tiempo sin usarse); con 251 en el Mac se cachea todo, en Colab
se baja a 40 o 50 y el resto se lee del disco (~0,3 s por estudio).

Aumentos de datos: solo volteos aleatorios en los ejes laterales (izquierda-derecha y
adelante-atrás). No volteo en z porque la anatomía superior-inferior sí es informativa
(la vejiga está abajo, el corazón arriba) y quiero que la red pueda usarla. Es
deliberadamente poco: el proyecto compara arquitecturas, no recetas de aumento, y el
mismo aumento se aplica a los tres modelos.
"""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

from .preprocess import load_study, sample_patch


# ---------------------------------------------------------------- particiones
def split_files(manifest_csv: str | Path, processed_dir: str | Path,
                split: Optional[str] = None) -> Dict[str, List[Path]]:
    """Archivos .npz por partición. Si `split` se indica, devuelve solo esa lista.

    Solo entran los estudios del sorteo (`subconjunto.csv`) que además tienen su .npz;
    si falta alguno se avisa, porque una partición incompleta cambia los resultados.
    """
    sub = pd.read_csv(manifest_csv)
    processed_dir = Path(processed_dir)
    out: Dict[str, List[Path]] = {}
    faltan = []
    for _, r in sub.iterrows():
        f = processed_dir / f"{r.patient_id}__{r.study_uid}.npz"
        if f.exists():
            out.setdefault(r.split, []).append(f)
        else:
            faltan.append(r.patient_id)
    if faltan:
        print(f"[split_files] {len(faltan)} estudios del sorteo sin .npz (se omiten): {faltan[:5]}...")
    for k in out:
        out[k] = sorted(out[k])
    return out[split] if split else out


# ---------------------------------------------------------------- caché LRU
class _StudyCache:
    """Guarda hasta `max_items` estudios en RAM; el menos usado sale primero."""

    def __init__(self, max_items: int):
        self.max_items = max(1, int(max_items))
        self._d: "OrderedDict[Path, dict]" = OrderedDict()

    def get(self, f: Path) -> dict:
        if f in self._d:
            self._d.move_to_end(f)
            return self._d[f]
        vol = load_study(f)
        # float16 en caché (la mitad de memoria); se pasa a float32 al armar el parche
        vol = {"suv": vol["suv"].astype(np.float16), "ct": vol["ct"].astype(np.float16),
               "seg": vol["seg"], "body": vol["body"], "suv_top": vol["suv_top"],
               "spacing": vol["spacing"], "head_at_end": vol["head_at_end"]}
        self._d[f] = vol
        if len(self._d) > self.max_items:
            self._d.popitem(last=False)
        return vol


# ---------------------------------------------------------------- parches
class PatchDataset(Dataset):
    """Parches 3D muestreados al azar de una lista de estudios.

    `length` es cuántos parches "tiene" el dataset por época; como el muestreo es
    aleatorio, el número solo define cuánto dura una época para el DataLoader. Con
    entrenamiento por iteraciones basta con que sea grande.
    """

    def __init__(self, files: Sequence[Path], patch_size=(96, 96, 96), p_lesion: float = 0.7,
                 length: int = 10_000, cache_size: int = 256, augment: bool = True,
                 seed: Optional[int] = None):
        if not files:
            raise ValueError("PatchDataset sin archivos")
        self.files = [Path(f) for f in files]
        self.patch_size = tuple(int(s) for s in patch_size)
        self.p_lesion = float(p_lesion)
        self.length = int(length)
        self.augment = augment
        self.cache = _StudyCache(cache_size)
        self._seed = seed
        self._rng = np.random.default_rng(seed)

    def __len__(self) -> int:
        return self.length

    def _rng_for_worker(self) -> np.random.Generator:
        # Cada proceso del DataLoader necesita su propia semilla, o todos sacan los
        # mismos parches. torch.utils.data.get_worker_info() lo resuelve.
        info = torch.utils.data.get_worker_info()
        if info is None:
            return self._rng
        if not hasattr(self, "_worker_rng"):
            base = self._seed if self._seed is not None else 0
            self._worker_rng = np.random.default_rng(base + 1000 * (info.id + 1) + int(info.seed) % 1000)
        return self._worker_rng

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        rng = self._rng_for_worker()
        f = self.files[rng.integers(len(self.files))]
        vol = self.cache.get(f)
        p = sample_patch(vol, self.patch_size, self.p_lesion, rng)
        x = np.stack([p["suv"].astype(np.float32), p["ct"].astype(np.float32)])   # (2, D, H, W)
        y = p["seg"].astype(np.int64)[None]                                       # (1, D, H, W)
        if self.augment:
            for ax in (2, 3):          # ejes H (y) y W (x); z (eje 1) no se voltea
                if rng.random() < 0.5:
                    x = np.flip(x, axis=ax)
                    y = np.flip(y, axis=ax)
            x, y = np.ascontiguousarray(x), np.ascontiguousarray(y)
        return torch.from_numpy(x), torch.from_numpy(y)


# ---------------------------------------------------------------- volúmenes completos
class VolumeDataset(Dataset):
    """Estudios completos para validación/prueba. Devuelve (x, y, meta)."""

    def __init__(self, files: Sequence[Path]):
        self.files = [Path(f) for f in files]

    def __len__(self) -> int:
        return len(self.files)

    def __getitem__(self, idx: int):
        f = self.files[idx]
        vol = load_study(f)
        x = torch.from_numpy(np.stack([vol["suv"], vol["ct"]]).astype(np.float32))
        y = torch.from_numpy(vol["seg"].astype(np.int64))[None]
        meta = {"file": str(f), "patient_id": f.stem.split("__")[0], "suv_top": vol["suv_top"],
                "ml_per_voxel": float(np.prod(vol["spacing"])) / 1000.0,
                "head_at_end": vol["head_at_end"]}
        return x, y, meta


def patch_positive_fraction(ds: PatchDataset, n: int = 50) -> float:
    """Diagnóstico rápido: fracción de parches que contienen al menos un vóxel de lesión.
    Con p_lesion = 0,7 y estudios positivos debería rondar 0,7 o más."""
    hits = 0
    for i in range(n):
        _, y = ds[i]
        hits += int(y.any())
    return hits / n
