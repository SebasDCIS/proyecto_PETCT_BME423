#!/usr/bin/env python
"""Métricas comprometidas en la definición de tema que faltaban, sobre máscaras ya guardadas.

No entrena ni vuelve a predecir nada: lee las máscaras de `runs/*/mascaras_<particion>/` y los
estudios preprocesados. Corre sin torch.

Calcula, por estudio y por brazo:

  1. Hausdorff 95 (HD95, mm). Para cada vóxel del borde de la predicción, la distancia al
     borde más cercano de la verdad, y al revés. Se toma el percentil 95 de cada lado y se
     queda el mayor (misma convención que MONAI). Solo en estudios positivos y con la métrica
     corregida (sin la zona anonimizada). Si la predicción está vacía, el HD95 no existe y se
     cuenta aparte.
  2. Error de SUVmax por paciente: SUVmax dentro de la predicción contra SUVmax dentro de la
     anotación. El SUV del preprocesamiento tiene tope en 30, así que un SUVmax real mayor que
     30 queda como 30; el script cuenta cuántos estudios tocan ese tope.
  3. Contraste con el script oficial de autoPET (`scripts/oficial_autopet/val_script.py`,
     copiado sin cambios de github.com/lab-midas/autoPET, licencia MIT). El oficial usa
     componentes con conectividad 18 y no excluye la zona anonimizada; se compara contra
     nuestra implementación (conectividad 26) en la misma métrica cruda.
  4. Referencia clásica con exclusión de órganos por TotalSegmentator: umbral SUV 2,5,
     apertura de radio 1, mínimo 0,5 mL y se apagan los vóxeles que caen en los grupos de
     `petct.organs.ORGANOS_FISIOLOGICOS` (12 grupos; lista fijada el 2026-09-24, antes de abrir la
     prueba). Es la variante que prometía la definición y que no se había corrido.

Nada de esto estaba en el preregistro de la prueba: se reporta como análisis secundario,
declarado después de abrirla, sin parámetros ajustables.

Uso (desde la raíz del repositorio):
    python scripts/40_metricas_complementarias.py --particion test
    python scripts/40_metricas_complementarias.py --particion val --solo-clasica
"""
import argparse
import pickle
import time
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from petct.classical import classical_segmentation  # noqa: E402
from petct.metrics import blank_region_mask, evaluate_study  # noqa: E402
from petct.organs import ORGANOS_FISIOLOGICOS_COD as CODIGOS  # noqa: E402
from petct.preprocess import load_study  # noqa: E402

# Brazos: etiqueta -> lista de carpetas de máscaras (varias = semillas, se promedian por estudio)
BRAZOS = {
    "Acto 1 · A": ["A", "A_s2", "A_s3"],
    "Acto 1 · B": ["B", "B_s2", "B_s3"],
    "Acto 1 · C": ["C", "C_s2", "C_s3"],
    "Acto 1 · E": ["E", "E_s2", "E_s3"],
    "Extendido · A": ["A_ext_largo", "A_ext_largo_s2", "A_ext_largo_s3"],
    "Extendido · A+": ["Aplus_ext_largo", "Aplus_ext_largo_s2", "Aplus_ext_largo_s3"],
    "Extendido · B": ["B_ext_largo", "B_ext_largo_s2", "B_ext_largo_s3"],
    "Extendido · C": ["C_ext_largo", "C_ext_largo_s2", "C_ext_largo_s3"],
    "Extendido · B preentrenada": ["B_ext_largo_pre", "B_ext_largo_pre_s2", "B_ext_largo_pre_s3"],
    "Ensamble + TTA (u 0,5)": ["ensambles/ensamble_B_ens_tta"],
    "Sistema final (u 0,6)": ["ensambles/ensamble_final"],
}
# Brazos que se contrastan con el script oficial (una corrida cada uno, para no repetir semillas)
BRAZOS_OFICIAL = {
    "Clásica": None,
    "Acto 1 · A (s423)": "A",
    "Extendido · B (s423)": "B_ext_largo",
    "Sistema final (u 0,6)": "ensambles/ensamble_final",
}


def split_files(manifest, procesado, particion):
    sub = pd.read_csv(manifest)
    sub = sub[sub.split == particion]
    fs = [Path(procesado) / f"{r.patient_id}__{r.study_uid}.npz" for r in sub.itertuples()]
    return sorted(f for f in fs if f.exists())


def borde(m):
    return m & ~ndimage.binary_erosion(m, structure=np.ones((3, 3, 3), bool), border_value=0)


def hd95(pred, gt, spacing):
    """HD95 simétrico en mm (máximo de los dos percentiles 95 dirigidos). NaN si alguna está vacía."""
    if not pred.any() or not gt.any():
        return float("nan")
    union = pred | gt
    idx = np.argwhere(union)
    lo = np.maximum(idx.min(0) - 2, 0)
    hi = np.minimum(idx.max(0) + 3, np.array(union.shape))
    sl = tuple(slice(a, b) for a, b in zip(lo, hi))
    p, g = pred[sl], gt[sl]
    bp, bg = borde(p), borde(g)
    d_a_g = ndimage.distance_transform_edt(~bg, sampling=spacing)
    d_a_p = ndimage.distance_transform_edt(~bp, sampling=spacing)
    return float(max(np.percentile(d_a_g[bp], 95), np.percentile(d_a_p[bg], 95)))


def suvmax(suv, m):
    return float(suv[m].max()) if m.any() else float("nan")


def clasica(vol, suv, ml, groups, con_organos):
    organos = None
    if con_organos:
        organos = {"fisiologicos": np.isin(groups, CODIGOS)}
    return classical_segmentation(suv, vol["body"], ml, 2.5, 1, 0.5, organ_masks=organos,
                                  use_heuristics=False, head_at_end=bool(vol["head_at_end"]))


def cargar_oficial():
    ruta = RAIZ / "scripts" / "oficial_autopet" / "val_script.py"
    spec = importlib.util.spec_from_file_location("val_script_oficial", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--particion", default="test", choices=["val", "test"])
    ap.add_argument("--manifest", default="data/manifests/subconjunto_extendido.csv")
    ap.add_argument("--procesado", default="data/processed")
    ap.add_argument("--organos", default="data/processed_organos")
    ap.add_argument("--solo-clasica", action="store_true", help="solo la referencia clásica con exclusión")
    ap.add_argument("--max-segundos", type=float, default=1e9,
                    help="cortar después de este tiempo; se retoma donde quedó (cada estudio se guarda aparte)")
    a = ap.parse_args()
    t0 = time.time()

    files = split_files(a.manifest, a.procesado, a.particion)
    out_dir = Path("results") / ("test_final" if a.particion == "test" else "val_final")
    out_dir.mkdir(parents=True, exist_ok=True)
    oficial = None if a.solo_clasica else cargar_oficial()

    cache = out_dir / f"_s40_{a.particion}{'_clasica' if a.solo_clasica else ''}"
    cache.mkdir(exist_ok=True)
    for f in files:
        est = f.stem.split("__")[0]
        if (cache / f"{est}.pkl").exists():
            continue
        if time.time() - t0 > a.max_segundos:
            print("tiempo agotado; volver a correr para seguir", flush=True)
            return
        filas_hd, filas_suv, filas_of, filas_cl = [], [], [], []
        vol = load_study(f)
        suv = (vol["suv"].astype(np.float32) * vol["suv_top"])
        gt_crudo = vol["seg"].astype(bool)
        spacing = tuple(float(s) for s in vol["spacing"])
        ml = float(np.prod(vol["spacing"])) / 1000.0
        blank = blank_region_mask(suv)
        gt = gt_crudo & ~blank
        z = np.load(Path(a.organos) / f.name, allow_pickle=True)
        groups = z["groups"]
        positivo = bool(gt.any())

        # referencias clásicas, sin y con exclusión de órganos
        mascaras_clasicas = {}
        for etiqueta, con in (("Clásica", False), ("Clásica + exclusión de órganos", True)):
            pred = clasica(vol, suv, ml, groups, con)
            mascaras_clasicas[etiqueta] = pred
            m = evaluate_study(pred, gt_crudo, suv, ml, exclude_blank=True)
            m.update(estudio=est, brazo=etiqueta)
            filas_cl.append(m)
        if a.solo_clasica:
            pickle.dump((filas_hd, filas_suv, filas_of, filas_cl), open(cache / f"{est}.pkl", "wb"))
            print(f"[ok] {est}", flush=True)
            continue

        # HD95 y SUVmax por brazo (y las clásicas)
        fuentes = {k: [None] for k in mascaras_clasicas}
        fuentes.update(BRAZOS)
        for brazo, carpetas in fuentes.items():
            for corrida in carpetas:
                if corrida is None:
                    pred = mascaras_clasicas[brazo] & ~blank
                else:
                    pred = np.load(RAIZ / "runs" / corrida / f"mascaras_{a.particion}" / f.name)["pred"].astype(bool) & ~blank
                if positivo:
                    filas_hd.append(dict(estudio=est, brazo=brazo, corrida=corrida or brazo,
                                         hd95_mm=hd95(pred, gt, spacing), pred_vacia=not pred.any()))
                    filas_suv.append(dict(estudio=est, brazo=brazo, corrida=corrida or brazo,
                                          suvmax_gt=suvmax(suv, gt), suvmax_pred=suvmax(suv, pred)))

        # contraste con el script oficial (métrica cruda: sin excluir la zona anonimizada)
        for brazo, corrida in BRAZOS_OFICIAL.items():
            if corrida is None:
                pred = mascaras_clasicas["Clásica"]
            else:
                pred = np.load(RAIZ / "runs" / corrida / f"mascaras_{a.particion}" / f.name)["pred"].astype(bool)
            # recorte a la caja de predicción y verdad: no cambia ninguna componente y acelera el oficial
            caja = pred | gt_crudo
            if caja.any():
                ii = np.argwhere(caja)
                sl = tuple(slice(lo, hi + 1) for lo, hi in zip(ii.min(0), ii.max(0)))
            else:
                sl = tuple(slice(0, 1) for _ in caja.shape)
            p8, g8 = pred[sl].astype(np.uint8), gt_crudo[sl].astype(np.uint8)
            fp_of = oficial.false_pos_pix(g8, p8) * ml
            fn_of = oficial.false_neg_pix(g8, p8) * ml
            d_of = float(oficial.dice_score(g8, p8)) if (p8.sum() + g8.sum()) else float("nan")
            nuestro = evaluate_study(pred, gt_crudo, suv, ml, exclude_blank=False)
            filas_of.append(dict(estudio=est, brazo=brazo, positivo=bool(gt_crudo.any()),
                                 dice_oficial=d_of, dice_nuestro=nuestro["dice"],
                                 fpv_oficial=fp_of, fpv_nuestro=nuestro["fpv_ml"],
                                 fnv_oficial=fn_of, fnv_nuestro=nuestro["fnv_ml"]))
        pickle.dump((filas_hd, filas_suv, filas_of, filas_cl), open(cache / f"{est}.pkl", "wb"))
        print(f"[ok] {est}", flush=True)

    # todos los estudios listos: juntar
    todo = [pickle.load(open(cache / f"{f.stem.split('__')[0]}.pkl", "rb")) for f in files]
    H, S, O, C = ([r for t in todo for r in t[i]] for i in range(4))
    sufijo = a.particion
    pd.DataFrame(C).to_csv(out_dir / f"clasicas_{sufijo}.csv", index=False)
    if not a.solo_clasica:
        pd.DataFrame(H).to_csv(out_dir / f"hd95_{sufijo}.csv", index=False)
        pd.DataFrame(S).to_csv(out_dir / f"suvmax_{sufijo}.csv", index=False)
        pd.DataFrame(O).to_csv(out_dir / f"contraste_oficial_{sufijo}.csv", index=False)
    print("listo", flush=True)

if __name__ == "__main__":
    main()
