"""Geometría de series: orden por posición, espaciado efectivo, relación de aspecto."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from petct.geometry import series_geometry, index_to_mm, measurement_error_if_aspect_ignored  # noqa: E402
import synthetic  # noqa: E402


def test_geometria_del_fantoma(tmp_path):
    synthetic.make_phantom(tmp_path)
    g = series_geometry(tmp_path / "PT")
    assert g["n_slices"] == synthetic.PET_SHAPE[0]
    assert g["uniform"] and abs(g["gap_mean_mm"] - synthetic.PET_SP[0]) < 1e-9
    assert abs(g["slice_thickness_mm"] - synthetic.PET_SP[0]) < 1e-9
    assert g["row_spacing_mm"] == synthetic.PET_SP[1]
    assert g["normal"] == [0.0, 0.0, 1.0]        # axial, z hacia la cabeza
    assert g["order_by_name_ok"]                  # los nombres del fantoma sí están ordenados


def test_orden_alfabetico_no_es_anatomico(tmp_path):
    """Renombramos los cortes con nombres desordenados: la geometría debe ordenarlos igual."""
    synthetic.make_phantom(tmp_path)
    folder = tmp_path / "CT"
    files = sorted(folder.iterdir())
    for k, f in enumerate(files):                 # nombre "al revés" del orden anatómico
        f.rename(folder / f"z_{len(files) - k:03d}.dcm")
    g = series_geometry(folder)
    assert not g["order_by_name_ok"]
    assert g["uniform"] and abs(g["gap_mean_mm"] - synthetic.CT_SP[0]) < 1e-9
    assert g["positions_sorted_mm"][0] == synthetic.ORIGIN[2]


def test_ecuacion_image_plane():
    p = index_to_mm(2, 3, 4, origin=(-100, -100, 0), row_sp=2.0, col_sp=2.0,
                    col_dir=(1, 0, 0), row_dir=(0, 1, 0), normal=(0, 0, 1), slice_sp=3.0)
    assert np.allclose(p, [-100 + 3 * 2, -100 + 2 * 2, 4 * 3])


def test_error_de_aspecto():
    # segmento vertical: si el vóxel es 3 mm de alto y se dibuja como 1 mm, se "acorta" 3 veces
    assert abs(measurement_error_if_aspect_ignored(30, 90, 1.0, 3.0) + 2 / 3) < 1e-9
    # segmento horizontal: sin error
    assert abs(measurement_error_if_aspect_ignored(30, 0, 1.0, 3.0)) < 1e-9
