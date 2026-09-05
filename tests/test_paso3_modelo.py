"""Pruebas del Paso 3: dataset de parches, modelo A, bucle de entrenamiento e inferencia.

Todo corre en CPU con la red chica y parches de 32³ sobre el fantoma sintético; tarda
menos de un minuto. Lo que se verifica no es que la red aprenda bien (para eso están
los datos reales) sino que las piezas encajan: formas de tensores, muestreo sesgado,
que la pérdida baje en unas decenas de pasos, que el checkpoint se guarde y se reanude,
y que la ventana deslizante devuelva una máscara del tamaño del estudio.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from petct.convert import convert_study  # noqa: E402
from petct.data import PatchDataset, VolumeDataset, patch_positive_fraction, split_files  # noqa: E402
from petct.infer import evaluate_files, predict_volume, summarize  # noqa: E402
from petct.models import build_model, count_parameters, logits_to_mask  # noqa: E402
from petct.preprocess import preprocess_study  # noqa: E402
from petct.train import TrainConfig, poly_lr, train  # noqa: E402
import synthetic  # noqa: E402

PATCH = (32, 32, 32)


@pytest.fixture(scope="module")
def datos(tmp_path_factory):
    """Dos copias del fantoma preprocesado (una 'train', otra 'val') y su manifiesto."""
    root = tmp_path_factory.mktemp("p3")
    synthetic.make_phantom(root / "dicom")
    convert_study(root / "dicom", root / "nifti")
    proc = root / "processed"
    filas = []
    for pid, split in (("FANTOMA_a", "train"), ("FANTOMA_b", "train"), ("FANTOMA_c", "val")):
        f = proc / f"{pid}__1.2.3.npz"
        preprocess_study(root / "nifti", f, spacing=(3.0, 3.0, 3.0))
        filas.append({"patient_id": pid, "study_uid": "1.2.3", "diagnosis": "X", "split": split})
    filas.append({"patient_id": "FANTOMA_faltante", "study_uid": "9.9.9", "diagnosis": "X", "split": "test"})
    man = root / "subconjunto.csv"
    pd.DataFrame(filas).to_csv(man, index=False)
    return root, man, proc


# ---------------------------------------------------------------- particiones
def test_split_files(datos):
    _, man, proc = datos
    s = split_files(man, proc)
    assert len(s["train"]) == 2 and len(s["val"]) == 1
    assert "test" not in s            # el estudio sin .npz se omite, no rompe
    assert split_files(man, proc, "val")[0].name.startswith("FANTOMA_c")


# ---------------------------------------------------------------- dataset
def test_patch_dataset_formas_y_sesgo(datos):
    _, man, proc = datos
    ds = PatchDataset(split_files(man, proc, "train"), PATCH, p_lesion=1.0, length=20, seed=1)
    x, y = ds[0]
    assert x.shape == (2,) + PATCH and x.dtype == torch.float32
    assert y.shape == (1,) + PATCH and y.dtype == torch.int64
    assert 0.0 <= float(x.min()) and float(x.max()) <= 1.0
    assert patch_positive_fraction(ds, 10) == 1.0        # con p_lesion = 1 todos traen lesión
    # sin sesgo, no todos los parches traen lesión (parche chico: el fantoma mide ~13×43×43)
    ds0 = PatchDataset(split_files(man, proc, "train"), (8, 8, 8), p_lesion=0.0, length=20, seed=1, augment=False)
    assert patch_positive_fraction(ds0, 20) < 1.0


def test_volume_dataset(datos):
    _, man, proc = datos
    vd = VolumeDataset(split_files(man, proc, "val"))
    x, y, meta = vd[0]
    assert x.shape[0] == 2 and x.shape[1:] == y.shape[1:]
    assert meta["patient_id"] == "FANTOMA_c" and abs(meta["ml_per_voxel"] - 0.027) < 1e-9


# ---------------------------------------------------------------- modelo
def test_modelo_a_forma():
    m = build_model("A", small=True)
    x = torch.zeros(1, 2, *PATCH)
    out = m(x)
    assert out.shape == (1, 2, *PATCH)
    assert logits_to_mask(out).shape == (1, 1, *PATCH)
    assert count_parameters(m) > 1e5
    assert count_parameters(build_model("A")) > count_parameters(m)


def test_modelo_desconocido():
    with pytest.raises(NotImplementedError):
        build_model("Z")


@pytest.mark.parametrize("nombre", ["B", "C"])
def test_modelos_b_c_forma_y_gradiente(nombre):
    m = build_model(nombre, small=True)
    x = torch.rand(2, 2, *PATCH)
    out = m(x)
    assert out.shape == (2, 2, *PATCH)
    out.mean().backward()
    assert all(p.grad is not None for p in m.parameters() if p.requires_grad)
    # B y C solo difieren en el bloque de atención: C tiene más parámetros, pero poco
    nb, nc = count_parameters(build_model("B", small=True)), count_parameters(m if nombre == "C" else build_model("C", small=True))
    assert 0 < nc - nb < 0.1 * nb


def test_atencion_cruzada_pesos_suman_uno():
    from petct.models import CrossAttentionFusion, sincos_pos_3d
    blk = CrossAttentionFusion(64, heads=4)
    pet, ct = torch.randn(1, 64, 3, 4, 5), torch.randn(1, 64, 3, 4, 5)
    fused = blk(pet, ct)
    assert fused.shape == pet.shape
    assert torch.allclose(fused, pet)          # gamma parte en 0: al inicio C se comporta como B
    w = blk.attention_maps(pet, ct)
    assert w.shape == (1, 60, 60) and torch.allclose(w.sum(-1), torch.ones(1, 60), atol=1e-5)
    pe = sincos_pos_3d((3, 4, 5), 64, "cpu", torch.float32)
    assert pe.shape == (60, 64) and not torch.allclose(pe[0], pe[1])   # posiciones distintas, códigos distintos


@pytest.mark.parametrize("nombre", ["B", "C"])
def test_entrenar_b_c_corto(datos, tmp_path, nombre):
    _, man, proc = datos
    s = split_files(man, proc)
    cfg = TrainConfig(modelo=nombre, iteraciones=12, lote=2, lr=1e-3, precision_mixta=False,
                      checkpoint_cada=6, validar_cada=12, max_estudios_val=1, parche=PATCH,
                      prob_parche_con_lesion=0.9, semilla=1, workers=0, small=True, log_cada=4)
    r = train(cfg, s["train"], s["val"], tmp_path / nombre, torch.device("cpu"), verbose=False)
    assert r["iteraciones_hechas"] == 12 and (tmp_path / nombre / "mejor.pt").exists()
    log = pd.read_csv(tmp_path / nombre / "log_entrenamiento.csv")
    assert log["loss"].iloc[-1] < log["loss"].iloc[0]


def test_poly_lr():
    assert poly_lr(1.0, 0, 100) == 1.0
    assert 0.0 < poly_lr(1.0, 99, 100) < 0.05
    assert poly_lr(1.0, 50, 100) < poly_lr(1.0, 10, 100)


# ---------------------------------------------------------------- entrenamiento
def test_entrenar_reanudar_y_evaluar(datos, tmp_path):
    root, man, proc = datos
    s = split_files(man, proc)
    cfg = TrainConfig(modelo="A", iteraciones=30, lote=2, lr=1e-3, precision_mixta=False,
                      checkpoint_cada=10, validar_cada=15, max_estudios_val=1, parche=PATCH,
                      prob_parche_con_lesion=0.9, semilla=1, workers=0, small=True, log_cada=5)
    out = tmp_path / "run"
    r = train(cfg, s["train"], s["val"], out, torch.device("cpu"), verbose=False)
    assert r["iteraciones_hechas"] == 30
    assert (out / "ultimo.pt").exists() and (out / "mejor.pt").exists()
    log = pd.read_csv(out / "log_entrenamiento.csv")
    assert log["iter"].iloc[-1] == 30
    assert log["loss"].iloc[-1] < log["loss"].iloc[0]          # la pérdida baja
    val = pd.read_csv(out / "validacion.csv")
    assert list(val["iter"]) == [15, 30]

    # reanudar: pedir 40 iteraciones debe continuar desde la 30, no empezar de cero
    cfg2 = TrainConfig(**{**cfg.__dict__, "iteraciones": 40})
    r2 = train(cfg2, s["train"], s["val"], out, torch.device("cpu"), verbose=False)
    assert r2["iteraciones_hechas"] == 40
    log2 = pd.read_csv(out / "log_entrenamiento.csv")
    assert log2["iter"].iloc[-1] == 40 and (log2["iter"] == 30).sum() == 1

    # inferencia sobre el estudio completo
    model = build_model("A", small=True)
    ck = torch.load(out / "mejor.pt", map_location="cpu", weights_only=False)
    model.load_state_dict(ck["model"])
    vd = VolumeDataset(s["val"])
    x, y, meta = vd[0]
    mask = predict_volume(model, x, torch.device("cpu"), roi=PATCH)
    assert mask.shape == tuple(y.shape[1:]) and mask.dtype == np.uint8
    df = evaluate_files(model, s["val"], torch.device("cpu"), roi=PATCH, variante="prueba")
    assert set(["dice", "fpv_ml", "fnv_ml", "estudio", "variante"]) <= set(df.columns)
    res = summarize(df)
    assert res["n"] == 1 and res["n_pos"] == 1
