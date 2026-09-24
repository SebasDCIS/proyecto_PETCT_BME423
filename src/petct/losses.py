"""Rama `extendido`, paso 3. Pérdida pesada por órgano.

La pérdida de siempre es Dice + entropía cruzada (`DiceCELoss` de MONAI), y castiga igual
a todos los vóxeles. Acá la parte de entropía cruzada se pondera vóxel a vóxel: un vóxel
de fondo (sin lesión) que cae en un órgano con captación fisiológica (hígado, vejiga,
riñones, corazón... la lista es `petct.organs.ORGANOS_FISIOLOGICOS`) pesa `peso` veces más
que el resto. Todo lo demás (los vóxeles de lesión, el fondo fuera de esos órganos, y el
término Dice) queda exactamente como estaba.

La analogía del residente: hasta ahora cada error costaba lo mismo. Ahora el tutor le
dice "marcar la vejiga como tumor es un error más grave que marcar un pliegue de grasa",
y se lo cobra tres veces. No le da el mapa de órganos como entrada (en inferencia no lo
tendrá): se lo usa solo para corregirlo mientras aprende. Es la diferencia entre darle
una chuleta y enseñarle.

Escalado: la entropía cruzada pesada se divide por la suma de los pesos y no por el
número de vóxeles, así su magnitud es comparable a la versión sin pesos y el balance con
el Dice no se mueve por accidente.
"""
from __future__ import annotations

from typing import Sequence

import torch
import torch.nn as nn
import torch.nn.functional as F
from monai.losses import DiceLoss

from .organs import ORGANOS_FISIOLOGICOS_COD


class OrganWeightedDiceCE(nn.Module):
    """Dice (canal lesión) + entropía cruzada ponderada por órgano.

    forward(logits (N,2,D,H,W), y (N,1,D,H,W) en {0,1}, groups (N,1,D,H,W) códigos de órgano).
    Con `peso = 1` es numéricamente la misma pérdida que `DiceCELoss(softmax=True,
    to_onehot_y=True, include_background=False)`.
    """

    def __init__(self, peso: float = 3.0, grupos: Sequence[int] = ORGANOS_FISIOLOGICOS_COD):
        super().__init__()
        self.peso = float(peso)
        self.dice = DiceLoss(softmax=True, to_onehot_y=True, include_background=False)
        self.register_buffer("mask_grupos", torch.zeros(256, dtype=torch.bool), persistent=False)
        self.mask_grupos[list(grupos)] = True

    def weights(self, y: torch.Tensor, groups: torch.Tensor) -> torch.Tensor:
        """Peso por vóxel: `peso` en fondo dentro de órganos fisiológicos, 1 en el resto."""
        pesado = self.mask_grupos[groups.long()] & (y == 0)
        return torch.where(pesado, torch.full_like(y, self.peso, dtype=torch.float32),
                           torch.ones_like(y, dtype=torch.float32))

    def forward(self, logits: torch.Tensor, y: torch.Tensor, groups: torch.Tensor) -> torch.Tensor:
        w = self.weights(y, groups)[:, 0]                                   # (N, D, H, W)
        ce = F.cross_entropy(logits.float(), y[:, 0], reduction="none")     # (N, D, H, W)
        ce_w = (ce * w).sum() / w.sum()
        return self.dice(logits, y) + ce_w
