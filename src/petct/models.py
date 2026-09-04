"""Paso 3b. Los modelos. Aquí vive el modelo A; B y C se agregan en el Paso 4 sobre la
misma interfaz, para que el script de entrenamiento no cambie.

Modelo A: fusión temprana. PET y CT entran como dos canales de la misma imagen, igual
que el rojo y el verde de una foto. Desde la primera convolución la red mezcla ambos.
Es la solución estándar (la que usan casi todos los equipos del reto autoPET) y por eso
es el punto de comparación de los otros dos. Uso la U-Net 3D de MONAI:

  - codificador de 5 niveles (32, 64, 128, 256, 320 filtros) con reducción ×2 en cada
    uno: un parche de 96³ llega al fondo como 6³ con 320 canales;
  - dos unidades residuales por nivel (dos convoluciones 3×3×3 con atajo);
  - normalización por instancia (el estándar en imagen médica con lotes chicos);
  - decodificador simétrico con conexiones de salto, y salida de 2 canales (fondo,
    lesión) sobre la que se aplica softmax.

Por qué esta configuración y no otra: es la que cabe en 16 GB de GPU con lote 2 y
parches de 96³ en precisión mixta, y es la misma que se reutiliza como codificador en
B y C, así los tres modelos tienen capacidades comparables (la comparación es de la
estrategia de fusión, no del tamaño de la red).

`build_model("A", small=True)` da una versión chica (16, 32, 64, 128) para pruebas y
para el humo en el Mac; los números del informe salen siempre de la versión completa.
"""
from __future__ import annotations

from typing import Dict

import torch
import torch.nn as nn
from monai.networks.nets import UNet

CHANNELS_FULL = (32, 64, 128, 256, 320)
CHANNELS_SMALL = (16, 32, 64, 128)


def early_fusion_unet(in_channels: int = 2, out_channels: int = 2, small: bool = False) -> nn.Module:
    channels = CHANNELS_SMALL if small else CHANNELS_FULL
    return UNet(
        spatial_dims=3,
        in_channels=in_channels,
        out_channels=out_channels,
        channels=channels,
        strides=(2,) * (len(channels) - 1),
        num_res_units=2,
        norm="instance",
    )


_REGISTRY = {
    "A": ("fusión temprana: U-Net 3D con PET y CT como dos canales de entrada", early_fusion_unet),
}


def build_model(name: str = "A", small: bool = False) -> nn.Module:
    """Construye el modelo por su letra. B y C llegan en el Paso 4."""
    if name not in _REGISTRY:
        raise NotImplementedError(f"modelo {name!r}: disponibles {sorted(_REGISTRY)} (B y C se agregan en el Paso 4)")
    return _REGISTRY[name][1](small=small)


def describe_models() -> Dict[str, str]:
    return {k: v[0] for k, v in _REGISTRY.items()}


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


@torch.no_grad()
def logits_to_mask(logits: torch.Tensor) -> torch.Tensor:
    """(N, 2, D, H, W) de logits → (N, 1, D, H, W) binario: 1 donde gana el canal lesión."""
    return logits.argmax(dim=1, keepdim=True)
