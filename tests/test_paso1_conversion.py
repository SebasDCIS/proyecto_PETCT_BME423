"""Pruebas del Paso 1: SUV y conversión DICOM → NIfTI, con un fantoma sintético."""
import sys
from pathlib import Path

import numpy as np
import pytest
import SimpleITK as sitk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from petct.suv import SUVParams, parse_dicom_time, suv_params_from_dataset  # noqa: E402
from petct.convert import convert_study  # noqa: E402
import synthetic  # noqa: E402


def test_suv_factor_aritmetica():
    p = SUVParams(70.0, 300e6, 6586.2, parse_dicom_time("100000"), parse_dicom_time("110000"))
    assert abs(p.decay_time_s - 3600) < 1e-6
    # tras 60 min queda 2^(-3600/6586.2) ≈ 68.5 % de la dosis
    assert abs(p.decayed_dose_bq / 300e6 - 0.6847) < 1e-3
    assert abs(p.scale_factor - synthetic.expected_suv_factor()) < 1e-9


def test_cruce_de_medianoche():
    p = SUVParams(70.0, 300e6, 6586.2, parse_dicom_time("235000"), parse_dicom_time("003000"))
    assert abs(p.decay_time_s - 2400) < 1e-6


def test_parse_time_fraccional():
    t = parse_dicom_time("101530.250000")
    assert (t.hour, t.minute, t.second, t.microsecond) == (10, 15, 30, 250000)


@pytest.fixture(scope="module")
def phantom(tmp_path_factory):
    root = tmp_path_factory.mktemp("estudio")
    truth = synthetic.make_phantom(root)
    out = convert_study(root, root / "nifti")
    return root, truth, out


def test_params_desde_dicom(phantom):
    import pydicom
    root, truth, _ = phantom
    ds = pydicom.dcmread(str(sorted((root / "PT").iterdir())[0]), stop_before_pixels=True)
    p = suv_params_from_dataset(ds)
    assert abs(p.scale_factor - truth["suv_factor"]) < 1e-9


def test_archivos_generados(phantom):
    _, _, out = phantom
    assert set(out) == {"CT", "PET", "SUV", "CTres", "SEG"}
    for p in out.values():
        assert p.exists() and p.stat().st_size > 0


def test_suv_en_lesion_y_fondo(phantom):
    _, truth, out = phantom
    suv = sitk.GetArrayFromImage(sitk.ReadImage(str(out["SUV"])))
    assert suv.shape == synthetic.PET_SHAPE
    # la lesión debe estar ~8 y el fondo ~1 (tolerancia por cuantización a int16)
    assert abs(np.median(suv[truth["lesion_pet"]]) - 8.0) < 0.05
    fondo = truth["body_pet"] & ~truth["lesion_pet"]
    assert abs(np.median(suv[fondo]) - 1.0) < 0.05


def test_ctres_en_grilla_pet(phantom):
    _, truth, out = phantom
    ctres = sitk.ReadImage(str(out["CTres"]))
    pet = sitk.ReadImage(str(out["PET"]))
    assert ctres.GetSize() == pet.GetSize()
    assert np.allclose(ctres.GetSpacing(), pet.GetSpacing())
    arr = sitk.GetArrayFromImage(ctres)
    # dentro del cuerpo el CT remuestreado debe ser tejido blando (~40–60 HU), fuera aire
    assert 30 < np.median(arr[truth["body_pet"]]) < 70
    assert np.median(arr[~truth["body_pet"]]) < -900


def test_seg_coincide_con_lesion(phantom):
    _, truth, out = phantom
    seg = sitk.GetArrayFromImage(sitk.ReadImage(str(out["SEG"]))).astype(bool)
    assert seg.shape == truth["lesion_pet"].shape
    inter = (seg & truth["lesion_pet"]).sum()
    dice = 2 * inter / (seg.sum() + truth["lesion_pet"].sum())
    assert dice > 0.999, f"Dice SEG vs verdad = {dice:.4f}"


def test_seg_orientacion_normal_e_invertida(tmp_path):
    """La máscara debe ser la misma con filas normales y con filas invertidas (autoPET)."""
    res = {}
    for flip in (False, True):
        root = tmp_path / f"flip_{flip}"
        truth = synthetic.make_phantom(root, seg_flip_rows=flip)
        out = convert_study(root, root / "nifti")
        seg = sitk.GetArrayFromImage(sitk.ReadImage(str(out["SEG"]))).astype(bool)
        inter = (seg & truth["lesion_pet"]).sum()
        res[flip] = 2 * inter / (seg.sum() + truth["lesion_pet"].sum())
    assert res[False] > 0.999 and res[True] > 0.999, res
