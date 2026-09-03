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

## 2026-09-03. Paso 0 y Paso 1 (código)

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

## 2026-09-03 (tarde). Cuadernos, entorno y dónde corre cada cosa

**Qué se hizo**

- Se agregaron dos cuadernos comentados en `notebooks/`, pensados para VS Code en el Mac: `00_entorno.ipynb` (versiones, dispositivo que ve PyTorch, RAM y disco; su salida se pega aquí) y `01_datos_suv_conversion.ipynb` (todo el Paso 1 explicado celda a celda: SUV a mano, fantoma sintético, lectura de metadatos, conversión, verificación visual y numérica, y una sección que solo corre cuando hay estudios reales en `data/raw`). Los cuadernos se generan desde `notebooks/build_notebooks.py`, así quedan versionados como texto y se pueden regenerar sin editarlos a mano.
- `src/petct/device.py`: elige `cuda` (Colab), `mps` (chip gráfico de Apple) o `cpu`, e imprime una descripción para la bitácora.
- Se quitaron los guiones largos de los textos y se revisó el tono de los comentarios para que se lean como notas de trabajo y no como texto generado.

**Decisión: Mac o Colab**

Los pasos 1, 2 y 5 corren en el Mac (lectura DICOM, SUV, remuestreo, referencia clásica, métricas). Los entrenamientos con presupuesto completo (pasos 3 y 4, unas 25 000 iteraciones por modelo) corren en Colab, que tiene CUDA y una GPU dedicada. En el Mac, PyTorch usa `mps` para probar que el código funciona con parches chicos y para entrenamientos cortos; si `00_entorno` muestra 32 GB o más de memoria unificada y una prueba de 500 iteraciones rinde razonablemente, se puede correr un modelo completo de noche en el Mac y dejar Colab para los otros dos. La decisión final se toma con los tiempos medidos, no antes.

**Pendiente**

- Correr `00_entorno.ipynb` en el Mac y pegar la salida aquí.
- Paso 1 con datos reales (CSV clínico, `scripts/01`, `scripts/02 --limit 3`, `scripts/03`, revisión en `01_datos_suv_conversion.ipynb` sección 5).
- Push a GitHub.

## 2026-09-03 (noche). Paso 2: preprocesamiento, métricas y referencia clásica

**Qué se hizo**

- `src/petct/preprocess.py`: remuestreo a 3 mm isotrópicos (lineal para imágenes, vecino más cercano para máscaras), ventana de tejido blando −200/300 HU a [0, 1], SUV/30 con tope, máscara del cuerpo desde el CT (umbral −500 HU, componente más grande, relleno de huecos corte a corte), recorte a la caja del cuerpo, y guardado en un `.npz` por estudio. Muestreo de parches 96³ con 70 % de centros sobre lesión.
- `src/petct/metrics.py`: Dice, FPV y FNV con las definiciones del script oficial de autoPET (componentes conexas con 26 vecinos), más MTV y SUVmax.
- `src/petct/classical.py`: referencia clásica en cuatro pasos (umbral SUV ≥ 2,5; apertura con bola de radio 1; volumen mínimo 0,5 mL; exclusión de componentes dentro de máscaras de órganos). Mientras no haya máscaras del CT, dos reglas provisionales ubican encéfalo y vejiga por posición y volumen.
- `scripts/04_preprocesar.py` y `scripts/05_referencia_clasica.py`; cuaderno `02_preprocesamiento_referencia_clasica.ipynb` con un paciente sintético a 3 mm (encéfalo SUV 7, vejiga SUV 25, hígado 2,2, dos lesiones).
- Pruebas: 9 nuevas (17 en total). Con el fantoma del Paso 1, la esfera de 3,05 mL sale en 3,13 mL a 3 mm y la referencia clásica la recupera con Dice > 0,8 y FPV = FNV = 0.

**Resultado que vale la pena guardar**

En el paciente sintético, el umbral solo da Dice 0,03 y FPV 983 mL (marca encéfalo y vejiga); apertura y tamaño mínimo no cambian nada; la exclusión anatómica lleva el FPV a 0 y el Dice a 0,97. Es la hipótesis del proyecto en miniatura: sin anatomía no hay especificidad.

**Decisiones**

- Las máscaras de órganos heurísticas son un andamio. Para el análisis por órgano del informe se usarán máscaras del CT (TotalSegmentator en modo rápido corre en CPU; se evaluará su tiempo en el Mac cuando haya estudios reales).
- Volúmenes a 3 mm y `float16` en disco: un paciente entero ocupa 20 a 30 MB.

**Pendiente**

- Paso 1 con datos reales (sigue pendiente de la descarga).
- Cuando haya `.npz` reales: correr `scripts/05` y registrar aquí la tabla de la referencia clásica. Ese es el primer número del informe.

## 2026-09-03 (noche). Entorno del Mac, según `00_entorno.ipynb`

Python 3.12.13 (venv dentro del proyecto), macOS 26.6.2, arm64. numpy 2.5.2, scipy 1.18.1,
pandas 3.0.5, pydicom 3.0.2, SimpleITK 2.5.6, nibabel 5.4.2, scikit-image 0.26.0,
matplotlib 3.11.1, pytest 9.1.1, tcia_utils instalado. torch y monai todavía no
instalados (se instalan para el Paso 3). Las 17 pruebas pasan en el Mac. Falta anotar
RAM, disco libre y si PyTorch ve `mps`.
