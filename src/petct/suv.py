"""Cálculo del SUV (Standardized Uptake Value) a partir de las etiquetas DICOM de un PET.

Idea en una frase: el scanner entrega actividad en Bq/mL; el SUV la divide por la
"actividad esperada" si la dosis inyectada se hubiera repartido uniformemente en
el cuerpo (dosis / peso). Un SUV de 1 significa "captación promedio"; un SUV de 5
significa "cinco veces el promedio".

    SUVbw = A_vox [Bq/mL] / ( D_corr [Bq] / peso [g] )

donde D_corr es la dosis inyectada corregida por el decaimiento radiactivo entre la
hora de inyección y la hora de adquisición (¹⁸F tiene semivida de ~109.8 min).

Esta implementación sigue la convención del reto autoPET (lab-midas/autoPET) y las
recomendaciones QIBA para PET FDG: unidades BQML, corrección de decaimiento
referida al inicio de la serie (DecayCorrection = START).
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

import numpy as np

try:  # pydicom es dependencia opcional para poder testear la aritmética sin DICOM
    import pydicom
except ImportError:  # pragma: no cover
    pydicom = None


@dataclass
class SUVParams:
    """Parámetros necesarios para escalar Bq/mL a SUVbw."""

    weight_kg: float
    injected_dose_bq: float
    half_life_s: float
    injection_time: _dt.time
    scan_time: _dt.time
    units: str = "BQML"

    @property
    def decay_time_s(self) -> float:
        """Segundos entre inyección y adquisición (maneja el cruce de medianoche)."""
        t0 = _time_to_seconds(self.injection_time)
        t1 = _time_to_seconds(self.scan_time)
        dt = t1 - t0
        if dt < 0:  # el scan ocurrió después de medianoche
            dt += 24 * 3600
        return dt

    @property
    def decayed_dose_bq(self) -> float:
        """Dosis que queda en el cuerpo al momento del scan: D · 2^(−t/T½)."""
        return self.injected_dose_bq * 2.0 ** (-self.decay_time_s / self.half_life_s)

    @property
    def scale_factor(self) -> float:
        """Factor tal que SUV = actividad[Bq/mL] · factor.  peso en gramos."""
        return (self.weight_kg * 1000.0) / self.decayed_dose_bq


def _time_to_seconds(t: _dt.time) -> float:
    return t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1e6


def parse_dicom_time(value: str) -> _dt.time:
    """Convierte un TM DICOM ('HHMMSS', 'HHMMSS.ffffff' o 'HHMM') a datetime.time."""
    value = str(value).strip()
    if "." in value:
        head, frac = value.split(".", 1)
        micro = int((frac + "000000")[:6])
    else:
        head, micro = value, 0
    head = (head + "00000")[:6]
    return _dt.time(int(head[0:2]), int(head[2:4]), int(head[4:6]), micro)


def suv_params_from_dataset(ds) -> SUVParams:
    """Extrae los parámetros de SUV de un dataset pydicom de una lámina PET.

    Etiquetas usadas (todas estándar, módulo PET Isotope / PET Series):
      (0010,1030) PatientWeight                       [kg]
      (0054,0016) RadiopharmaceuticalInformationSequence
          (0018,1074) RadionuclideTotalDose           [Bq]
          (0018,1075) RadionuclideHalfLife            [s]
          (0018,1072) RadiopharmaceuticalStartTime    [TM]  (o StartDateTime)
      (0054,1102) DecayCorrection                     'START' | 'ADMIN' | 'NONE'
      (0008,0031) SeriesTime  /  (0008,0032) AcquisitionTime
      (0054,1001) Units                               'BQML' esperado
    """
    units = str(getattr(ds, "Units", "")).upper()
    if units != "BQML":
        raise ValueError(
            f"Units={units!r}; esta rutina asume BQML. (Philips 'CNTS' requiere "
            "el factor privado SUVScaleFactor; ver docs/GLOSARIO.md)."
        )
    rps = ds.RadiopharmaceuticalInformationSequence[0]
    dose = float(rps.RadionuclideTotalDose)
    half_life = float(rps.RadionuclideHalfLife)
    if getattr(rps, "RadiopharmaceuticalStartDateTime", None):
        inj_time = parse_dicom_time(str(rps.RadiopharmaceuticalStartDateTime)[8:])
    else:
        inj_time = parse_dicom_time(rps.RadiopharmaceuticalStartTime)

    decay_corr = str(getattr(ds, "DecayCorrection", "START")).upper()
    if decay_corr == "START":
        scan_time = parse_dicom_time(ds.SeriesTime)
    elif decay_corr == "ADMIN":
        # ya está corregido al momento de la inyección: t = 0
        scan_time = inj_time
    else:
        scan_time = parse_dicom_time(getattr(ds, "AcquisitionTime", ds.SeriesTime))

    weight = float(ds.PatientWeight)
    if not (20.0 <= weight <= 300.0):
        raise ValueError(f"PatientWeight={weight} kg fuera de rango plausible")
    return SUVParams(weight, dose, half_life, inj_time, scan_time, units)


def activity_to_suv(activity_bq_ml: np.ndarray, params: SUVParams) -> np.ndarray:
    """Aplica el factor de escala. La actividad ya debe incluir RescaleSlope/Intercept."""
    return np.asarray(activity_bq_ml, dtype=np.float32) * np.float32(params.scale_factor)
