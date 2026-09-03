"""Pruebas del Paso 2: preprocesamiento, parches, métricas y referencia clásica."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from petct.convert import convert_study  # noqa: E402
from petct.preprocess import (load_study, preprocess_study, sample_patch,  # noqa: E402
                              scale_suv, window_ct)
from petct.metrics import dice, evaluate_study, false_negative_volume, false_positive_volume  # noqa: E402
from petct.classical import classical_segmentation, clean_mask, heuristic_organ_masks  # noqa: E402
import synthetic  # noqa: E402


# ---------------------------------------------------------------- escalado
def test_ventana_ct():
    hu = np.array([-1000.0, -200.0, 50.0, 300.0, 1500.0])
    out = window_ct(hu, -200, 300)
    assert np.allclose(out, [0.0, 0.0, 0.5, 1.0, 1.0])


def test_escala_suv():
    assert np.allclose(scale_suv(np.array([0.0, 2.5, 30.0, 80.0]), 30.0), [0, 2.5 / 30, 1, 1])


# ---------------------------------------------------------------- métricas en casos de juguete
def test_metricas_juguete():
    gt = np.zeros((10, 10, 10), bool)
    gt[2:5, 2:5, 2:5] = True          # lesión 1: 27 vóxeles
    gt[7:9, 7:9, 7:9] = True          # lesión 2: 8 vóxeles
    pred = np.zeros_like(gt)
    pred[2:5, 2:5, 2:5] = True        # acierta la lesión 1
    pred[0:2, 8:10, 0:2] = True       # inventa una componente de 8 vóxeles
    ml = 0.1
    assert abs(dice(pred, gt) - 2 * 27 / (35 + 35)) < 1e-9
    assert abs(false_positive_volume(pred, gt, ml) - 0.8) < 1e-9
    assert abs(false_negative_volume(pred, gt, ml) - 0.8) < 1e-9
    assert np.isnan(dice(np.zeros_like(gt), np.zeros_like(gt)))


# ---------------------------------------------------------------- fantoma completo
@pytest.fixture(scope="module")
def procesado(tmp_path_factory):
    root = tmp_path_factory.mktemp("p2")
    truth = synthetic.make_phantom(root)
    convert_study(root, root / "nifti")
    info = preprocess_study(root / "nifti", root / "proc" / "fantoma.npz", spacing=(3.0, 3.0, 3.0))
    vol = load_study(root / "proc" / "fantoma.npz")
    return truth, info, vol


def test_forma_y_espaciado(procesado):
    _, info, vol = procesado
    assert vol["suv"].shape == vol["ct"].shape == vol["seg"].shape
    assert abs(info["ml_per_voxel"] - 0.027) < 1e-9
    # el fantoma mide 128 x 128 x 40 mm; el recorte al cuerpo debe dejar menos que eso
    assert vol["suv"].shape[1] < 128 / 3 and vol["suv"].shape[2] < 128 / 3


def test_cuerpo_cubre_lesion(procesado):
    _, _, vol = procesado
    assert vol["body"][vol["seg"] > 0].all()
    assert 0.3 < vol["body"].mean() < 1.0


def test_volumen_lesion_se_conserva(procesado):
    truth, info, vol = procesado
    # esfera de radio 9 mm: 4/3 pi r^3 = 3.05 mL; con vóxeles de 3 mm se tolera 30 %
    ml = vol["seg"].sum() * info["ml_per_voxel"]
    assert 2.0 < ml < 4.2


def test_parche_con_lesion(procesado):
    _, _, vol = procesado
    rng = np.random.default_rng(0)
    p = sample_patch(vol, size=(16, 16, 16), p_lesion=1.0, rng=rng)
    assert p["suv"].shape == (16, 16, 16) and p["with_lesion"]
    # parche más grande que el volumen: se rellena con ceros sin fallar
    q = sample_patch(vol, size=(96, 96, 96), p_lesion=0.0, rng=rng)
    assert q["suv"].shape == (96, 96, 96)


def test_referencia_clasica_recupera_esfera(procesado):
    _, info, vol = procesado
    suv_real = vol["suv"] * vol["suv_top"]
    pred = classical_segmentation(suv_real, vol["body"], info["ml_per_voxel"])
    m = evaluate_study(pred, vol["seg"], suv_real, info["ml_per_voxel"])
    assert m["dice"] > 0.8, m
    assert m["fpv_ml"] == 0.0 and m["fnv_ml"] == 0.0
    assert 7.0 < m["suvmax_pred"] < 9.0


def test_limpieza_elimina_puntos():
    mask = np.zeros((20, 20, 20), bool)
    mask[5:12, 5:12, 5:12] = True     # bloque grande
    mask[15, 15, 15] = True           # punto suelto
    out = clean_mask(mask, open_radius=1, min_ml=0.5, ml_per_voxel=0.027)
    assert out[8, 8, 8] and not out[15, 15, 15]


def _paciente(head_at_end):
    """Cilindro con 'encéfalo' grande y 'vejiga' intensa; la cabeza al principio o al final."""
    Z, Y, X = 200, 60, 60
    zz, yy, xx = np.mgrid[:Z, :Y, :X]
    body = ((yy - 30) / 27) ** 2 + ((xx - 30) / 27) ** 2 <= 1
    suv = np.where(body, 1.0, 0.0)
    z_head, z_bladder = (185, 30) if head_at_end else (15, 170)
    brain = (zz - z_head) ** 2 + (yy - 30) ** 2 + (xx - 30) ** 2 <= 14 ** 2
    bladder = (zz - z_bladder) ** 2 + (yy - 30) ** 2 + (xx - 30) ** 2 <= 8 ** 2
    suv[brain] = 7.0
    suv[bladder] = 25.0
    return suv, body, brain, bladder


@pytest.mark.parametrize("head_at_end", [True, False])
def test_heuristicas_respetan_orientacion(head_at_end):
    suv, body, brain, bladder = _paciente(head_at_end)
    org = heuristic_organ_masks(suv, body, 0.027, head_at_end=head_at_end)
    assert "encefalo" in org and "vejiga" in org, org.keys()
    assert (org["encefalo"] & brain).sum() / brain.sum() > 0.95
    assert (org["vejiga"] & bladder).sum() / bladder.sum() > 0.95
    assert not (org["encefalo"] & bladder).any()
