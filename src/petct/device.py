"""Elección del dispositivo de cómputo para PyTorch.

Orden de preferencia: GPU NVIDIA (cuda, en Colab) > GPU de Apple (mps, en un Mac
con chip M) > CPU. La función no importa torch hasta que se la llama, así el resto
del paquete (SUV, conversión, preprocesamiento) funciona sin PyTorch instalado.

Nota sobre el Mac: MPS es la puerta de PyTorch al chip gráfico de Apple. Sirve para
desarrollar y para entrenamientos cortos, pero algunas operaciones 3D todavía caen
a la CPU y no existe la misma madurez que en CUDA. Por eso los entrenamientos con
el presupuesto completo se corren en Colab; en el Mac se prueba que el código
funciona con parches pequeños.
"""
from __future__ import annotations


def pick_device(prefer: str | None = None):
    """Devuelve un torch.device. `prefer` fuerza 'cuda', 'mps' o 'cpu' si está disponible."""
    import torch

    if prefer:
        return torch.device(prefer)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def describe_device() -> str:
    """Texto corto para la bitácora: qué dispositivo se usó y con cuánta memoria."""
    try:
        import torch
    except ImportError:
        return "torch no instalado"
    dev = pick_device()
    if dev.type == "cuda":
        props = torch.cuda.get_device_properties(0)
        return f"cuda: {props.name}, {props.total_memory / 2**30:.1f} GB"
    if dev.type == "mps":
        return "mps: GPU de Apple (memoria unificada con el sistema)"
    return "cpu"
