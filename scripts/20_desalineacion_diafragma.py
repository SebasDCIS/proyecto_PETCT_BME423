#!/usr/bin/env python
"""Paso 7a. ¿Cuánto se desalinean el PET y el CT en el diafragma, en estudios reales?

Uso (no necesita PyTorch):
    python scripts/20_desalineacion_diafragma.py
    python scripts/20_desalineacion_diafragma.py --particion val

El problema, en una línea: el CT es una foto de un instante de la respiración y el PET es un
promedio de varios minutos de respiración libre. Donde más se nota es en el diafragma, que se
mueve 1–3 cm en respiración tranquila. Cuando no coinciden, la corrección de atenuación se
aplica con el mapa equivocado y el SUV de las lesiones de la base pulmonar y la cúpula hepática
sale mal: el estudio con maniquí XCAT de 2013 reporta 24 % de error de SUVmáx y 129 % de
sobrestimación de volumen para una lesión de 9 mm con 35 mm de excursión diafragmática.

Las magnitudes publicadas vienen de maniquíes y de series clínicas chicas. Esto mide el desfase
real en una cohorte pública de estudios estáticos de rutina, que es lo que se adquiere en la
mayoría de los servicios del mundo (y donde, justamente, no se puede aplicar ninguno de los
métodos de corrección publicados, porque todos necesitan adquisición sincronizada o datos
crudos).

## Cómo se mide

La clave es medir **la misma magnitud física en las dos modalidades**, para que la comparación
signifique algo. Esa magnitud es el **área de pulmón por corte**, visible en las dos por razones
distintas:

  en el CT   TotalSegmentator da la máscara de pulmón directamente (es aire, unos −800 HU)
  en el PET  el pulmón es lo frío: por debajo de 0,5 veces el hígado del propio paciente.
             El hígado, justo debajo del diafragma, vale 1,0 por definición de esa escala.
             La referencia se toma de la **mitad caudal** del hígado, lejos de la cúpula: si se
             toma de todo el hígado, un desfase grande mete pulmón en la muestra, baja la
             referencia y el umbral de "frío" deja de separar (detectado con datos sintéticos).

Las dos curvas tienen entonces la misma forma —la sección del pulmón a lo largo del eje
cabeza-pies— y el diafragma es su **borde caudal**, donde el área cae de golpe. El desfase es la
distancia entre los dos bordes.

Un primer intento comparaba la fracción de hígado del CT contra la actividad media del PET. No
sirvió, y conviene dejarlo escrito: son curvas de forma distinta, así que ni el cruce ni la
correlación significan nada entre ellas, y daba desfases de 17 cm, físicamente imposibles
(2026-09-11). Medir la misma magnitud en ambas es lo que hace comparable la comparación.

Se excluyen las columnas que contienen corazón (fuente caliente pegada al pulmón izquierdo) y
la ventana de análisis va **de la mitad del hígado a la mitad del pulmón**: fuera de ahí hay
otras cosas frías —gas intestinal por debajo, cuello y hombros por encima— que crean bordes
falsos.

Dos estimadores independientes sobre las mismas curvas, para que uno controle al otro:
  borde         dónde cada curva cruza la mitad de su máximo, con precisión subvóxel
  correlación   el desplazamiento que mejor las superpone, acotado a un rango fisiológico

## Convención de signo

Positivo = **el diafragma del PET está más craneal que el del CT**, que es lo que ocurre cuando
el CT se adquirió en una inspiración más profunda que el promedio respiratorio del PET.

Salidas:
  results/desalineacion_diafragma.csv    una fila por estudio
  docs/figuras/desalineacion.png         distribución del desfase y perfiles de ejemplo
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.organs import GROUP_CODE  # noqa: E402

MIN_COLUMNAS = 30        # columnas (x, y) mínimas que deben cruzar el diafragma
MIN_VOX_EJE = 4          # vóxeles mínimos de hígado y de pulmón en una columna para contarla
MARGEN_Z = 14            # cortes de contexto a cada lado de la transición
ZONA_RIESGO_MM = 30.0    # distancia al diafragma dentro de la cual una lesión queda expuesta
FRIO_REL = 0.5           # el pulmón en el PET: por debajo de 0,5 veces el hígado propio
MAX_DESFASE_MM = 50.0    # tope fisiológicamente razonable para la excursión diafragmática


def borde_caudal(area: np.ndarray, nivel: float = 0.5) -> float:
    """Borde caudal del pulmón, es decir el diafragma.

    `area` es el área de pulmón por corte normalizada a su máximo, con el índice creciendo hacia
    la cabeza: el pulmón ocupa los índices altos y el diafragma es el **primer** cruce
    ascendente de la mitad del máximo. Interpolación lineal para precisión subvóxel.
    """
    p = np.asarray(area, dtype=float)
    arriba = p >= nivel
    if arriba.all() or (~arriba).all():
        return float("nan")
    idx = np.flatnonzero(arriba[1:] & ~arriba[:-1])
    if len(idx) == 0:
        return float("nan")
    i = int(idx[0])
    d = p[i + 1] - p[i]
    return float(i + (nivel - p[i]) / d) if abs(d) > 1e-9 else float(i)


def desplazamiento_por_correlacion(a: np.ndarray, b: np.ndarray, max_shift: int) -> float:
    """Desplazamiento de `b` respecto de `a`, en índices, por mínimos cuadrados.

    Devuelve k tal que b[i] ≈ a[i − k]; positivo si la curva de b va corrida hacia índices
    altos. Ojo: el s que minimiza el error entre a[s:] y b[:n−s] es −k, de ahí el signo
    negativo al devolver (comprobado con desplazamientos sintéticos conocidos). Se refina con
    una parábola sobre los tres mejores para llegar a subvóxel sin interpolar las curvas.
    """
    a, b = np.asarray(a, float), np.asarray(b, float)
    n = len(a)
    max_shift = int(max(1, min(max_shift, n // 3)))
    shifts = np.arange(-max_shift, max_shift + 1)
    costos = []
    for s in shifts:
        x, y = (a[s:], b[: n - s]) if s >= 0 else (a[: n + s], b[-s:])
        costos.append(np.mean((x - y) ** 2) if len(x) > 5 else np.inf)
    costos = np.asarray(costos)
    k = int(np.argmin(costos))
    if 0 < k < len(costos) - 1:
        c0, c1, c2 = costos[k - 1], costos[k], costos[k + 1]
        den = c0 - 2 * c1 + c2
        sub = 0.5 * (c0 - c2) / den if abs(den) > 1e-12 else 0.0
        return -float(shifts[k] + np.clip(sub, -1, 1))
    return -float(shifts[k])


def medir_estudio(d, groups: np.ndarray):
    """Devuelve (resultado, estado). `resultado` es None si el estudio no permite medir."""
    suv = d["suv"].astype(np.float32) * float(d["suv_top"])
    body = d["body"].astype(bool)
    spacing = d["spacing"].astype(float)
    head_at_end = bool(d["head_at_end"]) if "head_at_end" in d else True

    pulmon = groups == GROUP_CODE["pulmon"]
    higado = groups == GROUP_CODE["higado"]
    corazon = groups == GROUP_CODE["corazon"]
    if pulmon.sum() < 1000 or higado.sum() < 1000:
        return None, "sin pulmón o sin hígado en el campo"

    # Referencia hepática a prueba de diafragma. No se usa `reference.liver_reference` (la del
    # modelo E) a propósito: aquella toma la mediana de TODO el hígado, y justamente cuando hay
    # mucho desfase la parte alta de la máscara hepática del CT contiene pulmón en el PET, lo
    # que baja la referencia y arruina el umbral de "frío". Acá se usa solo la mitad caudal del
    # hígado, que está lejos de la cúpula y nunca se contamina. Es además lo que hace un médico
    # nuclear: la ROI va en el lóbulo derecho, no pegada al diafragma.
    z_hig = np.flatnonzero(higado.any(axis=(1, 2)))
    corte = z_hig[len(z_hig) // 2]
    mitad_caudal = higado.copy()
    if head_at_end:
        mitad_caudal[corte:] = False          # z creciente = craneal: nos quedamos con lo bajo
    else:
        mitad_caudal[:corte] = False
    util = mitad_caudal & body & (suv > 0)
    if util.sum() < 500:
        return None, "hígado caudal insuficiente para la referencia"
    ref = float(np.median(suv[util]))
    if not np.isfinite(ref) or ref <= 0:
        return None, "referencia hepática inválida"

    # Columnas que cruzan el diafragma por el lado del hígado, sin corazón encima
    footprint = ((pulmon.sum(axis=0) >= MIN_VOX_EJE) & (higado.sum(axis=0) >= MIN_VOX_EJE)
                 & (corazon.sum(axis=0) == 0))
    if footprint.sum() < MIN_COLUMNAS:
        return None, f"solo {int(footprint.sum())} columnas útiles"

    # Ventana acotada al entorno del diafragma: de la mitad del hígado a la mitad del pulmón.
    # Extenderla hasta los extremos de ambos órganos, como hacía la primera versión, metía en la
    # curva del PET el gas intestinal (frío, por debajo del hígado) y el cuello y los hombros
    # (fríos, por encima del pulmón). Esos bordes falsos daban desfases de hasta 23 cm en 38 de
    # 202 estudios reales, con las curvas sintéticas pasando perfecto (2026-09-11). Entre las dos
    # medianas el diafragma queda encerrado por construcción y no hay nada más frío que el pulmón.
    z_p = np.flatnonzero(pulmon[:, footprint].any(axis=1))
    z_h = np.flatnonzero(higado[:, footprint].any(axis=1))
    mid_p, mid_h = int(np.median(z_p)), int(np.median(z_h))
    lo, hi = min(mid_p, mid_h), max(mid_p, mid_h) + 1
    if hi - lo < 16:
        return None, "hígado y pulmón demasiado juntos"

    # La misma magnitud en las dos modalidades: área de pulmón por corte, en las mismas columnas
    a_ct = pulmon[lo:hi][:, footprint].sum(axis=1).astype(float)
    frio = body & (suv < FRIO_REL * ref)
    a_pet = frio[lo:hi][:, footprint].sum(axis=1).astype(float)
    if a_ct.max() < 20 or a_pet.max() < 20:
        return None, "curvas de pulmón demasiado pequeñas"
    a_ct = a_ct / a_ct.max()
    a_pet = a_pet / a_pet.max()

    # Índice creciente hacia la cabeza, siempre: así el pulmón queda arriba y el diafragma es
    # el primer cruce ascendente del 50 %
    if not head_at_end:
        a_ct, a_pet = a_ct[::-1], a_pet[::-1]

    e_ct, e_pet = borde_caudal(a_ct), borde_caudal(a_pet)
    if not (np.isfinite(e_ct) and np.isfinite(e_pet)):
        return None, "no se encontró el borde del pulmón"

    dz = float(spacing[0])
    off_borde = (e_pet - e_ct) * dz                       # positivo = PET más craneal
    off_corr = desplazamiento_por_correlacion(a_ct, a_pet, int(MAX_DESFASE_MM / dz)) * dz

    # Índice del diafragma en el arreglo original (sin voltear), para ubicar las lesiones
    z_diaf = (lo + e_ct) if head_at_end else (hi - 1 - e_ct)

    return {
        "offset_mm": round(float(off_borde), 2),
        "offset_corr_mm": round(float(off_corr), 2),
        "columnas": int(footprint.sum()),
        "z_diafragma_ct": float(z_diaf),
        "spacing_z": dz,
        "ref_higado": round(float(ref), 3),
        "discrepancia_mm": round(abs(float(off_borde) - float(off_corr)), 2),
        # Dos estimadores independientes que coinciden es la única garantía que tenemos de que
        # la medición no se fue por un borde falso; no hay verdad de referencia con la que
        # comparar en datos reales.
        "confiable": bool(abs(float(off_borde) - float(off_corr)) <= 10.0),
        "_a_ct": a_ct, "_a_pet": a_pet, "_dz": dz,
    }, "ok"


def lesiones_en_riesgo(d, z_diaf: float) -> dict:
    """Lesión anotada dentro de la zona expuesta al artefacto, alrededor del diafragma."""
    seg = d["seg"].astype(bool)
    spacing = d["spacing"].astype(float)
    ml = float(np.prod(spacing) / 1000.0)
    if not seg.any():
        return {"lesion_total_ml": 0.0, "lesion_zona_riesgo_ml": 0.0, "frac_en_riesgo": 0.0}
    cerca = np.abs(np.arange(seg.shape[0]) - z_diaf) * spacing[0] <= ZONA_RIESGO_MM
    total = float(seg.sum() * ml)
    zona = float((seg & cerca[:, None, None]).sum() * ml)
    return {"lesion_total_ml": round(total, 2), "lesion_zona_riesgo_ml": round(zona, 2),
            "frac_en_riesgo": round(zona / total, 3) if total > 0 else 0.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--particion", default=None, choices=["train", "val", "test"])
    ap.add_argument("--manifest", default="data/manifests/subconjunto.csv")
    ap.add_argument("--procesado", default="data/processed")
    ap.add_argument("--organos", default="data/processed_organos")
    ap.add_argument("--salida", default="results/desalineacion_diafragma.csv")
    ap.add_argument("--figura", default="docs/figuras/desalineacion.png")
    a = ap.parse_args()

    sub = pd.read_csv(a.manifest)
    if a.particion:
        sub = sub[sub.split == a.particion]

    filas, curvas, descartes = [], {}, {}
    for i, r in enumerate(sub.itertuples(), 1):
        base = f"{r.patient_id}__{r.study_uid}"
        f_org = Path(a.organos) / f"{base}.npz"
        if not f_org.exists():
            descartes["sin mapa de órganos"] = descartes.get("sin mapa de órganos", 0) + 1
            continue
        d = np.load(Path(a.procesado) / f"{base}.npz")
        groups = np.load(f_org)["groups"].astype(np.uint8)
        if groups.shape != d["seg"].shape:
            descartes["formas distintas"] = descartes.get("formas distintas", 0) + 1
            continue
        res, estado = medir_estudio(d, groups)
        if res is None:
            descartes[estado] = descartes.get(estado, 0) + 1
            continue
        fila = {"patient_id": r.patient_id, "split": r.split, "diagnosis": r.diagnosis,
                **{k: v for k, v in res.items() if not k.startswith("_")}}
        fila.update(lesiones_en_riesgo(d, res["z_diafragma_ct"]))
        filas.append(fila)
        curvas[r.patient_id] = (res["_a_ct"], res["_a_pet"], res["_dz"], fila["offset_mm"])
        if i % 40 == 0:
            print(f"  {i}/{len(sub)} · {len(filas)} medidos", flush=True)

    if not filas:
        sys.exit(f"No se pudo medir ningún estudio. Descartes: {descartes}")
    df = pd.DataFrame(filas)
    out = Path(a.salida); out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)

    n_total = len(df)
    df_ok = df[df.confiable]
    o = df_ok.offset_mm
    print(f"\nDesalineación PET–CT en el diafragma · {n_total} estudios medidos de {len(sub)}")
    if descartes:
        print(f"descartados antes de medir: {descartes}")
    print(f"con los dos estimadores de acuerdo (≤ 10 mm): {len(df_ok)} de {n_total} "
          f"({100 * len(df_ok) / n_total:.0f} %); las cifras siguientes son sobre esos")
    print(f"\n  mediana del desfase absoluto ...... {o.abs().median():.1f} mm")
    print(f"  media (con signo) ................. {o.mean():+.1f} mm   (positivo = PET más craneal)")
    print(f"  percentil 75 del absoluto ......... {o.abs().quantile(0.75):.1f} mm")
    print(f"  percentil 95 del absoluto ......... {o.abs().quantile(0.95):.1f} mm")
    print(f"  máximo ............................ {o.abs().max():.1f} mm")
    for u in (5, 10, 15, 20, 30):
        print(f"  estudios con desfase > {u:2d} mm ...... {100 * (o.abs() > u).mean():5.1f} %  "
              f"({int((o.abs() > u).sum())} de {len(df)})")

    conc = (df_ok.offset_mm - df_ok.offset_corr_mm).abs()
    print(f"\n  acuerdo entre los dos estimadores: mediana {conc.median():.1f} mm, "
          f"p90 {conc.quantile(0.9):.1f} mm, correlación de Pearson "
          f"{df.offset_mm.corr(df.offset_corr_mm):.3f}")

    pos = df_ok[df_ok.lesion_total_ml > 0]
    if len(pos):
        print(f"\nLesión anotada dentro de {ZONA_RIESGO_MM:.0f} mm del diafragma "
              f"({len(pos)} estudios con lesión):")
        print(f"  con algo de lesión en la zona ............ {100 * (pos.lesion_zona_riesgo_ml > 0).mean():.1f} %")
        exp = pos[(pos.lesion_zona_riesgo_ml > 0) & (pos.offset_mm.abs() > 10)]
        print(f"  lesión en la zona Y desfase > 10 mm ...... {len(exp)} "
              f"({100 * len(exp) / len(pos):.1f} % de los positivos)")

    print(f"\n{out}")
    figura(df_ok, curvas, Path(a.figura))
    print(a.figura)


def figura(df, curvas, destino: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    destino.parent.mkdir(parents=True, exist_ok=True)
    # Tres ejemplos: el mejor alineado, uno intermedio y el peor
    orden = df.reindex(df.offset_mm.abs().sort_values().index)
    elegidos = [orden.iloc[0], orden.iloc[len(orden) // 2], orden.iloc[-1]]
    elegidos = [e for e in elegidos if e.patient_id in curvas]

    fig, ax = plt.subplots(1, 1 + len(elegidos), figsize=(5 + 3.6 * len(elegidos), 4.2))
    ax = np.atleast_1d(ax)

    o = df.offset_mm
    lim = max(10.0, float(np.ceil(max(abs(o.quantile(0.02)), abs(o.quantile(0.98))) / 5) * 5))
    ax[0].hist(o, bins=np.arange(-lim, lim + 2.5, 2.5), color="#2F6285", edgecolor="white")
    ax[0].axvline(0, color="#444", lw=1)
    for u in (-10, 10):
        ax[0].axvline(u, color="#B85C10", ls="--", lw=1)
    ax[0].set_xlabel("desfase PET − CT en el diafragma (mm)\npositivo = PET más craneal")
    ax[0].set_ylabel("estudios")
    ax[0].set_title(f"n = {len(df)} · mediana |desfase| = {o.abs().median():.1f} mm")

    for k, e in enumerate(elegidos, start=1):
        a_ct, a_pet, dz, off = curvas[e.patient_id]
        z = np.arange(len(a_ct)) * dz
        ax[k].plot(z, a_ct, color="#2F6285", lw=2, label="CT (máscara de pulmón)")
        ax[k].plot(z, a_pet, color="#B85C10", lw=2, label="PET (por debajo de 0,5× hígado)")
        ax[k].axhline(0.5, color="#999", ls=":", lw=1)
        ax[k].set_title(f"{e.patient_id} · {off:+.1f} mm")
        ax[k].set_xlabel("eje pies→cabeza (mm)")
        ax[k].set_ylabel("área de pulmón (normalizada)")
        ax[k].legend(fontsize=8, loc="lower right")
    fig.suptitle("Desalineación PET–CT medida en el diafragma · PET/CT estáticos de rutina", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(destino, dpi=140)
    plt.close(fig)


if __name__ == "__main__":
    main()
