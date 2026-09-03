"""El manifiesto .tcia se lee y se escribe sin perder UIDs."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from petct.tcia import read_tcia_manifest, write_tcia_manifest  # noqa: E402


def test_manifiesto_ida_y_vuelta(tmp_path):
    uids = ["1.2.840.1", "1.2.840.2", "1.2.840.3"]
    p = write_tcia_manifest(uids, tmp_path / "x.tcia")
    text = p.read_text()
    assert text.startswith("downloadServerUrl=") and "ListOfSeriesToDownload=" in text
    assert read_tcia_manifest(p) == uids
