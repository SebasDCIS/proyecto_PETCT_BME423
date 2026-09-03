# Carpeta de datos

Nada de lo que hay en `raw/`, `interim/` o `processed/` se sube al repositorio (`.gitignore`).
Solo se versionan los **manifiestos** (`manifests/*.csv`): listas de pacientes, estudios y
series con las que cualquiera puede reconstruir exactamente el mismo subconjunto.

```
manifests/clinical_tcia.csv   CSV clínico de TCIA (descargar a mano desde la colección)
manifests/subconjunto.csv     250 estudios elegidos con semilla 423 + partición train/val/test
manifests/series_tcia.csv     series CT/PT/SEG de esos estudios (salida del script 02)
raw/<SeriesInstanceUID>/      DICOM descargados                    ~400 MB por estudio
interim/nifti/<pid>/<study>/  CT, PET, SUV, CTres, SEG en NIfTI     ~100 MB por estudio
processed/                    volúmenes a 3 mm, normalizados          ~25 MB por estudio
```

Analogía: `raw` es la caja con las placas originales del archivo; `interim` son las
copias digitalizadas en un formato cómodo; `processed` son las copias ya recortadas y
escaladas al tamaño que la red puede mirar.
