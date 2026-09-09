#!/usr/bin/env python
"""Paso 5d. Datos para el visor de fusión PET/CT (cortes axiales, HU reales).

Uso:
    python scripts/15_visor_fusion.py --estudios PETCT_f6295a93a6 PETCT_94962fe878 PETCT_1a90052cb2

Para cada estudio arma un "atlas de cortes" (sprite) RGBA donde cada píxel guarda:
  R = CT en unidades Hounsfield reales, mapeadas de [-1000, 1000] a [0, 255]
  G = SUV, mapeado de [0, SUV_MAX_VIS] a [0, 255]
  B = grupo de órgano (0-16) de TotalSegmentator
  A = 255
Con eso el visor puede rehacer la ventana de CT y la fusión en el navegador, y mostrar el HU y
el SUV reales bajo el cursor, que es lo que permite distinguir grasa (HU negativo) de músculo
o ganglio (HU positivo) cuando ambos captan.

El CT del .npz ya viene con ventana −200/300 aplicada, así que aquí se vuelve a leer
`CTres.nii.gz`, se remuestrea a 3 mm y se recorta con el mismo bbox: se recupera el HU real.

Los contornos (experto y predicción de cada modelo) van como listas de píxeles de borde, no
como imagen, para que sean exactos.

Escribe docs/figuras/visor_datos.js (un solo archivo, listo para incrustar en el visor).
"""
import argparse
import base64
import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.organs import GROUP_NAMES  # noqa: E402
from petct.preprocess import load_study, resample_iso  # noqa: E402

HU_LO, HU_HI = -1000.0, 1000.0      # rango que se guarda en 8 bits (paso ≈ 7,8 HU)
SUV_MAX_VIS = 15.0                  # tope de SUV representable (paso ≈ 0,06)
MAX_CORTES = 80                     # tope por estudio, para que el visor no pese de más
MARGEN = 6                          # cortes extra a cada lado de la zona de interés


def borde(mask2d: np.ndarray) -> list:
    """Píxeles de borde de una máscara 2D, como [x0, y0, x1, y1, ...] (compacto)."""
    if not mask2d.any():
        return []
    m = mask2d
    interior = np.ones_like(m)
    interior[1:, :] &= m[:-1, :]
    interior[:-1, :] &= m[1:, :]
    interior[:, 1:] &= m[:, :-1]
    interior[:, :-1] &= m[:, 1:]
    ys, xs = np.nonzero(m & ~interior)
    out = np.empty(2 * len(xs), dtype=np.int32)
    out[0::2], out[1::2] = xs, ys
    return out.tolist()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--estudios", nargs="+", required=True)
    ap.add_argument("--particion", default="val")
    ap.add_argument("--corridas", nargs="*", default=["A", "B", "C"])
    ap.add_argument("--procesado", default="data/processed")
    ap.add_argument("--nifti", default="data/interim/nifti")
    ap.add_argument("--organos", default="data/processed_organos")
    ap.add_argument("--manifest", default="data/manifests/subconjunto.csv")
    ap.add_argument("--salida", default="docs/figuras/visor_datos.js")
    a = ap.parse_args()

    sub = pd.read_csv(a.manifest).set_index("patient_id")
    estudios = []

    for pid in a.estudios:
        uid = sub.loc[pid, "study_uid"]
        base = f"{pid}__{uid}"
        print(f"[{pid}] cargando…", flush=True)
        vol = load_study(Path(a.procesado) / f"{base}.npz")
        suv = vol["suv"] * vol["suv_top"]
        gt = vol["seg"].astype(bool)
        bbox = vol["bbox"] if "bbox" in vol else None

        # CT con HU reales: releer el NIfTI, remuestrear igual y recortar con el bbox guardado
        import SimpleITK as sitk
        d = np.load(Path(a.procesado) / f"{base}.npz")
        box = d["bbox"]
        ct_img = resample_iso(sitk.ReadImage(str(Path(a.nifti) / pid / uid / "CTres.nii.gz")),
                              tuple(float(x) for x in vol["spacing"]), default_value=-1024.0)
        hu = sitk.GetArrayFromImage(ct_img).astype(np.float32)
        hu = hu[box[0, 0]:box[0, 1], box[1, 0]:box[1, 1], box[2, 0]:box[2, 1]]
        if hu.shape != suv.shape:
            print(f"  [aviso] formas distintas {hu.shape} vs {suv.shape}; se usa el CT con ventana")
            hu = vol["ct"] * 500.0 - 200.0

        org_file = Path(a.organos) / f"{base}.npz"
        groups = np.load(org_file)["groups"].astype(np.uint8) if org_file.exists() else np.zeros_like(gt, np.uint8)

        preds = {}
        for r in a.corridas:
            f = Path("runs") / r / f"mascaras_{a.particion}" / f"{base}.npz"
            if f.exists():
                preds[r] = np.load(f)["pred"].astype(bool)

        # Ventana de cortes: la de MAX_CORTES que contiene MÁS volumen de interés (lesión
        # anotada más falso positivo). Centrarla en el medio del rango dejaba fuera el
        # hallazgo cuando la predicción está repartida (error detectado el 2026-09-08).
        interes = gt.copy()
        for p in preds.values():
            interes |= p
        peso = interes.reshape(interes.shape[0], -1).sum(axis=1).astype(np.int64)
        nz_tot = suv.shape[0]
        if peso.sum() == 0:
            z0, z1 = 0, min(MAX_CORTES, nz_tot)
        elif nz_tot <= MAX_CORTES:
            z0, z1 = 0, nz_tot
        else:
            acum = np.concatenate([[0], np.cumsum(peso)])
            ini = np.arange(0, nz_tot - MAX_CORTES + 1)
            suma = acum[ini + MAX_CORTES] - acum[ini]
            z0 = int(ini[int(np.argmax(suma))])
            z1 = z0 + MAX_CORTES
        z0, z1 = int(z0), int(z1)
        cubierto = peso[z0:z1].sum() / max(1, peso.sum())
        print(f"  ventana cubre {100 * cubierto:.0f} % del volumen de interés", flush=True)
        n = z1 - z0
        H, W = int(suv.shape[1]), int(suv.shape[2])
        print(f"  cortes {z0}–{z1} ({n}) de {suv.shape[0]}; {H}×{W} px", flush=True)

        # sprite: cuadrícula de cortes
        cols = int(np.ceil(np.sqrt(n * H / max(W, 1))))
        cols = int(max(1, min(cols, n)))
        rows = int(np.ceil(n / cols))
        sprite = np.zeros((rows * H, cols * W, 4), dtype=np.uint8)
        sprite[..., 3] = 255

        r_ct = np.clip((hu[z0:z1] - HU_LO) / (HU_HI - HU_LO), 0, 1)
        g_suv = np.clip(suv[z0:z1] / SUV_MAX_VIS, 0, 1)
        for k in range(n):
            i, j = divmod(k, cols)
            sl = (slice(i * H, (i + 1) * H), slice(j * W, (j + 1) * W))
            sprite[sl[0], sl[1], 0] = (r_ct[k] * 255).astype(np.uint8)
            sprite[sl[0], sl[1], 1] = (g_suv[k] * 255).astype(np.uint8)
            sprite[sl[0], sl[1], 2] = groups[z0 + k]

        buf = io.BytesIO()
        Image.fromarray(sprite, "RGBA").save(buf, format="PNG", optimize=True)
        png64 = base64.b64encode(buf.getvalue()).decode()
        print(f"  sprite {cols}×{rows} = {sprite.shape[1]}×{sprite.shape[0]} px, {len(png64)/1e6:.1f} MB en base64", flush=True)

        # corte de apertura: el de mayor volumen predicho fuera de la lesión anotada
        z_best = n // 2
        if preds:
            ref = preds.get("A", next(iter(preds.values())))
            fp_por_corte = (ref & ~gt).reshape(ref.shape[0], -1).sum(axis=1)[z0:z1]
            if fp_por_corte.max() > 0:
                z_best = int(np.argmax(fp_por_corte))
        print(f"  corte de apertura: {z_best} (z={z0 + z_best})", flush=True)

        # contornos exactos por corte
        cont = {"gt": [borde(gt[z]) for z in range(z0, z1)]}
        for r, p in preds.items():
            cont[r] = [borde(p[z]) for z in range(z0, z1)]

        # MIP coronal de referencia (para ubicar el corte)
        mip = suv.max(axis=1)
        mip8 = (np.clip(mip / 8.0, 0, 1) * 255).astype(np.uint8)
        b2 = io.BytesIO()
        Image.fromarray(255 - mip8, "L").save(b2, format="PNG", optimize=True)
        mip64 = base64.b64encode(b2.getvalue()).decode()

        estudios.append({
            "id": pid, "diagnostico": str(sub.loc[pid, "diagnosis"]),
            "n": n, "z0": int(z0), "zBest": int(z_best), "nz": int(suv.shape[0]), "H": H, "W": W,
            "cols": cols, "rows": rows,
            "spacing": [float(x) for x in vol["spacing"]],
            "headAtEnd": bool(vol["head_at_end"]),
            "huLo": HU_LO, "huHi": HU_HI, "suvMax": SUV_MAX_VIS,
            "lesionMl": float(gt.sum() * np.prod(vol["spacing"]) / 1000.0),
            "sprite": png64, "mip": mip64,
            "mipShape": [int(mip.shape[0]), int(mip.shape[1])],
            "contornos": cont,
            "modelos": list(preds.keys()),
        })

    out = Path(a.salida)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"grupos": list(GROUP_NAMES), "estudios": estudios}
    def _py(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.bool_,)):
            return bool(o)
        raise TypeError(type(o))
    out.write_text("window.VISOR = " + json.dumps(payload, separators=(",", ":"), default=_py) + ";\n")
    print(f"\n{out} · {out.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()
