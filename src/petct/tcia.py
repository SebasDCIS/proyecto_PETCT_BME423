"""Selección reproducible del subconjunto de autoPET y descarga desde TCIA.

Por qué un subconjunto: la colección completa pesa 419 GB (1 014 estudios). El
proyecto usa 250 estudios elegidos con semilla fija, estratificados por
diagnóstico, y particionados POR PACIENTE (un paciente nunca queda repartido
entre entrenamiento y prueba: sería como estudiar con las respuestas del examen).

La API pública de TCIA (NBIA) no requiere cuenta para colecciones CC BY. Este
módulo usa el paquete `tcia_utils` (pip install tcia_utils) para consultarla.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

COLLECTION = "FDG-PET-CT-Lesions"
DIAG_POS = ("LYMPHOMA", "MELANOMA", "LUNG_CANCER")
DIAG_NEG = "NEGATIVE"


# ---------------------------------------------------------------- clínico → tabla limpia
def _find_col(df: pd.DataFrame, *candidates: str) -> str:
    low = {c.lower().replace(" ", "").replace("_", ""): c for c in df.columns}
    for cand in candidates:
        key = cand.lower().replace(" ", "").replace("_", "")
        if key in low:
            return low[key]
    raise KeyError(f"Ninguna columna entre {candidates} en {list(df.columns)}")


def load_clinical(csv_path: str | Path) -> pd.DataFrame:
    """Lee el CSV clínico de TCIA y devuelve columnas normalizadas:
    patient_id, study_uid (si existe), diagnosis, age, sex."""
    raw = pd.read_csv(csv_path)
    out = pd.DataFrame()
    out["patient_id"] = raw[_find_col(raw, "Subject ID", "PatientID", "patient_id")].astype(str)
    try:
        out["study_uid"] = raw[_find_col(raw, "Study UID", "StudyInstanceUID", "study_uid")].astype(str)
    except KeyError:
        out["study_uid"] = ""
    out["diagnosis"] = raw[_find_col(raw, "diagnosis", "Diagnosis")].astype(str).str.upper().str.strip()
    for name, cands in (("age", ("age", "Age")), ("sex", ("sex", "Sex"))):
        try:
            out[name] = raw[_find_col(raw, *cands)]
        except KeyError:
            out[name] = np.nan
    out["diagnosis"] = out["diagnosis"].str.replace(" ", "_")
    # el CSV de TCIA trae una fila por serie (CT, PT, SEG); nos interesa una por estudio
    return out.drop_duplicates(["patient_id", "study_uid"]).reset_index(drop=True)


# ---------------------------------------------------------------- selección estratificada
def select_subset(clinical: pd.DataFrame, n_positive: int = 200, n_negative: int = 50,
                  seed: int = 423, splits=(0.7, 0.1, 0.2)) -> pd.DataFrame:
    """Elige estudios estratificados por diagnóstico y asigna train/val/test por paciente.

    - Positivos: n_positive repartidos en partes iguales entre los tres diagnósticos.
    - Negativos: n_negative.
    - Un estudio por paciente (el primero en orden de fecha/UID) para evitar fugas.
    """
    rng = np.random.default_rng(seed)
    one_per_patient = (clinical.sort_values(["patient_id", "study_uid"])
                               .drop_duplicates("patient_id", keep="first"))
    chosen: List[pd.DataFrame] = []
    per_diag = int(np.ceil(n_positive / len(DIAG_POS)))
    for d in DIAG_POS:
        pool = one_per_patient[one_per_patient.diagnosis == d]
        k = min(per_diag, len(pool))
        chosen.append(pool.iloc[rng.permutation(len(pool))[:k]])
    pool_neg = one_per_patient[one_per_patient.diagnosis == DIAG_NEG]
    chosen.append(pool_neg.iloc[rng.permutation(len(pool_neg))[:min(n_negative, len(pool_neg))]])
    sub = pd.concat(chosen, ignore_index=True)

    # partición por paciente, estratificada por diagnóstico
    sub["split"] = ""
    for d, grp in sub.groupby("diagnosis"):
        idx = grp.index.to_numpy()
        idx = idx[rng.permutation(len(idx))]
        n = len(idx)
        n_tr = int(round(splits[0] * n))
        n_va = int(round(splits[1] * n))
        sub.loc[idx[:n_tr], "split"] = "train"
        sub.loc[idx[n_tr:n_tr + n_va], "split"] = "val"
        sub.loc[idx[n_tr + n_va:], "split"] = "test"
    sub["seed"] = seed
    return sub.sort_values(["split", "diagnosis", "patient_id"]).reset_index(drop=True)


# ---------------------------------------------------------------- manifiestos .tcia
# Un manifiesto .tcia es un archivo de texto: unas líneas de cabecera y luego un
# SeriesInstanceUID por línea. Es lo que abre el NBIA Data Retriever. TCIA publica uno
# con TODAS las series de la versión "defaced" (la de acceso abierto); de ahí sacamos
# las series de nuestros 250 pacientes y escribimos un manifiesto reducido.
_TCIA_HEADER = (
    "downloadServerUrl=https://nbia.cancerimagingarchive.net/nbia-download/servlet/DownloadServlet\n"
    "includeAnnotation=true\nnoOfrRetry=4\ndatabasketId={name}\nmanifestVersion=3.0\n"
    "ListOfSeriesToDownload=\n"
)


def read_tcia_manifest(path: str | Path) -> List[str]:
    """Devuelve la lista de SeriesInstanceUID de un manifiesto .tcia."""
    uids: List[str] = []
    started = False
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if started and line:
            uids.append(line)
        elif line.startswith("ListOfSeriesToDownload"):
            started = True
    if not uids:
        raise ValueError(f"No se encontraron UIDs en {path}")
    return uids


def write_tcia_manifest(uids: List[str], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_TCIA_HEADER.format(name=path.name) + "\n".join(uids) + "\n")
    return path


def _normalize_series_columns(df: pd.DataFrame) -> pd.DataFrame:
    """La API devuelve nombres de columna distintos según el endpoint; los unificamos."""
    out = pd.DataFrame()
    out["PatientID"] = df[_find_col(df, "PatientID", "Subject ID", "patient_id")].astype(str)
    out["StudyInstanceUID"] = df[_find_col(df, "StudyInstanceUID", "Study UID", "study_uid")].astype(str)
    out["SeriesInstanceUID"] = df[_find_col(df, "SeriesInstanceUID", "Series UID", "Series ID", "series_uid")].astype(str)
    out["Modality"] = df[_find_col(df, "Modality")].astype(str).str.upper()
    for extra in ("SeriesDescription", "Series Description", "ImageCount", "Number of Images", "FileSize", "File Size"):
        if extra in df.columns:
            out[extra.replace(" ", "")] = df[extra]
    return out


def series_from_manifest(manifest_path: str | Path, patient_ids: List[str], chunk: int = 200) -> pd.DataFrame:
    """Cruza el manifiesto oficial (todas las series abiertas) con nuestros pacientes.

    Consulta a NBIA los metadatos de los UIDs del manifiesto por bloques y se queda
    con las series CT, PT y SEG de los pacientes del subconjunto.
    """
    from tcia_utils import nbia  # requiere red

    uids = read_tcia_manifest(manifest_path)
    frames = []
    for i in range(0, len(uids), chunk):
        part = nbia.getSeriesList(uids[i:i + chunk])
        if part is not None and len(part):
            frames.append(part)
    if not frames:
        raise RuntimeError("NBIA no devolvió metadatos para los UIDs del manifiesto")
    df = _normalize_series_columns(pd.concat(frames, ignore_index=True))
    wanted = set(str(p) for p in patient_ids)
    return df[df.PatientID.isin(wanted) & df.Modality.isin(["CT", "PT", "SEG"])].reset_index(drop=True)


# ---------------------------------------------------------------- descarga TCIA
def fetch_series_table(patient_ids: List[str]) -> pd.DataFrame:
    """Consulta a NBIA las series (CT, PT, SEG) de cada paciente del subconjunto."""
    from tcia_utils import nbia  # importación diferida: requiere red

    frames = []
    for pid in patient_ids:
        rows = nbia.getSeries(collection=COLLECTION, patientId=pid, format="df")
        if rows is not None and len(rows):
            frames.append(rows)
    if not frames:
        raise RuntimeError("NBIA no devolvió series; ¿hay red / el ID es correcto?")
    df = _normalize_series_columns(pd.concat(frames, ignore_index=True))
    return df[df["Modality"].isin(["CT", "PT", "SEG"])].reset_index(drop=True)


def download_series(series_df: pd.DataFrame, out_dir: str | Path, max_workers: int = 4):
    """Descarga las series (una carpeta por SeriesInstanceUID) con tcia_utils."""
    from tcia_utils import nbia

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    uids = series_df["SeriesInstanceUID"].tolist()
    return nbia.downloadSeries(uids, input_type="list", path=str(out_dir), format="df",
                               max_workers=max_workers)
