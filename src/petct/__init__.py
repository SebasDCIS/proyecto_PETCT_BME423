"""petct — Segmentación de lesiones en FDG-PET/CT (mini-proyecto BME423, UV, 2026).

Módulos:
    suv         cálculo del SUV desde etiquetas DICOM
    convert     DICOM (CT, PT, SEG) → NIfTI (CT, PET, SUV, CTres, SEG)
    tcia        selección reproducible del subconjunto y descarga desde TCIA
    preprocess  remuestreo, ventaneo, recorte y parches (Paso 2)
"""
__version__ = "0.1.0"
