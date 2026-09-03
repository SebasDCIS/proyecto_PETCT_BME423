"""Fantoma DICOM sintético (CT + PT + SEG) para probar la conversión sin datos reales.

Un cuerpo elíptico de agua con una "lesión" esférica caliente. El PET tiene una
grilla más gruesa que el CT, como en la realidad, para probar CTres y SEG.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

# geometría
CT_SHAPE, CT_SP = (20, 64, 64), (2.0, 2.0, 2.0)      # (z, y, x), mm
PET_SHAPE, PET_SP = (20, 32, 32), (2.0, 4.0, 4.0)
ORIGIN = (-64.0, -64.0, 0.0)                       # x, y, z del primer vóxel (mm)
LESION_CENTER_MM, LESION_R_MM = (10.0, -6.0, 20.0), 9.0

# parámetros SUV
WEIGHT_KG, DOSE_BQ, HALF_LIFE_S = 70.0, 300e6, 6586.2
INJ_TIME, SCAN_TIME = "100000", "110000"             # 60 min de decaimiento


def expected_suv_factor() -> float:
    decayed = DOSE_BQ * 2 ** (-(3600.0) / HALF_LIFE_S)
    return WEIGHT_KG * 1000.0 / decayed


def _grid(shape, sp):
    z = ORIGIN[2] + np.arange(shape[0]) * sp[0]
    y = ORIGIN[1] + np.arange(shape[1]) * sp[1]
    x = ORIGIN[0] + np.arange(shape[2]) * sp[2]
    return np.meshgrid(z, y, x, indexing="ij")


def _lesion_mask(shape, sp):
    Z, Y, X = _grid(shape, sp)
    cx, cy, cz = LESION_CENTER_MM
    return ((X - cx) ** 2 + (Y - cy) ** 2 + (Z - cz) ** 2) <= LESION_R_MM ** 2


def _body_mask(shape, sp):
    Z, Y, X = _grid(shape, sp)
    return (X / 50.0) ** 2 + (Y / 40.0) ** 2 <= 1.0


def _base_ds(path: Path, modality: str, sop_class: str) -> FileDataset:
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = sop_class
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID, ds.SOPInstanceUID = sop_class, meta.MediaStorageSOPInstanceUID
    ds.PatientName, ds.PatientID = "FANTOMA^SINTETICO", "PETCT_0000"
    ds.PatientWeight = WEIGHT_KG
    ds.Modality = modality
    ds.StudyDate = ds.SeriesDate = "20260903"
    ds.StudyTime = ds.SeriesTime = SCAN_TIME
    ds.ImageOrientationPatient = [1, 0, 0, 0, 1, 0]
    return ds


def write_series(out: Path, modality: str, arr: np.ndarray, sp, study_uid, series_uid,
                 slope=1.0, intercept=0.0, extra=None):
    out.mkdir(parents=True, exist_ok=True)
    sop_class = {"CT": "1.2.840.10008.5.1.4.1.1.2", "PT": "1.2.840.10008.5.1.4.1.1.128"}[modality]
    n = arr.shape[0]
    for k in range(n):
        ds = _base_ds(out / f"{modality}_{k:03d}.dcm", modality, sop_class)
        ds.StudyInstanceUID, ds.SeriesInstanceUID = study_uid, series_uid
        ds.InstanceNumber = k + 1
        ds.Rows, ds.Columns = arr.shape[1], arr.shape[2]
        ds.PixelSpacing = [sp[1], sp[2]]
        ds.SliceThickness = sp[0]
        ds.ImagePositionPatient = [ORIGIN[0], ORIGIN[1], ORIGIN[2] + k * sp[0]]
        ds.SamplesPerPixel, ds.PhotometricInterpretation = 1, "MONOCHROME2"
        ds.BitsAllocated = ds.BitsStored = 16
        ds.HighBit, ds.PixelRepresentation = 15, 1
        ds.RescaleSlope, ds.RescaleIntercept = slope, intercept
        stored = np.round((arr[k] - intercept) / slope).astype(np.int16)
        ds.PixelData = stored.tobytes()
        if extra:
            extra(ds)
        ds.save_as(str(ds.filename), enforce_file_format=True)


def _pet_tags(ds):
    ds.Units = "BQML"
    ds.DecayCorrection = "START"
    ds.AcquisitionTime = SCAN_TIME
    rps = Dataset()
    rps.RadionuclideTotalDose = DOSE_BQ
    rps.RadionuclideHalfLife = HALF_LIFE_S
    rps.RadiopharmaceuticalStartTime = INJ_TIME
    ds.RadiopharmaceuticalInformationSequence = Sequence([rps])


def write_seg(out: Path, mask: np.ndarray, sp, study_uid, series_uid):
    """Escribe un DICOM SEG binario mínimo (un frame por corte con lesión)."""
    out.mkdir(parents=True, exist_ok=True)
    ds = _base_ds(out / "SEG.dcm", "SEG", "1.2.840.10008.5.1.4.1.1.66.4")
    ds.StudyInstanceUID, ds.SeriesInstanceUID = study_uid, series_uid
    ds.SegmentationType = "BINARY"
    ds.SamplesPerPixel, ds.PhotometricInterpretation = 1, "MONOCHROME2"
    ds.BitsAllocated = ds.BitsStored = 1
    ds.HighBit, ds.PixelRepresentation = 0, 0
    ds.Rows, ds.Columns = mask.shape[1], mask.shape[2]
    # deliberadamente en orden inverso, para probar que se usa la posición y no el índice
    frames = [k for k in range(mask.shape[0]) if mask[k].any()][::-1]
    ds.NumberOfFrames = len(frames)
    pffg = []
    for k in frames:
        fg = Dataset()
        pp = Dataset()
        pp.ImagePositionPatient = [ORIGIN[0], ORIGIN[1], ORIGIN[2] + k * sp[0]]
        fg.PlanePositionSequence = Sequence([pp])
        pffg.append(fg)
    ds.PerFrameFunctionalGroupsSequence = Sequence(pffg)
    bits = np.stack([mask[k] for k in frames]).astype(np.uint8)
    ds.PixelData = np.packbits(bits.reshape(-1), bitorder="little").tobytes()
    ds.save_as(str(ds.filename), enforce_file_format=True)


def make_phantom(root: Path) -> dict:
    """Crea root/CT, root/PT, root/SEG. Devuelve las verdades para los tests."""
    study_uid = generate_uid()
    body_ct = _body_mask(CT_SHAPE, CT_SP)
    ct = np.where(body_ct, 40.0, -1000.0)                 # tejido blando / aire
    ct[_lesion_mask(CT_SHAPE, CT_SP)] = 60.0
    write_series(root / "CT", "CT", ct, CT_SP, study_uid, generate_uid(), 1.0, -1024.0)

    body_pet = _body_mask(PET_SHAPE, PET_SP)
    les_pet = _lesion_mask(PET_SHAPE, PET_SP)
    f = expected_suv_factor()
    pet = np.zeros(PET_SHAPE)
    pet[body_pet] = 1.0 / f          # SUV 1 de fondo
    pet[les_pet] = 8.0 / f           # SUV 8 en la lesión
    write_series(root / "PT", "PT", pet, PET_SP, study_uid, generate_uid(),
                 slope=max(pet.max() / 30000.0, 1e-9), intercept=0.0, extra=_pet_tags)
    write_seg(root / "SEG", les_pet, PET_SP, study_uid, generate_uid())
    return {"lesion_pet": les_pet, "body_pet": body_pet, "suv_factor": f}
