#!/usr/bin/env python
"""Paso 6a. Atlas de captación normal por órgano.

Uso (no necesita PyTorch; corre con numpy/scipy/pandas):
    python scripts/17_atlas_normalidad.py --subconjunto controles
    python scripts/17_atlas_normalidad.py --subconjunto train
    python scripts/17_atlas_normalidad.py --comparar

La idea clínica, en una línea: un SUV de 8 no significa lo mismo en el hígado que en el
músculo. Lo que un médico nuclear hace de forma implícita —y lo que la escala de Deauville
formaliza para el linfoma usando hígado y mediastino como referencia— es comparar la
captación de un foco contra lo que ese órgano capta normalmente. Este script construye esa
tabla de referencia para los 17 grupos de órganos del proyecto.

De dónde salen los "valores normales":

  --subconjunto controles : solo los estudios NEGATIVE del entrenamiento (35). Son pacientes
                            a los que se les hizo un PET/CT por sospecha oncológica y no se
                            les encontró lesión ávida de FDG. NO son sujetos sanos; es la
                            aproximación más limpia que el conjunto de datos permite.
  --subconjunto train     : los 176 estudios de entrenamiento, excluyendo los vóxeles
                            anotados como lesión (más un margen de seguridad). Cinco veces
                            más pacientes, a cambio de que la "normalidad" quede contaminada
                            con la patología que autoPET no anotó (inflamación, ganglios
                            reactivos).

El sentido de construir los dos es compararlos (`--comparar`). Si coinciden, la contaminación
es despreciable y queda demostrado en vez de supuesto; si no coinciden, el desacuerdo mismo
mide cuánta captación no tumoral anómala hay en la cohorte oncológica.

Qué se excluye siempre, y por qué:
  - la zona borrada por el defacing (SUV = 0): ahí no hay imagen.
  - todo lo que está fuera de la máscara corporal: es aire.
  - los vóxeles de lesión anotada, dilatados 2 vóxeles (6 mm): el margen evita que el halo
    de volumen parcial de un tumor infle el "normal" del órgano que lo rodea.

Salidas:
  results/atlas_normalidad_<nombre>.csv    una fila por grupo de órgano: percentiles agrupados
                                           y variabilidad entre pacientes
  results/atlas_por_paciente_<nombre>.csv  una fila por paciente y órgano (para ver la dispersión)
  results/atlas_hist_<nombre>.npz          el histograma crudo, por si hace falta recalcular
  results/comparacion_atlas.csv            (con --comparar) las dos versiones lado a lado
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.organs import GROUP_NAMES  # noqa: E402

# Histograma acumulado: 0 a 40 de SUV en pasos de 0,01. Guardar el histograma en vez de
# todos los vóxeles permite recorrer 176 estudios sin acumular gigabytes en memoria, y da
# percentiles con una precisión de 0,01 de SUV, que es más de la que necesitamos.
SUV_MAX_HIST = 40.0
N_BINS = 4000
BORDES = np.linspace(0.0, SUV_MAX_HIST, N_BINS + 1)
CENTROS = 0.5 * (BORDES[:-1] + BORDES[1:])
MARGEN_LESION = 2          # vóxeles de dilatación alrededor de la lesión anotada (6 mm)
PERCENTILES = [25, 50, 75, 90, 95, 99]


def percentiles_de_histograma(hist: np.ndarray, qs=PERCENTILES) -> dict:
    """Percentiles a partir de un histograma acumulado. Devuelve NaN si no hay datos."""
    total = hist.sum()
    if total == 0:
        return {f"p{q}": float("nan") for q in qs}
    acum = np.cumsum(hist) / total
    return {f"p{q}": float(CENTROS[int(np.searchsorted(acum, q / 100.0))]) for q in qs}


def media_sd_de_histograma(hist: np.ndarray) -> tuple:
    total = hist.sum()
    if total == 0:
        return float("nan"), float("nan")
    media = float((hist * CENTROS).sum() / total)
    var = float((hist * (CENTROS - media) ** 2).sum() / total)
    return media, float(np.sqrt(max(var, 0.0)))


def estudios_del_subconjunto(sub: pd.DataFrame, cual: str) -> pd.DataFrame:
    if cual == "controles":
        return sub[(sub.split == "train") & (sub.diagnosis == "NEGATIVE")]
    if cual == "train":
        return sub[sub.split == "train"]
    if cual == "val":                      # solo para diagnóstico; no usar como referencia
        return sub[sub.split == "val"]
    raise SystemExit(f"subconjunto desconocido: {cual}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subconjunto", default="controles", choices=["controles", "train", "val"])
    ap.add_argument("--manifest", default="data/manifests/subconjunto.csv")
    ap.add_argument("--procesado", default="data/processed")
    ap.add_argument("--organos", default="data/processed_organos")
    ap.add_argument("--salida", default="results")
    ap.add_argument("--comparar", action="store_true",
                    help="no calcula nada: junta los atlas ya escritos y escribe la tabla comparativa")
    a = ap.parse_args()

    out = Path(a.salida)
    out.mkdir(parents=True, exist_ok=True)

    if a.comparar:
        return comparar(out)

    sub = pd.read_csv(a.manifest)
    estudios = estudios_del_subconjunto(sub, a.subconjunto)
    print(f"atlas '{a.subconjunto}': {len(estudios)} estudios", flush=True)

    n_grupos = len(GROUP_NAMES)
    hist = np.zeros((n_grupos, N_BINS), dtype=np.int64)
    por_paciente = []
    usados, faltantes = 0, []

    for i, r in enumerate(estudios.itertuples(), 1):
        base = f"{r.patient_id}__{r.study_uid}"
        f_npz = Path(a.procesado) / f"{base}.npz"
        f_org = Path(a.organos) / f"{base}.npz"
        if not f_org.exists():
            faltantes.append(r.patient_id)
            continue

        d = np.load(f_npz)
        suv = d["suv"].astype(np.float32) * float(d["suv_top"])   # SUV en unidades reales
        seg = d["seg"].astype(bool)
        body = d["body"].astype(bool)
        groups = np.load(f_org)["groups"].astype(np.uint8)
        if groups.shape != suv.shape:
            faltantes.append(f"{r.patient_id} (forma {groups.shape} vs {suv.shape})")
            continue

        # Máscara de "esto es tejido normal medible"
        valido = body & (suv > 0.0)                    # fuera el aire y la zona del defacing
        if seg.any():
            halo = ndimage.binary_dilation(seg, iterations=MARGEN_LESION)
            valido &= ~halo                            # fuera la lesión y su borde difuso

        g = groups[valido]
        v = np.clip(suv[valido], 0.0, SUV_MAX_HIST - 1e-6)
        idx_bin = np.minimum((v / SUV_MAX_HIST * N_BINS).astype(np.int32), N_BINS - 1)

        # Un solo bincount 2D: grupo * N_BINS + bin
        plano = g.astype(np.int64) * N_BINS + idx_bin
        conteo = np.bincount(plano, minlength=n_grupos * N_BINS).reshape(n_grupos, N_BINS)
        hist += conteo

        # Estadísticos de este paciente, para medir la variabilidad entre personas
        for k, nombre in enumerate(GROUP_NAMES):
            if nombre == "fuera":
                continue
            n = int(conteo[k].sum())
            if n < 100:                                 # menos de 100 vóxeles: no es medible
                continue
            pc = percentiles_de_histograma(conteo[k])
            por_paciente.append({"patient_id": r.patient_id, "diagnosis": r.diagnosis,
                                 "organo": nombre, "n_voxeles": n,
                                 "mediana": pc["p50"], "p95": pc["p95"]})
        usados += 1
        if i % 20 == 0 or i == len(estudios):
            print(f"  {i}/{len(estudios)} · {usados} usados", flush=True)

    if faltantes:
        print(f"[aviso] {len(faltantes)} estudios sin mapa de órganos: {faltantes[:5]}"
              f"{' ...' if len(faltantes) > 5 else ''}", flush=True)
    if usados == 0:
        sys.exit("Ningún estudio tenía mapa de órganos. Corre antes scripts/11_organos_totalsegmentator.py")

    dfp = pd.DataFrame(por_paciente)
    filas = []
    for k, nombre in enumerate(GROUP_NAMES):
        if nombre == "fuera":
            continue
        n = int(hist[k].sum())
        pc = percentiles_de_histograma(hist[k])
        media, sd = media_sd_de_histograma(hist[k])
        sub_p = dfp[dfp.organo == nombre]
        filas.append({
            "organo": nombre,
            "n_pacientes": int(sub_p.patient_id.nunique()),
            "n_voxeles": n,
            "media": round(media, 3), "sd": round(sd, 3),
            **{k2: round(v2, 3) for k2, v2 in pc.items()},
            # Variabilidad ENTRE personas: la desviación de las medianas individuales. Es la
            # cifra que dice si 35 pacientes alcanzan para caracterizar ese órgano.
            "mediana_entre_pacientes": round(float(sub_p.mediana.median()), 3) if len(sub_p) else float("nan"),
            "sd_entre_pacientes": round(float(sub_p.mediana.std()), 3) if len(sub_p) > 1 else float("nan"),
            "cv_entre_pacientes": (round(float(sub_p.mediana.std() / sub_p.mediana.median()), 3)
                                   if len(sub_p) > 1 and sub_p.mediana.median() > 0 else float("nan")),
        })

    df = pd.DataFrame(filas).sort_values("n_voxeles", ascending=False)
    f1 = out / f"atlas_normalidad_{a.subconjunto}.csv"
    f2 = out / f"atlas_por_paciente_{a.subconjunto}.csv"
    df.to_csv(f1, index=False)
    dfp.to_csv(f2, index=False)
    np.savez_compressed(out / f"atlas_hist_{a.subconjunto}.npz",
                        hist=hist, bordes=BORDES, grupos=np.array(GROUP_NAMES))

    print(f"\nAtlas de captación normal · subconjunto '{a.subconjunto}' · {usados} estudios\n")
    cols = ["organo", "n_pacientes", "mediana_entre_pacientes", "p50", "p75", "p95", "p99", "cv_entre_pacientes"]
    print(df[cols].to_string(index=False))
    print(f"\n{f1}\n{f2}")
    print("\nCómo leerlo: 'p95' es el SUV que solo supera el 5 % del tejido normal de ese órgano; "
          "un foco por encima de ese valor ya es raro para ese órgano. 'cv_entre_pacientes' es la "
          "variabilidad de persona a persona: por debajo de 0,2 la referencia es sólida, por encima "
          "de 0,5 el órgano es demasiado variable para usarlo como referencia con esta muestra.")


def comparar(out: Path):
    """Junta el atlas de controles y el de train completo, para ver si coinciden."""
    fa, fb = out / "atlas_normalidad_controles.csv", out / "atlas_normalidad_train.csv"
    if not (fa.exists() and fb.exists()):
        sys.exit("Faltan los dos atlas. Corre el script con --subconjunto controles y con --subconjunto train.")
    a_ = pd.read_csv(fa).set_index("organo")
    b_ = pd.read_csv(fb).set_index("organo")
    comunes = [o for o in a_.index if o in b_.index]
    filas = []
    for o in comunes:
        filas.append({
            "organo": o,
            "n_pac_controles": int(a_.loc[o, "n_pacientes"]), "n_pac_train": int(b_.loc[o, "n_pacientes"]),
            "p50_controles": a_.loc[o, "p50"], "p50_train": b_.loc[o, "p50"],
            "dif_p50": round(float(b_.loc[o, "p50"] - a_.loc[o, "p50"]), 3),
            "p95_controles": a_.loc[o, "p95"], "p95_train": b_.loc[o, "p95"],
            "dif_p95": round(float(b_.loc[o, "p95"] - a_.loc[o, "p95"]), 3),
            "dif_p95_rel": (round(float((b_.loc[o, "p95"] - a_.loc[o, "p95"]) / a_.loc[o, "p95"]), 3)
                            if a_.loc[o, "p95"] > 0 else float("nan")),
        })
    df = pd.DataFrame(filas).sort_values("dif_p95_rel", ascending=False)
    f = out / "comparacion_atlas.csv"
    df.to_csv(f, index=False)
    print("Atlas de 35 controles frente a atlas de los 176 de entrenamiento\n")
    print(df.to_string(index=False))
    print(f"\n{f}")
    print("\nLectura: 'dif_p95_rel' cerca de 0 significa que incluir pacientes oncológicos (excluyendo "
          "su lesión anotada) no desplaza la referencia de ese órgano, y entonces conviene usar el "
          "atlas de 176 por tener cinco veces más pacientes. Una diferencia grande y positiva señala "
          "un órgano donde la cohorte oncológica tiene captación anómala que autoPET no anotó.")


if __name__ == "__main__":
    main()
