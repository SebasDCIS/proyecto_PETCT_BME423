"""Paso 3b y 4. Los tres modelos sobre una misma interfaz: `build_model("A" | "B" | "C")`.

Modelo A: fusión temprana. PET y CT entran como dos canales de la misma imagen, igual
que el rojo y el verde de una foto. Desde la primera convolución la red mezcla ambos.
Es la solución estándar (la que usan casi todos los equipos del reto autoPET) y por eso
es el punto de comparación. Uso la U-Net 3D de MONAI:

  - codificador de 5 niveles (32, 64, 128, 256, 320 filtros) con reducción ×2 en cada
    uno: un parche de 96³ llega al fondo como 6³ con 320 canales;
  - dos unidades residuales por nivel (dos convoluciones 3×3×3 con atajo);
  - normalización por instancia (el estándar en imagen médica con lotes chicos);
  - decodificador simétrico con conexiones de salto, y salida de 2 canales (fondo,
    lesión) sobre la que se aplica softmax.

Modelos B y C: fusión intermedia con dos codificadores. El PET baja por un codificador
y el CT por otro, idénticos en forma pero con pesos propios (los mismos bloques
residuales y el mismo plan de canales que A). Las conexiones de salto llevan al
decodificador los mapas de ambos codificadores, concatenados nivel a nivel. La única
diferencia entre B y C está en el cuello de botella:

  B  concatenación: se apilan los 320 mapas del PET y los 320 del CT y una convolución
     1×1×1 los mezcla en 320. La mezcla es fija: siempre las mismas posiciones, de la
     misma manera.
  C  atención cruzada + concatenación: antes de apilar, cada posición del mapa PET
     "pregunta" al mapa CT (query desde el PET; keys y values desde el CT) y suma la
     respuesta a su propio mapa. Después se concatena y mezcla exactamente como en B.
     C es, literalmente, B más un bloque de atención cruzada; por eso la comparación
     B contra C aísla el efecto de la atención.

Por qué la atención va en el cuello de botella: en 6³ hay 216 posiciones y la atención
compara todas contra todas (216²), trivial; en 96³ serían 884 736 posiciones, imposible.
Y la pregunta que importa ("¿qué órgano hay aquí?") se responde a la escala de 10 cm por
posición, no a la de 3 mm; los bordes finos los aporta el decodificador con los saltos.
Como la atención no sabe dónde está cada posición, se suma a las consultas y a las
etiquetas una codificación de posición sinusoidal 3D (fija, sin parámetros).

Parámetros (versión completa): A 12,9 M; B 34,6 M; C 35,0 M. B y C tienen más porque
llevan dos codificadores completos (11,9 M cada uno); el decodificador es liviano a
propósito (un subbloque por nivel). La diferencia B–C es solo el bloque de atención
(0,4 M): esa es la comparación limpia. Para separar "más red" de "otra fusión" existe
además `A+`: la misma fusión temprana con canales ×1,5 (28,9 M, del orden de B); si
sobra tiempo de cómputo, es el control que responde si B gana por la fusión o por el
tamaño.

`build_model(nombre, small=True)` da versiones chicas (16, 32, 64, 128) para pruebas y
humo; los números del informe salen siempre de las versiones completas.
"""
from __future__ import annotations

import math
from typing import Dict, Sequence

import torch
import torch.nn as nn
from monai.networks.blocks import Convolution, ResidualUnit
from monai.networks.nets import UNet

CHANNELS_FULL = (32, 64, 128, 256, 320)
CHANNELS_SMALL = (16, 32, 64, 128)
CHANNELS_WIDE = (48, 96, 192, 384, 480)     # A ancha: ~2,2× parámetros, para separar capacidad de fusión


# ---------------------------------------------------------------- modelo A (MONAI)
def early_fusion_unet(in_channels: int = 2, out_channels: int = 2, small: bool = False,
                      channels: Sequence[int] | None = None) -> nn.Module:
    channels = channels or (CHANNELS_SMALL if small else CHANNELS_FULL)
    return UNet(
        spatial_dims=3,
        in_channels=in_channels,
        out_channels=out_channels,
        channels=channels,
        strides=(2,) * (len(channels) - 1),
        num_res_units=2,
        norm="instance",
    )


# ---------------------------------------------------------------- piezas de B y C
class Encoder(nn.Module):
    """Camino de bajada: un bloque residual por nivel; el primero sin reducir, los demás
    reducen ×2. Devuelve los mapas de todos los niveles (para los saltos) y el del fondo."""

    def __init__(self, in_channels: int, channels: Sequence[int]):
        super().__init__()
        stages = []
        prev = in_channels
        for i, ch in enumerate(channels):
            stages.append(ResidualUnit(3, prev, ch, strides=1 if i == 0 else 2, kernel_size=3,
                                       subunits=2, norm="instance"))
            prev = ch
        self.stages = nn.ModuleList(stages)

    def forward(self, x: torch.Tensor):
        feats = []
        for st in self.stages:
            x = st(x)
            feats.append(x)
        return feats            # feats[-1] es el cuello de botella


class Decoder(nn.Module):
    """Camino de subida. En cada nivel: subir ×2 (convolución transpuesta), concatenar con
    los saltos de ambos codificadores y refinar con un bloque residual."""

    def __init__(self, channels: Sequence[int], skip_mult: int = 2, out_channels: int = 2):
        super().__init__()
        ups, blocks = [], []
        for i in range(len(channels) - 1, 0, -1):
            ups.append(Convolution(3, channels[i], channels[i - 1], strides=2, kernel_size=3,
                                   norm="instance", is_transposed=True))
            # un solo subbloque en la subida (como la U-Net de MONAI): el decodificador es
            # liviano a propósito; la capacidad está en los codificadores
            blocks.append(ResidualUnit(3, channels[i - 1] * (1 + skip_mult), channels[i - 1], strides=1,
                                       kernel_size=3, subunits=1, norm="instance"))
        self.ups = nn.ModuleList(ups)
        self.blocks = nn.ModuleList(blocks)
        self.head = nn.Conv3d(channels[0], out_channels, kernel_size=1)

    def forward(self, bottom: torch.Tensor, skips: Sequence[torch.Tensor]) -> torch.Tensor:
        x = bottom
        for up, blk, skip in zip(self.ups, self.blocks, reversed(skips)):
            x = up(x)
            x = blk(torch.cat([x, skip], dim=1))
        return self.head(x)


def sincos_pos_3d(shape: Sequence[int], dim: int, device, dtype) -> torch.Tensor:
    """Codificación de posición sinusoidal para una grilla (D, H, W): devuelve (D·H·W, dim).
    Un tercio de las dimensiones codifica z, otro y, otro x (como en los transformers de
    imagen). Fija, sin parámetros, sirve para cualquier tamaño de grilla."""
    d, h, w = shape
    per_axis = (dim // 3) // 2 * 2          # par, para que sin y cos ocupen la mitad cada uno
    out = []
    for n, axis in ((d, 0), (h, 1), (w, 2)):
        pos = torch.arange(n, device=device, dtype=torch.float32)
        freqs = torch.exp(torch.arange(0, per_axis, 2, device=device, dtype=torch.float32) * (-math.log(10000.0) / per_axis))
        ang = pos[:, None] * freqs[None, :]                       # (n, per_axis/2)
        enc = torch.cat([ang.sin(), ang.cos()], dim=1)             # (n, per_axis)
        view = [1, 1, 1, per_axis]
        view[axis] = n
        out.append(enc.view(view).expand(d, h, w, per_axis))
    pe = torch.cat(out, dim=-1)                                      # (d, h, w, 3·per_axis)
    if pe.shape[-1] < dim:                                           # relleno si dim no es múltiplo de 3
        pe = torch.cat([pe, torch.zeros(d, h, w, dim - pe.shape[-1], device=device)], dim=-1)
    return pe.reshape(d * h * w, dim).to(dtype)


class CrossAttentionFusion(nn.Module):
    """El PET pregunta al CT. Entrada: dos mapas (N, C, d, h, w). Salida: el mapa PET más la
    respuesta de la atención (conexión residual), con la misma forma.

    Cada posición del PET genera una consulta (query); cada posición del CT ofrece una
    etiqueta (key) y un contenido (value). Los pesos de atención dicen, para cada foco
    del PET, de qué regiones del CT tomar información. Ocho cabezas: ocho "preguntas"
    distintas en paralelo. Normalización previa (pre-LN) para estabilidad."""

    def __init__(self, channels: int, heads: int = 8, dropout: float = 0.0):
        super().__init__()
        self.norm_q = nn.LayerNorm(channels)
        self.norm_kv = nn.LayerNorm(channels)
        self.attn = nn.MultiheadAttention(channels, heads, dropout=dropout, batch_first=True)
        self.gamma = nn.Parameter(torch.zeros(1))   # la atención empieza "apagada" y la red decide cuánto usarla

    def forward(self, pet: torch.Tensor, ct: torch.Tensor) -> torch.Tensor:
        n, c, d, h, w = pet.shape
        pe = sincos_pos_3d((d, h, w), c, pet.device, pet.dtype)               # (L, C)
        q = pet.flatten(2).transpose(1, 2)                                     # (N, L, C)
        kv = ct.flatten(2).transpose(1, 2)
        q_in = self.norm_q(q) + pe
        kv_in = self.norm_kv(kv) + pe
        out, _ = self.attn(q_in, kv_in, kv_in, need_weights=False)
        fused = q + self.gamma * out
        return fused.transpose(1, 2).reshape(n, c, d, h, w)

    @torch.no_grad()
    def attention_maps(self, pet: torch.Tensor, ct: torch.Tensor) -> torch.Tensor:
        """Pesos de atención promediados sobre cabezas: (N, L_pet, L_ct). Para el análisis."""
        n, c, d, h, w = pet.shape
        pe = sincos_pos_3d((d, h, w), c, pet.device, pet.dtype)
        q = self.norm_q(pet.flatten(2).transpose(1, 2)) + pe
        kv = self.norm_kv(ct.flatten(2).transpose(1, 2)) + pe
        _, wts = self.attn(q, kv, kv, need_weights=True, average_attn_weights=True)
        return wts


class DualEncoderUNet(nn.Module):
    """B (fusion='concat') y C (fusion='cross_attention'). Ver el docstring del módulo."""

    def __init__(self, fusion: str = "concat", channels: Sequence[int] = CHANNELS_FULL,
                 out_channels: int = 2, heads: int = 8):
        super().__init__()
        if fusion not in ("concat", "cross_attention"):
            raise ValueError(fusion)
        self.fusion = fusion
        self.channels = tuple(channels)
        self.enc_pet = Encoder(1, channels)
        self.enc_ct = Encoder(1, channels)
        cb = channels[-1]
        self.cross = CrossAttentionFusion(cb, heads=heads) if fusion == "cross_attention" else None
        # la mezcla del fondo es idéntica en B y en C: 1×1×1 de 2·cb a cb
        self.fuse = Convolution(3, 2 * cb, cb, strides=1, kernel_size=1, norm="instance")
        self.dec = Decoder(channels, skip_mult=2, out_channels=out_channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        pet, ct = x[:, 0:1], x[:, 1:2]
        f_pet = self.enc_pet(pet)
        f_ct = self.enc_ct(ct)
        bottom_pet, bottom_ct = f_pet[-1], f_ct[-1]
        if self.cross is not None:
            bottom_pet = self.cross(bottom_pet, bottom_ct)
        bottom = self.fuse(torch.cat([bottom_pet, bottom_ct], dim=1))
        skips = [torch.cat([a, b], dim=1) for a, b in zip(f_pet[:-1], f_ct[:-1])]
        return self.dec(bottom, skips)


def dual_concat(small: bool = False) -> nn.Module:
    return DualEncoderUNet("concat", CHANNELS_SMALL if small else CHANNELS_FULL)


def dual_cross_attention(small: bool = False) -> nn.Module:
    return DualEncoderUNet("cross_attention", CHANNELS_SMALL if small else CHANNELS_FULL,
                           heads=4 if small else 8)


def early_fusion_wide(small: bool = False) -> nn.Module:
    return early_fusion_unet(small=small, channels=None if small else CHANNELS_WIDE)


_REGISTRY = {
    "A": ("fusión temprana: U-Net 3D con PET y CT como dos canales de entrada", early_fusion_unet),
    "A+": ("control de capacidad: A con canales ×1,5 (≈ los parámetros de B); separa el efecto de tener más red del de fusionar distinto", early_fusion_wide),
    "B": ("fusión intermedia: dos codificadores (PET, CT) concatenados en el cuello de botella y en los saltos", dual_concat),
    "C": ("fusión intermedia: dos codificadores con atención cruzada PET→CT en el cuello de botella (B + atención)", dual_cross_attention),
}


def build_model(name: str = "A", small: bool = False) -> nn.Module:
    """Construye el modelo por su letra."""
    if name not in _REGISTRY:
        raise NotImplementedError(f"modelo {name!r}: disponibles {sorted(_REGISTRY)}")
    return _REGISTRY[name][1](small=small)


def describe_models() -> Dict[str, str]:
    return {k: v[0] for k, v in _REGISTRY.items()}


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


@torch.no_grad()
def logits_to_mask(logits: torch.Tensor) -> torch.Tensor:
    """(N, 2, D, H, W) de logits → (N, 1, D, H, W) binario: 1 donde gana el canal lesión."""
    return logits.argmax(dim=1, keepdim=True)
