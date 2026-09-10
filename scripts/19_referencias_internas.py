#!/usr/bin/env python
"""Paso 6c. Referencia interna (hígado propio) de cada estudio, para el canal del modelo E.

Uso (no necesita PyTorch):
    python scripts/19_referencias_internas.py                 # todas las particiones que tengan mapa de órganos
    python scripts/19_referencias_internas.py --particion test

Escribe `data/manifests/referencias_internas.csv` con dos columnas de referencia por estudio:

  ref_higado             mediana del SUV de TODO el hígado, sin excluir nada más que el aire y
                         la zona borrada. **Es la que usa el canal de entrada**, porque es la
                         única calculable en un estudio nuevo, sin anotación.
  ref_higado_sin_lesion  la misma mediana excluyendo la lesión anotada y su halo de 2 vóxeles.
                         No se usa para entrenar: está solo para comprobar cuánto se separa de
                         la anterior. Si se separaran mucho, la referencia sin anotación estaría
                         contaminada por el tumor y habría que buscar otra cosa.

La comparación entre las dos columnas es la prueba de que usar la versión sin anotación no
estropea nada, y por eso el script la imprime al final en vez de dejarla implícita.

Requisito: el mapa de órganos de cada estudio (`scripts/11_organos_totalsegmentator.py`).
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.organs import internal_reference  # noqa: E402
from petct.reference import REF_POBLACIONAL, REL_TOP  # noqa: E402

MARGEN_LESION = 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--particion", default=None, choices=["train", "val", "test"],
                    help="por defecto, todas las que tengan mapa de órganos")
    ap.add_argument("--manifest", default="data/manifests/subconjunto.csv")
    ap.add_argument("--procesado", default="data/processed")
    ap.add_argument("--organos", default="data/processed_organos")
    ap.add_argument("--salida", default="data/manifests/referencias_internas.csv")
    a = ap.parse_args()

    sub = pd.read_csv(a.manifest)
    if a.particion:
        sub = sub[sub.split == a.particion]

    filas, faltan = [], []
    for i, r in enumerate(sub.itertuples(), 1):
        base = f"{r.patient_id}__{r.study_uid}"
        f_org = Path(a.organos) / f"{base}.npz"
        if not f_org.exists():
            faltan.append(r.patient_id)
            continue
        d = np.load(Path(a.procesado) / f"{base}.npz")
        suv = d["suv"].astype(np.float32) * float(d["suv_top"])
        body = d["body"].astype(bool)
        seg = d["seg"].astype(bool)
        groups = np.load(f_org)["groups"].astype(np.uint8)

        visible = body & (suv > 0.0)
        ref, origen = internal_reference(suv, groups, visible)          # ← la que usa el canal

        sin_les = visible.copy()
        if seg.any():
            sin_les &= ~ndimage.binary_dilation(seg, iterations=MARGEN_LESION)
        ref_sl, origen_sl = internal_reference(suv, groups, sin_les)    # ← solo para comparar

        filas.append({"patient_id": r.patient_id, "study_uid": r.study_uid, "split": r.split,
                      "diagnosis": r.diagnosis,
                      "ref_higado": round(float(ref), 4), "origen": origen,
                      "ref_higado_sin_lesion": round(float(ref_sl), 4), "origen_sin_lesion": origen_sl,
                      "lesion_ml": round(float(seg.sum() * np.prod(d["spacing"].astype(float)) / 1000.0), 2)})
        if i % 40 == 0:
            print(f"  {i}/{len(sub)}", flush=True)

    if not filas:
        sys.exit("Ningún estudio tenía mapa de órganos. Corre antes scripts/11_organos_totalsegmentator.py")
    df = pd.DataFrame(filas)

    out = Path(a.salida)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and a.particion:                 # actualizar sin perder las otras particiones
        prev = pd.read_csv(out)
        df = pd.concat([prev, df]).drop_duplicates(["patient_id", "study_uid"], keep="last")
    df.to_csv(out, index=False)

    print(f"\nReferencia interna de {len(df)} estudios · {out}")
    if faltan:
        print(f"[aviso] {len(faltan)} sin mapa de órganos, quedan fuera: {faltan[:5]}"
              f"{' ...' if len(faltan) > 5 else ''}")
    print(f"origen de la referencia: {df.origen.value_counts().to_dict()}")
    print(f"\nreferencia (SUV hepático) por partición:")
    print(df.groupby("split").ref_higado.describe()[["count", "mean", "std", "min", "50%", "max"]]
          .round(3).to_string())

    # La comprobación que justifica no usar la anotación
    ok = df[np.isfinite(df.ref_higado) & np.isfinite(df.ref_higado_sin_lesion) & (df.ref_higado_sin_lesion > 0)]
    dif = (ok.ref_higado - ok.ref_higado_sin_lesion) / ok.ref_higado_sin_lesion
    print(f"\nDiferencia entre calcular la referencia con y sin la anotación ({len(ok)} estudios):")
    print(f"  mediana {100 * dif.median():+.2f} %   |   p95 {100 * dif.abs().quantile(0.95):.2f} %   "
          f"|   máximo {100 * dif.abs().max():.2f} %")
    peor = ok.loc[dif.abs().idxmax()]
    print(f"  el peor caso es {peor.patient_id} ({peor.lesion_ml:.0f} mL de lesión anotada): "
          f"{peor.ref_higado:.2f} frente a {peor.ref_higado_sin_lesion:.2f}")
    print("  Si estas diferencias son pequeñas, usar la versión sin anotación —la única legal en un\n"
          "  estudio nuevo— no cambia el canal, y queda demostrado en vez de supuesto.")
    print(f"\nEl canal se construye como  SUV / referencia,  con tope en {REL_TOP:g} veces. "
          f"La ablación sustituye la referencia de cada paciente por la constante poblacional "
          f"{REF_POBLACIONAL:g}.")


if __name__ == "__main__":
    main()
