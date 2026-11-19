#!/usr/bin/env python
"""EXPERIMENTO de la rama `extendido`. Curva de rechazo de islas por brillo relativo al hígado.

Extrae, de las máscaras ya predichas, una fila por isla predicha y una fila por lesión
anotada, con lo necesario para construir después la curva de detección:

  islas_<corrida>_val.csv     estudio, isla, vol_ml, suvmax, veces_higado, organo,
                              lesiones_tocadas (ids separados por ';', vacío si es falsa)
  lesiones_<corrida>_val.csv  estudio, lesion, vol_ml, suvmax

Con esas dos tablas se puede contar correctamente cuántas LESIONES quedan detectadas al
aplicar un umbral de rechazo, que no es lo mismo que contar islas: varias islas pueden
tocar la misma lesión.

No usa GPU ni PyTorch.
"""
import argparse, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.organs import GROUP_NAMES, internal_reference  # noqa: E402

CONN = np.ones((3, 3, 3), dtype=int)

ap = argparse.ArgumentParser()
ap.add_argument("--corrida", required=True)
ap.add_argument("--particion", default="val")
a = ap.parse_args()

sub = pd.read_csv("data/manifests/subconjunto.csv")
est = sub[sub.split == a.particion]
mdir = Path("runs") / a.corrida / f"mascaras_{a.particion}"
islas, lesiones = [], []

for r in est.itertuples():
    base = f"{r.patient_id}__{r.study_uid}"
    fp, fo = mdir / f"{base}.npz", Path("data/processed_organos") / f"{base}.npz"
    if not (fp.exists() and fo.exists()):
        continue
    d = np.load(Path("data/processed") / f"{base}.npz")
    suv = d["suv"].astype(np.float32) * float(d["suv_top"])
    ml = float(np.prod(d["spacing"].astype(float)) / 1000.0)
    visible = suv > 0.0
    gt = d["seg"].astype(bool) & visible
    pred = np.load(fp)["pred"].astype(bool) & visible
    groups = np.load(fo)["groups"].astype(np.uint8)
    ref, _ = internal_reference(suv, groups, d["body"].astype(bool) & visible)

    lg, ng = ndimage.label(gt, structure=CONN)
    for sl, lab in zip(ndimage.find_objects(lg), range(1, ng + 1)):
        m = lg[sl] == lab
        lesiones.append({"estudio": r.patient_id, "lesion": lab,
                         "vol_ml": float(m.sum()) * ml, "suvmax": float(suv[sl][m].max())})

    lp, np_ = ndimage.label(pred, structure=CONN)
    for sl, lab in zip(ndimage.find_objects(lp), range(1, np_ + 1)):
        m = lp[sl] == lab
        tocadas = sorted(set(np.unique(lg[sl][m])) - {0})
        vals = groups[sl][m]
        cod = int(np.bincount(vals).argmax()) if vals.size else 0
        smax = float(suv[sl][m].max())
        islas.append({"estudio": r.patient_id, "isla": lab, "vol_ml": float(m.sum()) * ml,
                      "suvmax": smax,
                      "veces_higado": smax / ref if ref and np.isfinite(ref) else np.nan,
                      "organo": GROUP_NAMES[cod] if cod < len(GROUP_NAMES) else "otro",
                      "lesiones_tocadas": ";".join(str(x) for x in tocadas)})

o = Path("experimentos/resultados")
pd.DataFrame(islas).to_csv(o / f"islas_{a.corrida}_{a.particion}.csv", index=False)
pd.DataFrame(lesiones).to_csv(o / f"lesiones_{a.corrida}_{a.particion}.csv", index=False)
print(f"{a.corrida}: {len(islas)} islas predichas, {len(lesiones)} lesiones anotadas")
