"""Paso 6c. La referencia interna del paciente como tercer canal de entrada (modelo E).

Por qué existe este archivo, en un párrafo. La red se entrena con parches de 96³ vóxeles,
288 mm de lado. Desde un parche centrado en la pelvis **no se ve el hígado**: está fuera del
campo. Así que la captación hepática del propio paciente —que es la referencia con la que la
clínica lee un PET desde que existe la escala de Deauville— es información que la red no puede
deducir del parche por mucho que se entrene. El experimento del 2026-09-11
(`docs/ANALISIS_ATLAS.md`) mostró además que sí aporta: es la única de las cuatro puntuaciones
probadas que mueve el AUC *dentro* de un mismo órgano (riñones 0,887 → 1,000; hígado 0,698 →
0,778), porque su divisor cambia de paciente a paciente. Dividir por una constante poblacional,
en cambio, es una transformación monótona y no cambia nada.

De ahí el tercer canal: `SUV del vóxel ÷ SUV hepático de este paciente`.

## Dos decisiones que hay que poder defender

**1. La referencia se calcula SIN mirar la anotación.** En el atlas (`scripts/17`) sí se excluye
la lesión, porque ahí se está caracterizando la normalidad. Pero el canal de entrada tiene que
poder calcularse en un estudio nuevo, donde no hay anotación: usarla sería una fuga de
información que inflaría los resultados de validación y prueba. Por eso la referencia es la
**mediana** del SUV del hígado sobre todo el órgano, sin excluir nada. La mediana es robusta:
una lesión que ocupe menos de la mitad del hígado casi no la mueve. Es, de hecho, lo que hace
un médico nuclear cuando coloca una ROI de 3 cm en una zona de aspecto sano del lóbulo derecho.

**2. El tope del canal es 8 veces el hígado.** El canal se lleva a [0, 1] dividiendo por
`REL_TOP = 8`. La justificación es clínica: la frontera entre Deauville 4 y 5 está en 2–3 veces
el hígado, así que todo lo diagnósticamente relevante queda dentro del rango con resolución de
sobra. De paso arregla un problema del canal de SUV existente, que al dividir por 30 deja al
hígado en 0,07 y a casi todo el tejido normal aplastado contra el cero; en este canal el hígado
queda en 0,125 y la zona de decisión ocupa el tercio bajo de la escala.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

# Tope del canal relativo: 8 veces el hígado del paciente. Ver la nota de arriba.
REL_TOP = 8.0

# Mediana del SUV hepático de los 176 estudios de entrenamiento (results/atlas_normalidad_train.csv).
# Solo se usa para la ablación: sustituir la referencia de cada paciente por esta constante
# convierte el tercer canal en un reescalado monótono del canal de SUV, o sea información cero
# sobre el paciente. Es la forma limpia de aislar qué aporta la parte *individual*.
REF_POBLACIONAL = 2.165


def load_reference_table(csv_file: str | Path, columna: str = "ref_higado") -> Dict[str, float]:
    """Lee `data/manifests/referencias_internas.csv` → {'<pid>__<uid>': referencia}.

    La clave es el nombre base del `.npz`, que es como se identifican los estudios en el resto
    del proyecto. Se descartan las filas sin referencia utilizable.
    """
    import pandas as pd

    df = pd.read_csv(csv_file)
    tabla: Dict[str, float] = {}
    for r in df.itertuples():
        v = float(getattr(r, columna))
        if np.isfinite(v) and v > 0:
            tabla[f"{r.patient_id}__{r.study_uid}"] = v
    return tabla


def reference_for(tabla: Optional[Dict[str, float]], stem: str,
                  por_defecto: float = REF_POBLACIONAL) -> float:
    """Referencia de un estudio por el nombre base de su `.npz`.

    Si el estudio no está en la tabla se usa la constante poblacional en vez de fallar: el canal
    queda sin información individual para ese caso, que es peor que tenerla pero mucho mejor que
    cortar una corrida de nueve horas a mitad de camino. El script 19 avisa cuántos faltan.
    """
    if tabla is None:
        return float(por_defecto)
    return float(tabla.get(stem, por_defecto))


def relative_channel(suv_norm: np.ndarray, suv_top: float, ref: float) -> np.ndarray:
    """Canal relativo en [0, 1] a partir del SUV ya normalizado que guarda el `.npz`.

    `suv_norm` es SUV/suv_top (lo que hay en el archivo), así que el SUV real es
    `suv_norm * suv_top` y el canal es ese SUV dividido por la referencia del paciente, con
    tope en REL_TOP veces.
    """
    if not np.isfinite(ref) or ref <= 0:
        ref = REF_POBLACIONAL
    escala = float(suv_top) / (float(ref) * REL_TOP)
    return np.clip(np.asarray(suv_norm, dtype=np.float32) * escala, 0.0, 1.0)


def stack_input(suv_norm: np.ndarray, ct: np.ndarray, suv_top: float,
                ref: Optional[float] = None) -> np.ndarray:
    """Entrada del modelo: (2, D, H, W) sin referencia, (3, D, H, W) con ella.

    El orden de los dos primeros canales es el mismo que usan A, B y C desde el principio
    (SUV, CT), para que un checkpoint viejo siga siendo compatible y para que B y C puedan
    seguir repartiendo canal 0 = PET, canal 1 = CT.
    """
    suv = np.asarray(suv_norm, dtype=np.float32)
    canales = [suv, np.asarray(ct, dtype=np.float32)]
    if ref is not None:
        canales.append(relative_channel(suv, suv_top, ref))
    return np.stack(canales)


def liver_reference(suv_real: np.ndarray, groups: np.ndarray, body: np.ndarray,
                    min_voxeles: int = 500) -> Tuple[float, str]:
    """Referencia interna calculable en un estudio nuevo: mediana del SUV del hígado.

    A diferencia de `organs.internal_reference`, que se usa para construir el atlas, aquí **no**
    se excluye la lesión anotada: este número tiene que poder calcularse sin anotación. Sí se
    excluyen el aire y la zona borrada por el defacing, que no son tejido.
    """
    from .organs import internal_reference

    valido = np.asarray(body, dtype=bool) & (np.asarray(suv_real) > 0.0)
    return internal_reference(suv_real, groups, valido)
