# Bitácora del proyecto

Registro cronológico de lo que se hizo, por qué, qué se decidió y qué quedó pendiente.
Es la evidencia de "trabajo sistemático" que pide la rúbrica y la fuente para la sección
"Riesgos y ajustes al plan" de la entrega parcial. Cada entrada lleva fecha, paso y commit.

Convención de pasos (escalera de objetivos de la definición de tema):

| Paso | Objetivo | Estado |
|---|---|---|
| 0 | Repositorio, entorno, bitácora, glosario | hecho (03-09-2026) |
| 1 | Datos: subconjunto reproducible, descarga TCIA, DICOM → NIfTI con SUV | código listo y probado; descarga real pendiente |
| 2 | Preprocesamiento (3 mm, ventaneo, recorte, parches) + referencia clásica (OE1) | pendiente |
| 3 | Modelo A, fusión temprana (OE2), en Colab | pendiente |
| 4 | Modelos B y C, fusión intermedia (OE3) | pendiente |
| 5 | Evaluación comparativa y análisis por órgano (OE4) | pendiente |

Puertas de decisión: **S2** pipeline de punta a punta con 20 estudios reales · **S5** modelo A
entrenando con Dice creciente · **S8** bloque de fusión intermedia funcionando.

---

## 2026-09-03 — Paso 0 y Paso 1 (código)

**Qué se hizo**

- Se creó la estructura del repositorio (`src/petct`, `scripts`, `tests`, `configs`, `docs`, `report`, `data/manifests`) y la configuración central `configs/default.yaml` con todos los números del proyecto (semilla 423, 200 positivos + 50 negativos, partición 70/10/20 por paciente, 3 mm, ventana −200/300 HU, parches 96³).
- `src/petct/suv.py`: cálculo del SUVbw desde las etiquetas DICOM (dosis, semivida, hora de inyección y de adquisición, peso), con corrección de decaimiento y manejo del cruce de medianoche. Sigue la convención de autoPET (Units BQML, DecayCorrection START).
- `src/petct/convert.py`: lectura de series DICOM con SimpleITK, conversión a NIfTI, CT remuestreado a la grilla del PET (CTres) y conversión del DICOM SEG a máscara binaria ubicando cada frame por su posición física (no por su índice).
- `src/petct/tcia.py` y `scripts/01`–`03`: selección estratificada y reproducible del subconjunto a partir del CSV clínico de TCIA, consulta y descarga de series con `tcia_utils`, y conversión por estudio.
- `tests/`: fantoma DICOM sintético (CT 64×64 a 2 mm, PET 32×32 a 4 mm, lesión esférica de SUV 8 sobre fondo 1, SEG con frames en orden invertido a propósito). **8 pruebas pasan**: aritmética del SUV, cruce de medianoche, lectura de parámetros desde DICOM, archivos generados, SUV en lesión y fondo, CTres en la grilla del PET, SEG con Dice > 0,999 contra la verdad.

![Paso 1](docs/figuras/paso1_fantoma_conversion.png)

**Decisiones**

- Se usa **SimpleITK** para leer las series (ordena cortes y aplica RescaleSlope/Intercept) en lugar de `dicom2nifti`, para tener control total de la geometría y menos dependencias.
- El DICOM SEG se convierte con código propio (posición física de cada frame) en vez de `pydicom-seg`, que está sin mantención.
- La partición es **por paciente** y se fija con semilla: un paciente nunca aparece en dos particiones.
- Los datos y modelos quedan fuera del repositorio; solo se versionan manifiestos y código.

**Verificado / no verificado**

- Verificado: la conversión completa funciona en el fantoma sintético; el factor SUV coincide con el cálculo a mano.
- No verificado aún: el CSV clínico real de TCIA (nombres exactos de columnas; el script detecta variantes), la descarga con `tcia_utils` y un DICOM SEG real de autoPET. La API de TCIA está bloqueada desde el entorno de desarrollo remoto, así que la descarga se prueba en el computador personal.

**Pendiente inmediato (Paso 1, parte real)**

1. Descargar el CSV clínico desde TCIA a `data/manifests/clinical_tcia.csv`.
2. `pip install tcia_utils` y correr `scripts/01` y `scripts/02 --limit 3`.
3. Convertir esos 3 estudios con `scripts/03` y mirar SUV, CTres y SEG en un visor (3D Slicer o ITK-SNAP). Registrar en esta bitácora qué se vio y cualquier ajuste.
4. Subir el repositorio a GitHub (primer commit).
