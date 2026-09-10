"""Pruebas del Paso 5a: agrupación de etiquetas de TotalSegmentator y reparto de errores por
órgano. No se corre TotalSegmentator (pesa 1 GB): se fabrica un mapa de etiquetas sintético
con su tabla de clases y se verifica la aritmética."""
import sys
from pathlib import Path

import numpy as np
import pytest
import SimpleITK as sitk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from petct.organs import (GROUP_CODE, GROUP_NAMES, fn_by_organ, fp_by_organ, group_labels,  # noqa: E402
                          label_to_group_table, lesion_by_organ, organs_to_grid)

CLASS_MAP = {1: "spleen", 2: "kidney_right", 3: "kidney_left", 5: "liver", 6: "stomach", 19: "small_bowel",
             20: "colon", 21: "urinary_bladder", 51: "heart", 26: "vertebrae_L1", 90: "brain", 4: "gallbladder"}


def test_tabla_de_grupos():
    t = label_to_group_table(CLASS_MAP)
    assert t[5] == GROUP_CODE["higado"]
    assert t[2] == t[3] == GROUP_CODE["rinones"]
    assert t[19] == t[20] == GROUP_CODE["intestino"]
    assert t[26] == GROUP_CODE["hueso"]              # vertebrae_* por prefijo
    assert t[4] == GROUP_CODE["otros_organos"]       # gallbladder no tiene grupo propio
    assert t[0] == GROUP_CODE["fuera"]
    assert GROUP_NAMES[0] == "fuera" and GROUP_NAMES[1] == "otro"


def test_group_labels_cuerpo_sin_etiqueta_es_otro():
    ts = np.zeros((4, 4, 4), np.uint8); ts[1, 1, 1] = 5
    body = np.zeros((4, 4, 4), bool); body[:, :, :2] = True
    g = group_labels(ts, CLASS_MAP, body)
    assert g[1, 1, 1] == GROUP_CODE["higado"]
    assert g[0, 0, 0] == GROUP_CODE["otro"]          # cuerpo sin etiqueta
    assert g[0, 0, 3] == GROUP_CODE["fuera"]         # fuera del cuerpo


def test_reparto_fp_fn_por_organo():
    shape = (10, 10, 10); ml = 0.1
    groups = np.full(shape, GROUP_CODE["otro"], np.uint8)
    groups[0:5] = GROUP_CODE["higado"]; groups[5:] = GROUP_CODE["rinones"]
    gt = np.zeros(shape, bool); gt[6:8, 6:8, 6:8] = True          # lesión de 8 vóxeles en 'riñones'
    gt[1:3, 1:3, 1:3] = True                                      # lesión de 8 vóxeles en 'hígado'
    pred = np.zeros(shape, bool)
    pred[6:8, 6:8, 6:8] = True                                    # acierta la del riñón
    pred[0:2, 6:9, 6:9] = True                                    # inventa 18 vóxeles en hígado (no toca lesión)
    fp = fp_by_organ(pred, gt, groups, ml); fn = fn_by_organ(pred, gt, groups, ml); les = lesion_by_organ(gt, groups, ml)
    assert abs(fp["higado"] - 1.8) < 1e-9 and fp["rinones"] == 0.0
    assert abs(fn["higado"] - 0.8) < 1e-9 and fn["rinones"] == 0.0   # la lesión hepática no fue tocada
    assert abs(les["higado"] - 0.8) < 1e-9 and abs(les["rinones"] - 0.8) < 1e-9
    assert abs(sum(fp.values()) - 1.8) < 1e-9                         # la suma es el FPV


def test_organs_to_grid_alinea_con_preprocesamiento():
    """Un mapa de órganos en una grilla fina del CT termina en la grilla de 3 mm con el recorte."""
    from petct.preprocess import resample_iso
    ref = sitk.Image(20, 20, 10, sitk.sitkFloat32); ref.SetSpacing((2.0, 2.0, 3.0)); ref.SetOrigin((-20, -20, 0))
    ct = sitk.Image(40, 40, 30, sitk.sitkUInt8); ct.SetSpacing((1.0, 1.0, 1.0)); ct.SetOrigin((-20, -20, 0))
    arr = sitk.GetArrayFromImage(ct); arr[:, :, :20] = 5; arr[:, :, 20:] = 2      # mitad hígado, mitad riñón
    org = sitk.GetImageFromArray(arr); org.CopyInformation(ct)
    iso_ref = resample_iso(ref, (3.0, 3.0, 3.0))
    full = organs_to_grid(org, ref, (3.0, 3.0, 3.0))
    assert full.shape == sitk.GetArrayFromImage(iso_ref).shape
    bbox = np.array([[1, 5], [2, 9], [0, 12]])
    crop = organs_to_grid(org, ref, (3.0, 3.0, 3.0), bbox)
    assert crop.shape == (4, 7, 12)
    assert set(np.unique(crop)) <= {0, 2, 5}
    assert (crop[..., :5] == 5).mean() > 0.9 and (crop[..., -4:] == 2).mean() > 0.9


def test_referencia_interna_usa_el_higado_y_cae_a_los_vasos():
    """La referencia de Deauville sale del hígado del propio paciente; si no hay hígado
    utilizable, baja al fondo vascular, y nunca devuelve un valor de una zona excluida."""
    from petct.organs import GROUP_CODE, internal_reference, MIN_VOXELES_REF

    shape = (20, 20, 20)
    groups = np.full(shape, GROUP_CODE["otro"], np.uint8)
    groups[:10] = GROUP_CODE["higado"]
    groups[10:15] = GROUP_CODE["vasos"]
    suv = np.zeros(shape, np.float32)
    suv[groups == GROUP_CODE["higado"]] = 2.5
    suv[groups == GROUP_CODE["vasos"]] = 1.7
    suv[groups == GROUP_CODE["otro"]] = 0.8
    valido = np.ones(shape, bool)

    v, origen = internal_reference(suv, groups, valido)
    assert origen == "higado" and abs(v - 2.5) < 1e-5

    # Con el hígado casi todo excluido (por ejemplo, ocupado por lesión) baja a los vasos.
    sin_higado = valido.copy()
    sin_higado[groups == GROUP_CODE["higado"]] = False
    v, origen = internal_reference(suv, groups, sin_higado)
    assert origen == "vasos" and abs(v - 1.7) < 1e-5

    # Un hígado más chico que el mínimo tampoco se usa.
    chico = np.full(shape, GROUP_CODE["otro"], np.uint8)
    chico.reshape(-1)[:MIN_VOXELES_REF - 1] = GROUP_CODE["higado"]
    valor, origen = internal_reference(suv, chico, valido)
    assert origen != "higado"

    # Sin nada válido, NaN en vez de una división por cero más adelante.
    valor, origen = internal_reference(suv, groups, np.zeros(shape, bool))
    assert np.isnan(valor) and origen == "ninguna"
