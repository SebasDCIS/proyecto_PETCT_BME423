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

## 2026-09-04. Cómo se bajan los datos, con precisión

La página de TCIA ofrece dos versiones de las imágenes: la original (acceso controlado,
no sirve) y la *defaced* (rostro anonimizado, CC BY 4.0). El manifiesto oficial de la
versión abierta (`FDG-PET-CT-Lesions_v02_20260817.tcia`, actualizado el 17-08-2026)
lista todas sus series. `scripts/02` ahora cruza ese manifiesto con nuestros 250
pacientes, escribe `series_tcia.csv` y un manifiesto reducido `subconjunto.tcia`, y
descarga solo si se pide `--descargar`. Así hay dos caminos para bajar: `tcia_utils`
desde el script, o el NBIA Data Retriever abriendo el manifiesto reducido. Los archivos
de entrada se dejan en `data/manifests/`; los DICOM van a `data/raw/`. Prueba nueva:
lectura y escritura de manifiestos `.tcia` (18 pruebas en total).

## 2026-09-04. Datos verificados y subconjunto elegido

Los dos archivos de TCIA quedaron en `data/manifests/` (`clinical_tcia.csv`,
`FDG-PET-CT-Lesions_defaced.tcia`). El CSV clínico trae una fila por serie (3 042 filas:
1 014 CT, 1 014 PT, 1 014 SEG) de 900 pacientes; hay pacientes con hasta 5 estudios.
Diagnósticos por estudio: 513 negativos, 188 melanoma, 168 pulmón, 145 linfoma, igual
que el artículo del dataset. La colección completa pesa 409 GB según el propio CSV.

`scripts/01` con semilla 423 eligió 251 estudios de 251 pacientes distintos (67 por
diagnóstico positivo + 50 negativos; un estudio por paciente): 176 train, 26 val, 49
test. Esos 251 estudios suman 110 GB en DICOM (CT 81 GB, PT 27 GB, SEG 1,7 GB). El
manifiesto de la versión defaced tiene 3 042 UIDs, distintos de los del CSV (son series
nuevas, anonimizadas), así que el cruce con nuestros pacientes se hace por API con
`scripts/02 --tcia-manifest`.

Pendiente: `scripts/02 --limit 3 --descargar` en el Mac y revisar los tres estudios.

## 2026-09-04. Primeros tres pacientes reales: un error encontrado y el primer número del informe

**Descarga.** `scripts/02 --tcia-manifest --limit 3 --descargar` funcionó a la primera:
el cruce con el manifiesto defaced devolvió 9 series (3 CT, 3 PT, 3 SEG) y `tcia_utils`
bajó 1,1 GB en unos tres minutos. Los StudyInstanceUID de la versión defaced son los
mismos del CSV clínico; solo cambian los SeriesInstanceUID. Los tres PET son Siemens,
`Units = BQML`, `DecayCorrection = START`, con peso registrado (61 a 84 kg): el cálculo
de SUV se aplica sin excepciones. Tamaños: PET 400 × 400 × 284 a 2,04 × 2,04 × 3 mm; CT
512 × 512 × 340 a 852 cortes de 0,76 a 0,87 mm.

**Error encontrado y corregido.** La primera conversión dejó las máscaras SEG en el
lugar equivocado: el SUV medio dentro de la "lesión" era 0,9, es decir, fondo. La causa:
autoPET guarda los frames del DICOM SEG con las filas recorridas al revés que el PET
(`ImageOrientationPatient` 1,0,0,0,−1,0 contra 1,0,0,0,1,0), y el conversor apilaba
los frames sin mirar la orientación. `seg_to_mask` ahora ubica físicamente las dos
esquinas de cada frame en la grilla del PET y voltea filas o columnas cuando hace
falta. El fantoma sintético imita ese caso desde ahora y una prueba nueva exige que la
máscara salga igual con las dos orientaciones (19 pruebas). Tras la corrección, el SUV
medio en las lesiones es 3,3 a 4,3 y el 62 a 68 % de sus vóxeles supera 2,5, con
SUVmax de 11 a 20 (distinto del máximo global de cada estudio, que es la vejiga).
Lección para la defensa: un Dice de 1,0 en el fantoma no protege de un supuesto
equivocado sobre los datos reales; la validación con datos reales fue la que lo
descubrió.

**Preprocesamiento.** A 3 mm y recortado al cuerpo, cada paciente queda en
284 × 120 × 135 vóxeles aproximadamente y 10 MB en disco; los tres tardaron 6 s.
Lesiones anotadas: 184, 118 y 36 mL.

**Referencia clásica, primera tabla (3 pacientes, todos cáncer de pulmón):**

| variante | Dice | FPV (mL) | FNV (mL) |
|---|---|---|---|
| umbral 2,5 + apertura + tamaño mínimo | 0,126 | 823 | 0,8 |
| + exclusión heurística de órganos | 0,025 | 644 | 47,9 |

La exclusión heurística baja los falsos positivos pero borra lesiones reales: en
PETCT_04606080a0 una lesión pélvica de 106 mL con SUVmax 20 fue tomada por "vejiga"
(la regla usa posición baja + SUV ≥ 10). Decisión: la heurística no va en la
referencia clásica del informe; `scripts/05` reporta las dos variantes mientras tanto, y
la exclusión anatómica se hará con máscaras del CT (TotalSegmentator) cuando estén los
250 estudios. Figura: `docs/figuras/paso2_referencia_clasica_3_pacientes.png` (MIP
coronal con lesiones anotadas, umbral, órganos heurísticos y resultado).

**Pendiente.** Descarga completa (248 estudios más, ~110 GB); `scripts/03`, `04`, `05`
sobre todos; TotalSegmentator sobre el CT a 3 mm (medir tiempo por estudio en el Mac).

## 2026-09-04. Corrección: la cabeza está al final del arreglo

Sebastián notó que en la figura de los tres pacientes la vejiga aparecía arriba y la
cabeza "cortada" abajo. Tenía razón en lo primero: la figura estaba al revés. En los
NIfTI convertidos, el índice 0 del eje z es el corte más inferior (en DICOM la
coordenada z crece hacia la cabeza y la dirección del volumen es +1), así que la cabeza
queda al FINAL del arreglo. Las reglas heurísticas suponían lo contrario y por eso
la vejiga había sido etiquetada como "encéfalo" y una lesión mediastínica como
"vejiga". Lo que ayer se describió como "lesión pélvica de 106 mL" es una lesión
torácica, coherente con el diagnóstico de cáncer de pulmón de los tres pacientes.

Cambios: `preprocess_study` guarda `head_at_end` en el `.npz`; `heuristic_organ_masks`
y `classical_segmentation` reciben esa orientación; las figuras se dibujan con la
cabeza arriba; dos pruebas nuevas verifican las heurísticas con la cabeza al principio
y al final (21 pruebas). Regla para el resto del proyecto: nunca suponer orientación,
leerla de la geometría.

Sobre la "cabeza cortada": no es un error nuestro. La versión *defaced* de autoPET
borra un bloque rectangular que cubre toda la cabeza (PET y CT en cero), no solo el
rostro. Consecuencias: (1) no existe captación cerebral en estos datos, así que el
encéfalo sale de la lista de órganos fisiológicos del análisis de falsos positivos;
(2) las lesiones de cabeza y cuello altas, si las había, no están; (3) el recorte al
cuerpo y la máscara corporal funcionan igual porque el bloque queda en aire. Queda
declarado como limitación del dataset en el informe.

Tabla corregida de la referencia clásica (3 pacientes):

| variante | Dice | FPV (mL) | FNV (mL) |
|---|---|---|---|
| umbral 2,5 + apertura + tamaño mínimo | 0,126 | 823 | 0,8 |
| + exclusión heurística (orientación corregida) | 0,326 | 217 | 18,6 |

La heurística ahora ayuda (Dice de 0,13 a 0,33, FPV de 823 a 217 mL), pero en
PETCT_0117d7f11f la "vejiga" resultó ser una componente de 1,9 L que une hígado,
riñones y vejiga con SUV ≥ 2,5 y se llevó una lesión hiliar (FNV 56 mL). Se mantiene
la decisión: las máscaras de órganos definitivas saldrán del CT (TotalSegmentator).

## 2026-09-04. Geometría DICOM documentada (posiciones de corte, espaciado, medidas)

Se agregó `src/petct/geometry.py` (orden por `ImagePositionPatient` proyectado sobre la
normal, espaciado efectivo, comparación con `SliceThickness`, ecuación índice → mm,
error por relación de aspecto), `scripts/06_geometria_series.py` (tabla por serie en
`results/geometria_series.csv`), cuatro pruebas (25 en total) y el documento
`docs/GEOMETRIA_DICOM.md`, que es el desarrollo del punto del Laboratorio 1 sobre los
datos reales, para PET y CT.

Hallazgos sobre los tres estudios: PET 400 × 400 × 284, píxel 2,036 mm, cortes de 3 mm
cada 3 mm (contiguos), archivos ordenados de pies a cabeza; CT 512 × 512, píxel 0,76 a
0,87 mm, cortes de 3 mm cada 2,5 mm (o 2 mm cada 1 mm): reconstrucción con solape;
archivos ordenados de cabeza a pies, al revés que el PET. `SpacingBetweenSlices` no
viene en ninguna serie; el espaciado medido es uniforme en las seis. PET, CT y SEG
comparten `FrameOfReferenceUID`. Campo de visión 815 mm (PET) frente a 388 a 447 mm
(CT), por eso `CTres` rellena con −1024 fuera del CT. Relación de aspecto coronal 1,47
(PET) y hasta 3,13 (CT); ignorarla acorta las medidas verticales hasta un 68 %. Figura:
`docs/figuras/geometria_posiciones_y_aspecto.png`.

## 2026-09-04. Cuaderno 01b de geometría, ejecutado con los tres pacientes

`notebooks/01b_geometria_dicom.ipynb` recorre el documento de geometría celda a celda
sobre lo que haya en `data/raw` (hoy 6 series; se vuelve a ejecutar con los 251). Dos
detalles que aparecieron al correrlo con datos reales: cada carpeta de serie descargada
por `tcia_utils` trae un archivo `LICENSE` junto a los DICOM, así que todo lector de
carpetas ahora salta lo que no sea DICOM; y la posición de los frames del SEG confirma
la orientación invertida: su y es 237,2 mm, exactamente el origen del PET (−575,3) más
399 filas por 2,036 mm, es decir, la última fila del PET.

## 2026-09-04. Los cuadernos ahora los narro yo

Reescribí las celdas de texto de los cuatro cuadernos en primera persona: explico qué
hago y por qué, como lo contaría en la defensa, en vez de instrucciones dirigidas a mí.
Los tres cuadernos con datos quedaron ejecutados con los tres pacientes reales.

## 2026-09-04 (noche). Colección completa descargada; 232 estudios convertidos y medidos

**Descarga.** 831 series completas (verificadas archivo por archivo contra `ImageCount`),
115 GB. Son más de 753 porque el cruce con el manifiesto trajo todos los estudios de cada
paciente (26 pacientes tienen más de uno); el proyecto usa solo el estudio del sorteo y
`scripts/03` filtra por `subconjunto.csv`.

**Conversión.** 232 de 251 estudios convertidos sin errores. Los 19 restantes tienen CT
de 1 208 a 2 471 cortes (cuerpo completo hasta los pies) y no caben en la memoria del
entorno remoto; se convierten en el Mac con `python scripts/03_convertir_a_nifti.py`.
Cambios para que esto fuera posible: escritura atómica (carpeta `.tmp` renombrada al
final, así una corrida cortada no deja estudios a medias), compresión rápida (nivel 1:
20 s por estudio en vez de 45, archivos algo más grandes: 60 GB en NIfTI), scripts
04 a 06 reanudables, y las funciones por componente conexa (métricas y heurísticas)
vectorizadas con `ndimage` (la referencia clásica pasó de 10 s a 1,3 s por estudio con
el mismo resultado; las 25 pruebas siguen pasando).

**Geometría de la colección (251 PET + 251 CT).** Todo axial puro, muestreo uniforme
en las 502 series. PET: 400 × 400, píxel 2,036 mm siempre; 248 con cortes de 3 mm cada
3 mm y 3 con cortes de 5 mm cada 3 mm (solape); 200 a 661 cortes; extensión 600 a
1 983 mm (hay estudios de cuerpo entero hasta los pies). CT: 512 × 512, píxel 0,69 a
0,98 mm; tres protocolos: 3 mm cada 2,5 mm (175), 2 mm cada 1 mm (53) y 1 mm cada
0,7 mm (23); 240 a 2 471 cortes; relación de aspecto coronal 0,72 a 3,62. En los 251 el
CT viene ordenado de cabeza a pies y el PET de pies a cabeza. 216 pacientes entraron de
cabeza (HFS) y 35 de pies (FFS); no cambia nada porque las posiciones están en el sistema
del paciente y `head_at_end` se lee de la geometría, pero hay que saber decirlo.

**Preprocesamiento.** 232 `.npz`, 2,8 GB en total; forma mediana (z, y, x) 313 × 126 ×
146 a 3 mm, máxima 659 × 156 × 171.

**Referencia clásica, 232 estudios (182 positivos, 50 negativos).** Dice se promedia
solo sobre positivos (en un negativo cualquier predicción da Dice 0 por definición, como
en el reto).

| variante | Dice (positivos) media / mediana | FPV media / mediana (mL) | FNV media (mL) |
|---|---|---|---|
| umbral 2,5 + apertura + tamaño mínimo | 0,178 / 0,096 | 959 / 771 | 5,7 |
| + exclusión heurística | 0,207 / 0,113 | 731 / 518 | 15,1 |

Por diagnóstico (umbral + morfología): linfoma Dice 0,28 (lesiones grandes, MTV medio
333 mL), pulmón 0,18 (225 mL), melanoma 0,10 (107 mL, lesiones chicas y dispersas). En
los 50 negativos el umbral marca en promedio 1 009 mL de "tumor": ese es el tamaño del
problema de la captación fisiológica, dicho en mililitros. La heurística baja el FPV un
24 % pero triplica el FNV: se descarta del informe final, como estaba decidido.

**Pendiente.** Convertir los 19 estudios grandes en el Mac y rehacer 04 y 05 para
incluirlos (los scripts saltan lo ya hecho). Re-ejecutar los cuadernos con los 251.

## 2026-09-05. Colección completa: 251 estudios convertidos, preprocesados y medidos

Los 19 estudios grandes (CT de 1 208 a 2 471 cortes) se convirtieron en el Mac sin
errores en una sola corrida de `03 → 04 → 05 → 06` (los scripts saltaron lo ya hecho).
Totales: 251 NIfTI (69 GB), 251 `.npz` (3,0 GB; forma mediana 316 × 126 × 147, mínima
200 × 83 × 123, máxima 659 × 156 × 171), 502 series medidas. En los 251 `head_at_end`
es verdadero (índice 0 = corte inferior). `scripts/04` ahora reconstruye
`procesados.csv` desde los `.npz` existentes en cada corrida, porque la tabla anterior
solo guardaba lo procesado en la última máquina.

**Referencia clásica, 251 estudios (201 positivos, 50 negativos).** Dice promediado solo
sobre positivos. Los números cambian poco respecto de los 232: la colección completa
confirma lo que decía la parcial.

| variante | Dice (positivos) media / mediana | FPV media (mL) | FNV media (mL) | FPV en negativos (mL) |
|---|---|---|---|---|
| umbral 2,5 + apertura + tamaño mínimo | 0,179 / 0,100 | 952 | 7,6 | 1 009 |
| + exclusión heurística | 0,205 / 0,119 | 726 | 24,6 | 738 |

Por diagnóstico (umbral + morfología, 67 estudios cada uno): linfoma Dice 0,25 (MTV
medio 315 mL), pulmón 0,18 (225 mL), melanoma 0,11 (123 mL, lesiones chicas y
dispersas; FPV más alto, 1 104 mL, porque muchos son de cuerpo entero). Por partición:
entrenamiento 0,18 (141 positivos), validación 0,17 (21), prueba 0,18 (39): las tres
particiones se parecen, que es lo que se quiere de un sorteo estratificado. MTV anotado
medio 221 mL, mediana 94. La heurística se descarta (baja el FPV un 24 % pero triplica
el FNV); las máscaras de órganos vendrán del CT.

**Los 19 estudios largos y la comparación.** Pregunta que salió hoy: si algunos estudios
son de cuerpo entero hasta los pies y el resto de ojos a muslos, ¿no contamina eso la
comparación? No: los tres modelos verán exactamente los mismos estudios, con la misma
partición y el mismo preprocesamiento, así que la heterogeneidad les afecta por igual y
no sesga la diferencia entre ellos, que es lo que se mide. La red entrena con parches de
96³, no con el volumen completo, y en inferencia la ventana deslizante recorre lo que
haya. Lo que sí cambia es el nivel absoluto: un cuerpo de 2 m tiene más tejido donde
inventar falsos positivos, por eso las métricas se reportarán también por diagnóstico y,
si hace falta, por protocolo. Sacarlos sería peor: son en buena parte melanomas, y
meterían un sesgo de selección.

**Pendiente.** Re-ejecutar los cuadernos 01b y 02 con los 251 (`jupyter nbconvert
--execute --inplace`). Paso 3 empieza ahora: modelo A.

## 2026-09-05. Paso 3: dataset de parches, modelo A y bucle de entrenamiento

Código nuevo, probado en CPU con el fantoma (32 pruebas en total, 7 nuevas):

- `src/petct/data.py`: `split_files` (cruza el sorteo con los `.npz`), `PatchDataset`
  (parches 96³ sesgados a lesiones, dos canales SUV/CT, volteos laterales, caché LRU de
  estudios en RAM, semilla por proceso del DataLoader) y `VolumeDataset` (estudios
  completos para validar).
- `src/petct/models.py`: `build_model("A")` = U-Net 3D de MONAI, 5 niveles
  (32-64-128-256-320), 2 bloques residuales por nivel, normalización por instancia,
  12,9 M de parámetros; versión chica (1,2 M) para pruebas. B y C se registran en el
  Paso 4 sobre la misma interfaz.
- `src/petct/train.py`: bucle por iteraciones con pérdida Dice + CE (Dice solo sobre
  lesión), AdamW con decaimiento polinómico, precisión mixta solo en CUDA, recorte de
  gradiente, checkpoint atómico `ultimo.pt` cada 500 iteraciones, `mejor.pt` por Dice de
  validación rápida (12 estudios, ventana deslizante) cada 1 000, reanudación
  automática, parada por tiempo (`--max-minutos`) para Colab, registros en CSV.
- `src/petct/infer.py`: ventana deslizante (solape 0,5, peso gaussiano) y evaluación con
  las mismas columnas que `referencia_clasica.csv`.
- `scripts/07_entrenar.py`, `08_benchmark_dispositivo.py` (segundos por iteración y
  horas para 25 000 en cada dispositivo), `09_evaluar.py` (una partición completa con un
  checkpoint; `test` se evalúa una sola vez al final).
- `notebooks/03_modelo_a_fusion_temprana.ipynb`: particiones, un parche real, la red, la
  pérdida, el benchmark de esta máquina, corrida de humo de 150 iteraciones y una
  predicción sobre un estudio de validación.

Decisiones: aumentos mínimos (solo volteos laterales) porque se comparan arquitecturas;
sin volteo cabeza-pies; caché de estudios configurable (todo en el Mac, 40–50 en Colab);
el YAML gana `validar_cada` y `max_estudios_val`. Pendiente inmediato: benchmark en el
Mac (`mps`) para decidir dónde corre el presupuesto completo, y la corrida de humo con
datos reales.

**Benchmark en el Mac (M5, 24 GB), red completa, lote 2, parches 96³, sin AMP:**
`mps` 0,587 s/iteración → 4,1 h para 25 000 iteraciones, 1,1 GB de memoria pico;
`cpu` 0,629 s/iteración → 4,4 h. Decisión: los tres entrenamientos completos corren en
el Mac (una noche por modelo); Colab queda como plan B. Que la CPU quede casi igual que
MPS no es un error de medición: las convoluciones 3D en MPS no están tan optimizadas
como en CUDA y el procesador del M5 es rápido. El tiempo real por iteración se registra
en `runs/<modelo>/log_entrenamiento.csv`. Las 32 pruebas pasan en el Mac (12 s).

**Humo con datos reales (cuaderno 03):** pérdida 1,94 → 0,97 en 150 iteraciones de la
red chica; validación con ventana deslizante sobre un estudio de 284 × 135 × 147 en
1,8 s; checkpoints escritos y reanudados. La fracción de parches con lesión fue 53 %
(esperado 0,7 × 141/176 positivos ≈ 0,56: los estudios negativos no tienen lesión que
centrar).

**Entrenamiento completo del modelo A lanzado** (`runs/A`, semilla 423, 0,65 s por
iteración con datos reales). Iteración 1 000: Dice 0,12, FPV 579 mL, FNV 4,9 mL en los 12
estudios de validación rápida (la referencia clásica: 0,18 / 952 / 7,6).

**Protocolo acordado para lo que sigue.** No subir la resolución (2 mm = 3,4 veces más
vóxeles, menos contexto por parche, 10 h por modelo, ganancia modesta) ni bajar más
datos. Con 5 h por corrida, lo que mejora el proyecto es repetir: tres semillas por
modelo (nueve corridas, ~36 h de Mac) para reportar media y desviación, decidido después
de ver el nivel del modelo A. Agregados `--semilla` (07), `--etiqueta` (09) y
`scripts/10_resumir_corridas.py` (tabla de corridas, comparación media ± sd por modelo
junto a la referencia clásica, curvas de entrenamiento).

## 2026-09-05. Modelo A entrenado: Dice 0,55 en validación, falsos positivos de 1 192 a 18 mL

**Corrida.** `runs/A`, semilla 423, 25 000 iteraciones, lote 2, parches 96³, `mps`,
0,647 s/iteración, 4 h 48 min. Pérdida de 1,73 (iteración 20) a 0,49 (promedio de las
últimas 5 000); seguía bajando despacio, sin señal de sobreajuste. Validación rápida
(12 estudios) cada 1 000 iteraciones: el FPV cae primero (579 mL en la 1 000, 134 en la
6 000), el Dice sube después (0,40 en la 7 000, 0,51 en la 13 000) y desde ahí oscila entre
0,42 y 0,51 por el tamaño de la muestra. Mejor checkpoint: iteración 23 000 (Dice 0,512,
FPV 10 mL, FNV 3,9 mL).

**Validación completa (26 estudios, 21 positivos), `scripts/09`, checkpoint 23 000:**

| | Dice (positivos) media / mediana | FPV media (mL) | FNV media (mL) | FPV en negativos (mL) | MTV predicho / anotado (mL) |
|---|---|---|---|---|---|
| referencia clásica (mismos 26) | 0,170 / — | 1 192 | 7,6 | 852 | 1 545 / 199 |
| modelo A | 0,549 / 0,566 | 18 | 8,4 | 26 | 157 / 199 |

Por diagnóstico: pulmón Dice 0,70 (7), linfoma 0,66 (7), melanoma 0,28 (7). El melanoma
de validación tiene lesiones diminutas (MTV anotado medio 6,8 mL; predicho 24,5): con
lesiones de pocos vóxeles el Dice castiga cualquier borde de más, y ahí 3 mm isotrópicos
pesan. Un solo positivo con Dice 0 (`PETCT_1a90052cb2`: lesión de 9,5 mL no detectada,
43 mL inventados); el mayor FNV es `PETCT_e03b96666f` (93,6 mL no tocados, Dice 0,68 igual).
Los cinco negativos suman 129 mL de falsos positivos (el peor, 104 mL en `PETCT_f6295a93a6`).

**Lectura.** El modelo A está en el nivel esperado para 176 pacientes y 5 h de cómputo
(los ganadores de autoPET: 0,6–0,7 con semanas de GPU). Lo que aprendió entre la
iteración 1 000 y la 13 000 fue sobre todo a descartar captación fisiológica: es el CT
trabajando en fusión temprana. El MTV predicho queda un 20 % por debajo del anotado
(bordes conservadores), contra 8 veces por encima en la clásica.

**Protocolo congelado para las nueve corridas.** Se mantiene todo tal como corrió A:
lote 2, parches 96³, 25 000 iteraciones, lr 3·10⁻⁴, sin AMP en `mps`, volteos laterales.
Cambiar algo ahora obligaría a repetir A. Semillas: 423 (hecha), 2 y 3 por modelo. La
partición de prueba (49) no se toca hasta tener los nueve checkpoints. Resultados:
`results/modelo_A_val.csv`, `results/corridas.csv`, `results/comparacion_modelos.csv`,
`docs/figuras/curvas_entrenamiento.png`. Máscaras predichas en `runs/A/mascaras_val/`
(fuera de git) para el análisis por órgano.

## 2026-09-05. Semilla 2 del modelo A; Paso 4: modelos B y C construidos

**Semilla 2 de A** (`runs/A_s2`, 4 h 48 min): mejor Dice de validación rápida 0,586, contra
0,512 de la semilla 423. Siete centésimas de diferencia con la misma arquitectura, los
mismos datos y el mismo presupuesto: es la variabilidad que hay que conocer antes de
comparar arquitecturas, y la razón de las tres semillas. Evaluación en los 26 de
validación pendiente (`scripts/09 ... --etiqueta modelo_A_s2`). Semilla 3 en cola.

**Modelos B y C** (`src/petct/models.py`), sobre la misma interfaz `build_model`:

- Codificador propio (`Encoder`): un bloque residual de MONAI por nivel, mismo plan de
  canales que A (32-64-128-256-320), dos subbloques, normalización por instancia;
  reducción ×2 desde el segundo nivel. 11,9 M de parámetros por codificador.
- B: dos codificadores (PET, CT). En el cuello de botella se concatenan (640 canales) y
  una convolución 1×1×1 los mezcla en 320; los saltos llevan al decodificador los mapas
  de ambos lados concatenados. Decodificador liviano (un subbloque por nivel, como en la
  U-Net de MONAI). Total 34,6 M.
- C: B más un bloque de atención cruzada en el cuello de botella antes de concatenar:
  consultas desde el mapa PET, etiquetas y contenidos desde el mapa CT, 8 cabezas,
  pre-normalización, codificación de posición sinusoidal 3D fija, y una ganancia
  aprendible `gamma` que parte en 0 (al inicio C se comporta exactamente como B y la red
  decide cuánto usar la atención). Total 35,0 M; la diferencia con B son 0,4 M.
  `attention_maps()` devuelve los pesos promediados por cabeza para el análisis.
- A+: control de capacidad. La misma fusión temprana de A con canales ×1,5
  (48-96-192-384-480), 28,9 M. Si sobra cómputo, responde si B gana por fusionar distinto
  o por ser más grande. Opcional; no forma parte de las nueve corridas.

Decisión de diseño declarada: B y C tienen 2,7 veces los parámetros de A porque llevan dos
codificadores completos; se prefirió mantener el codificador idéntico al de A (misma
"lupa" por modalidad) antes que igualar parámetros angostando los canales. La comparación
limpia de la atención es B contra C; la de fusión temprana contra intermedia es A contra
B, con A+ como control si se corre.

Pruebas nuevas (37 en total): forma y gradiente de B y C, C−B < 10 % de parámetros, la
atención suma 1 por consulta y con `gamma = 0` deja el mapa PET intacto, la codificación
de posición distingue posiciones, y 12 iteraciones de entrenamiento de B y C bajan la
pérdida sobre el fantoma. `scripts/08` acepta `--modelos B C` para medir su velocidad en
`mps` antes de lanzarlos (se espera ~1,5× el tiempo de A por los dos codificadores).

**Semilla 2 de A en los 26 de validación:** Dice 0,578 (mediana 0,665), FPV 22 mL, FNV
7,9 mL, FPV en negativos 36 mL; pulmón 0,72, linfoma 0,64, melanoma 0,37. Con dos
semillas, A queda en Dice 0,56 ± 0,02, FPV 20 ± 3 mL, FNV 8,2 ± 0,4 mL
(`results/comparacion_modelos.csv`). La desviación entre semillas en validación completa
(0,02) es menor que en la validación rápida (0,07), como corresponde a 26 estudios frente a
12: es el umbral por debajo del cual una diferencia entre modelos no dice nada.

**Corrección de B y C antes de lanzarlos (misma tarde).** El benchmark en el Mac dio 4,03 s
por iteración para B y C (28 h por corrida, 11,6 GB de memoria) contra 0,59 de A. Contando
operaciones: A 37 GFLOP por parche, B 586. La causa no eran los dos codificadores sino que
mi `Encoder` procesaba el primer nivel a resolución completa (96³, 32 canales, dos
subbloques) y el decodificador terminaba con una convolución de 96 canales también a 96³;
la U-Net de MONAI de A reduce ×2 desde la primera convolución y nunca opera ancho a
resolución completa. Rehice `Encoder` y `Decoder` con exactamente el plan de MONAI
(96³ → 48³ → 24³ → 12³ → 6³; cuello de botella a 6³; subida con concatenación de saltos +
convolución transpuesta + un subbloque residual; último nivel produce la salida). Ahora:
B 24,0 M y 59 GFLOP; C 24,4 M y 59 GFLOP (1,6× A). A+ pasa a canales ×1,375 (24,3 M, los
parámetros de B). Las 37 pruebas pasan. Lección: contar operaciones (`torch.utils.flop_counter`)
antes de lanzar 25 000 iteraciones; el benchmark de 10 iteraciones evitó perder una semana.
Hay que repetir el benchmark y re-ejecutar el cuaderno 04 (el humo anterior de C queda
inválido: pesos de otra arquitectura).

**Semilla 3 de A en validación:** Dice 0,574 (mediana 0,688), FPV 24 mL, FNV 7,6 mL. Las
tres semillas: 0,549 / 0,578 / 0,574 → **A = 0,567 ± 0,016**, FPV 21 ± 3 mL, FNV 8,0 ± 0,4
mL. Modelo A cerrado.

## 2026-09-05 (tarde). Hallazgo: lesiones anotadas dentro de la caja borrada por el defacing

La figura de casos (`scripts/13_figuras_casos.py`, MIP coronal con experto y predicciones)
mostró que en `PETCT_1a90052cb2` y `PETCT_e03b96666f` el contorno del experto cae dentro de
la franja blanca superior: la caja que el defacing borró. La anotación se hizo sobre la
imagen original y conserva lesiones donde ya no queda señal (SUV exactamente 0, CT aire).
Ningún método puede segmentarlas y contaban como falsos negativos.

**Cuantificación (251 estudios):** 69 tienen lesión anotada fuera de la máscara de cuerpo;
2 064 mL en total (4,6 % de los 44 414 mL anotados), 1 651 mL con SUV = 0 (zona borrada); el
resto son lesiones fuera del campo de visión del CT (brazos), donde sí hay PET. En validación,
268 mL de 4 179; `PETCT_73fda3a382` tiene 207 de sus 269 mL en la zona borrada.

**Regla de evaluación adoptada (`metrics.blank_region_mask`, `evaluate_study(exclude_blank=True)`):**
se excluyen de la predicción y de la verdad los vóxeles con SUV = 0. Es objetiva, se aplica
igual a los tres modelos y a la referencia clásica, y la columna `gt_excluido_ml` deja
constancia. La métrica cruda del reto sigue disponible (`--incluir-zona-borrada`). El
entrenamiento no cambia (A ya entrenó con esas anotaciones y B corre igual; el efecto es el
mismo para los tres). La validación rápida durante el entrenamiento mantiene la regla cruda
para que la elección del checkpoint sea idéntica en las nueve corridas. Consecuencia: un
estudio de validación (`1a90052cb2`, melanoma) queda sin lesión evaluable y pasa a contar
como negativo (20 positivos, 6 negativos).

**Resultados recalculados desde las máscaras guardadas (`scripts/14`):**

| | Dice (positivos) | FPV (mL) | FNV (mL) | FPV negativos (mL) |
|---|---|---|---|---|
| A, semilla 423 | 0,603 (med 0,653) | 18,0 | 6,5 | 28,7 |
| A, semilla 2 | 0,632 (med 0,728) | 22,2 | 5,9 | 44,0 |
| A, semilla 3 | 0,630 (med 0,715) | 22,5 | 5,6 | 36,3 |
| **A, media ± sd** | **0,621 ± 0,016** | **20,9 ± 2,5** | **6,0 ± 0,4** | 36 |
| referencia clásica, val | 0,180 | 1 192 | 5,6 | 1 224 |

Los resultados sin la corrección quedan en `results/sin_exclusion/`. La referencia clásica
se recalculó sobre los 251 con la misma regla (Dice 0,184 en positivos, FPV 952, FNV 2,6).

**Para la defensa.** El defacing de la versión pública no solo elimina el encéfalo de los
datos: deja anotaciones huérfanas que ningún modelo puede acertar. Hay que decirlo, medirlo
(4,6 % del volumen anotado) y excluirlo de forma declarada; si no, se está midiendo el
anonimizado y no el modelo. Lo detectó una figura, no una tabla: mirar los casos vale.

## 2026-09-05 (noche). Primera corrida de B

`runs/B`, semilla 423, 5 h 56 min (0,85 s/it real), mejor checkpoint en la iteración 13 000
(Dice de validación rápida 0,513). En los 26 de validación, con la regla de exclusión:
Dice 0,603 (mediana 0,655), FPV 20,3 mL, FNV 5,8 mL, FPV en negativos 36 mL. Es
prácticamente idéntico a la semilla 423 de A (0,603 / 18,0 / 6,5). Una sola semilla no
permite concluir; B_s2 lanzada.

**B, semilla 2** (`runs/B_s2`, 6 h 32 min, mejor checkpoint 19 000): validación Dice 0,606
(mediana 0,711), FPV 26,2 mL, FNV 5,8 mL, FPV en negativos 44 mL. Con dos semillas,
B = 0,605 ± 0,002 de Dice y 23 ± 4 mL de FPV, contra A = 0,621 ± 0,016 y 21 ± 3. Diferencia
dentro del ruido. B_s3 lanzada.

## 2026-09-06. Auditoría del protocolo y de fugas, con B_s3 corriendo

Antes de lanzar C quise comprobar que las nueve corridas comparten exactamente los mismos datos
y la misma configuración, y que no hay fuga entre particiones. Lo revisé contra los archivos
reales (manifiesto, `resumen.json` de cada corrida, código), no de memoria; el detalle queda en
`docs/PROTOCOLO_CONGELADO.md`.

**Datos.** 251 estudios = 251 pacientes = 251 `study_uid`; ningún paciente en dos particiones;
estratificado por diagnóstico (train 47/47/47/35, val 7/7/7/5, test 13/13/13/10); el manifiesto
no cambió desde el commit `28a5ddf` (md5 `03d1d5c6…`). Lesión anotada por estudio: 173 / 161 /
200 mL (train / val / test), parecidos.

**Configuración.** Los `resumen.json` de A, A_s2, A_s3, B y B_s2 coinciden campo a campo
(25 000 it, lote 2, parche 96³, 70 % lesión, lr 3e-4, wd 1e-5, validación cada 1 000 sobre 12,
caché 256, red completa); solo cambian `modelo` y `semilla`. B_s3 va con la misma línea. AMP
está en `true` pero solo actúa en CUDA: todo se entrena en fp32 en mps, igual para todos.

**Fugas.** Entrenamiento solo ve train (`splits["train"]` → `PatchDataset`); val solo entra a
la validación rápida sin gradiente; test no se ha cargado nunca (no hay `*_test.csv` ni
`mascaras_test`). Normalizaciones constantes (sin estadísticas globales), aumento solo en
train, umbral clásico fijado por diseño, mapas de órganos solo en evaluación, regla de
exclusión solo en evaluación. Veredicto: sin fugas; test sigue cerrado.

**Dos cosas que descubrí y dejo declaradas.** (1) `split_files` ordena alfabéticamente, así que
los 12 de validación rápida no son los 12 primeros del manifiesto sino 3 pulmón, 3 linfoma,
4 melanoma y 2 negativos, siempre los mismos; incluyen a `1a90052cb2` (lesión solo en la zona
borrada, Dice cruda 0 fija), lo que explica que la validación rápida dé 0,50–0,59 y los 26 con
exclusión 0,60–0,63. Es un criterio ruidoso pero idéntico en las nueve corridas; no lo cambio
para no romper la comparabilidad. (2) Los 12 están dentro de los 26 que reporto en val, así
que val es levemente optimista; la cifra limpia será la de test. Mejores checkpoints: A 23 000,
A_s2 24 000, A_s3 22 000, B 13 000, B_s2 19 000 (B llega antes a su mejor punto).

Limpieza menor: la sección `evaluacion` del YAML decía `hd95` y una lista de órganos vieja;
ahora refleja lo que realmente se calcula. No afecta a B_s3 (leyó el YAML al arrancar y solo
usa `entrenamiento`/`preprocesamiento`).

## 2026-09-06 (tarde). Modelo B cerrado con tres semillas

**B, semilla 3** (`runs/B_s3`, 6 h 20 min, mejor checkpoint 22 000, validación rápida 0,557):
en los 26 con la regla de exclusión, Dice 0,628 (mediana 0,704), FPV 21,9 mL, FNV 4,4 mL,
FPV en negativos 36 mL. Es la mejor de las tres B y la que menos deja escapar (en
`e03b96666f` el FNV baja de ~80 a 64 mL).

| | Dice (positivos) | FPV (mL) | FNV (mL) | FPV negativos (mL) |
|---|---|---|---|---|
| B, semilla 423 | 0,603 | 20,3 | 5,8 | 36 |
| B, semilla 2 | 0,606 | 26,2 | 5,8 | 44 |
| B, semilla 3 | 0,628 | 21,9 | 4,4 | 36 |
| **B, media ± sd** | **0,612 ± 0,014** | **22,8 ± 3,1** | **5,4 ± 0,8** | 39 |
| A, media ± sd | 0,621 ± 0,016 | 20,9 ± 2,5 | 6,0 ± 0,4 | 36 |

Por diagnóstico (media de las tres semillas): A pulmón 0,74 / linfoma 0,70 / melanoma 0,40;
B pulmón 0,75 / linfoma 0,69 / melanoma 0,35. Lectura: separar los embudos no cambia nada
medible con tres semillas; la diferencia de Dice (0,009) es menor que la desviación entre
semillas de cualquiera de los dos. B tiende a dejar escapar un poco menos (FNV 5,4 vs 6,0) y
a inventar un poco más (FPV 22,8 vs 20,9), también dentro del ruido. `results/comparacion_modelos.csv`
y `docs/figuras/curvas_entrenamiento.png` actualizados con `scripts/10`. C semilla 423 lanzada.

## 2026-09-07. Primera corrida de C: mismo Dice, un cuarto menos de falsos positivos

`runs/C`, semilla 423, 5 h 56 min (0,86 s/it: la atención en el cuello casi no cuesta tiempo
frente a B), pérdida final 0,444 (la más baja de las siete corridas), mejor checkpoint en la
iteración 23 000 (validación rápida 0,548). En los 26 con la regla de exclusión: Dice 0,624
(mediana 0,717), **FPV 16,0 mL**, FNV 4,9 mL, **FPV en negativos 24,6 mL**.

| | Dice (positivos) | FPV (mL) | FNV (mL) | FPV negativos (mL) |
|---|---|---|---|---|
| A (3 semillas) | 0,621 ± 0,016 | 20,9 ± 2,5 | 6,0 ± 0,4 | 36 |
| B (3 semillas) | 0,612 ± 0,014 | 22,8 ± 3,1 | 5,4 ± 0,8 | 39 |
| C, semilla 423 | 0,624 | 16,0 | 4,9 | 25 |

El Dice es el mismo de siempre (pulmón 0,76, linfoma 0,70, melanoma 0,38), pero los falsos
positivos bajan un 25–30 % respecto a A y B, y es la primera vez que un modelo se sale de la
banda de ruido en alguna métrica. Dónde baja: en `1a90052cb2` (negativo evaluable) pasa de
43–66 mL a 28; en `742a9413db` de 68–74 a 48; en `ea6c621616` de 29–31 a 20; cuatro de los seis
negativos quedan bajo 5 mL. Dónde no baja: `f6295a93a6` sigue en 110 mL (los tres modelos
inventan lo mismo ahí; hay que ver qué es con el mapa de órganos) y `94962fe878` sigue en
78 mL. El FNV no cambia.

Es exactamente la dirección de la hipótesis (la atención al CT debería servir para descartar
captación fisiológica, no para dibujar mejor el borde), pero con una semilla no se afirma nada:
B_s2 tuvo FPV 26 y B 20 con la misma arquitectura. C_s2 lanzada; si las tres semillas de C
quedan bajo 20 mL con A y B en 21–23, el análisis por órgano del Paso 5 dirá dónde se ganó.
Pendiente: leer `gamma` del checkpoint para saber cuánto usa C la atención.

## 2026-09-07. Ablación de C: la atención no estaba haciendo nada

Antes de lanzar C_s2 quise saber cuánto usaba C la atención. `gamma`, la ganancia que
multiplica la salida del bloque de atención antes de sumarla al mapa PET, partió en 0 y
terminó en **0,0125**. Para saber si eso es poco o mucho hice la prueba directa: agregué
`--sin-atencion` a `scripts/09_evaluar.py` (carga el mismo `mejor.pt`, pone gamma = 0 y evalúa)
y comparé con la evaluación normal en los 26 de validación.

**Resultado: idéntico vóxel a vóxel.** Dice, FPV, FNV, MTV predicho y SUVmax predicho
coinciden en todos los decimales en los 26 estudios (`results/modelo_C_sin_atencion_val.csv`
frente a `results/modelo_C_val.csv`). Con gamma = 0,0125 la rama de atención aporta un 0,3 %
de la señal del mapa PET (medido con tensores de la forma del cuello: ‖atención‖/‖q‖ ≈ 0,25
con gamma 1, por 0,0125 → 0,003), y ese 0,3 % no alcanza a cambiar ni un argmax. En otras
palabras, la C que entrené es B con otra inicialización, y **los 16 mL de FPV frente a los
21–23 de A y B son ruido de semilla, no efecto de la atención**. Menos mal que lo medí antes
de contarlo como hallazgo.

**Por qué pasó.** La idea de partir en 0 (estilo ReZero, "C nace siendo B") suponía que la red
subiría gamma si la atención le servía. Pero el gradiente que llega a gamma es pequeño cuando
la salida de la atención es todavía ruido y la red ya resuelve la tarea por el camino de la
concatenación; con lr 3e-4 y decaimiento polinomial, gamma se movió al principio (0,012 en la
prueba de humo de 100 iteraciones) y después no volvió a crecer. Un dial que arranca en cero
y nadie tiene motivo para subir se queda en cero.

**Decisión (propuesta, pendiente de confirmar antes de lanzar C_s2).** Cambiar la inicialización
de gamma a 1, que es el residual estándar de un bloque transformer pre-LN (la atención aporta
~25 % de la señal al inicio y la red puede bajarla), y repetir las tres semillas de C. El
resto de la arquitectura, los datos y el protocolo no cambian. La corrida hecha pasa a
`runs/C_piloto_gamma0/` y sus resultados a `results/modelo_C_piloto_gamma0_val.csv`; los
scripts 10, 12 y 13 ignoran las carpetas con "piloto" en el nombre. Costo: tres noches en
vez de dos. Beneficio: la pregunta del proyecto se responde de verdad; con gamma en 0,0125
las tres semillas de C habrían medido tres veces "C = B" por una razón trivial.

Código: `CrossAttentionFusion(gamma_init=1.0)`, `DualEncoderUNet(gamma_init=...)`, prueba
actualizada (`gamma_init=0` sigue dando la identidad, que es lo que usa la ablación); 41
pruebas pasan. Glosario: entradas "gamma" (reescrita) y "ablación" (nueva).

**Para la defensa.** Esto es lo que debe verse en el informe: un mecanismo no se da por
funcionando porque esté en el diagrama; se apaga y se mide. Y una mejora no se atribuye a
un mecanismo hasta que la ablación lo confirme.

## 2026-09-07 (tarde). C con gamma inicial 1: la atención sigue sin cambiar un vóxel, y ahora sé por qué

`runs/C`, semilla 423, gamma inicial 1, 5 h 57 min, pérdida final 0,448. Gamma terminó en
1,00002 (no se movió: la proyección de salida de la atención absorbe cualquier escala, así
que el gradiente hacia gamma promedia cero; el número no informa). El checkpoint elegido es
el de la iteración **9 000**, un pico aislado de la validación rápida (8 000: 0,437; 9 000:
0,551; 10 000: 0,390; luego meseta en 0,45–0,52). Es la limitación (a) del protocolo pegando
fuerte: el modelo evaluado está a un tercio del entrenamiento.

En los 26 con exclusión: Dice 0,603 (mediana 0,639), FPV 16,1 mL, **FNV 7,8 mL** (el más alto de
todas las corridas, por `5255c79083` con 31 mL y `e03b96666f` con 89), FPV en negativos 37 mL.
Perfil de error distinto a A y B: `f6295a93a6` baja de 104–110 a 42 mL, `0f4ee9e078` sube de
Dice 0,2 a 0,57, pero `4a72eeb991` (negativo) sube de 2–5 a 55 mL y `1a90052cb2` a 91.

**Ablación: idéntica otra vez.** Con gamma forzado a 0, las 26 filas coinciden en todos los
decimales (`results/modelo_C_sin_atencion_val.csv`). Con la atención participando desde la
iteración 0 y recibiendo gradiente completo, su salida sigue sin cambiar ningún argmax.

**El mecanismo (medido en el sandbox con la red chica y pesos aleatorios).** La salida de la
atención es en un 99 % *constante entre posiciones*: los pesos de atención son casi uniformes
sobre las 216 posiciones del cuello (peso máximo medio 0,033 frente a 0,016 uniforme), así que
cada posición del PET recibe prácticamente el mismo vector, el promedio global del CT. Y la
mezcla del cuello (`fuse`: conv 1×1 → **norma de instancia** → activación) resta a cada canal su
media espacial: un vector constante entre posiciones desaparece exactamente. Solo pasa la parte
que varía con la posición, que es un 4 % de ‖q‖ al inicio; el efecto sobre los logits es del
0,9 % y cambia 81 de 32 768 vóxeles con pesos aleatorios, y tras el entrenamiento, ninguno.
Toda la red (codificadores y decodificador) usa norma de instancia, así que un "contexto
global" solo puede entrar como patrón espacial, nunca como constante. La atención en el
cuello, tal como está diseñada (aditiva, pre-LN, posición sinusoidal), produce sobre todo
contexto global, y la red no llegó a afinarla hacia algo posicional porque el gradiente que
recibe pasa solo por esa parte pequeña.

**Conclusión provisional, más interesante que un pequeño Dice:** en una U-Net con norma de
instancia, la atención cruzada aditiva en el cuello de botella es estructuralmente inerte.
Un revisor lo puede leer como "C ≡ B por diseño". Se demuestra con las dos ablaciones
(gamma 0,0125 y gamma 1) y con la medición de la constancia.

**Decisión.** C_s2 y C_s3 se corren como están (protocolo intacto; C es "la atención tal
como suele implementarse", y su nulidad es un resultado con mecanismo). Como brazo adicional,
declarado post hoc, se diseña una variante D en la que el contexto de la atención entra por
un camino que la norma de instancia no cancela: modulación de los parámetros afines de la
norma del cuello (estilo FiLM/AdaIN) con el vector global, más la parte posicional aditiva.
D se pilotea una noche y, si la ablación muestra que la atención cambia el resultado, se
corre con tres semillas si el calendario lo permite. Si no, queda como trabajo futuro con
la evidencia del mecanismo.

## 2026-09-08. C semilla 2: segunda ablación, misma respuesta

`runs/C_s2`, 5 h 57 min, mejor checkpoint en la iteración **19 000** (validación rápida 0,526).
Que esta semilla eligiera 19 000 y la anterior 9 000 confirma que aquel pico temprano fue mala
suerte de la semilla 423 y no algo sistemático de C.

En los 26 con exclusión: Dice 0,618 (mediana 0,716), FPV 24,0 mL, FNV 5,3 mL, FPV en negativos
44 mL. Por diagnóstico: pulmón 0,763, linfoma 0,715, melanoma 0,337, el mismo patrón de siempre.
Gamma terminó en 0,9996 (partió en 1; tampoco se movió).

**Ablación, segunda vez: diferencia exactamente cero** en las 26 filas y en las cinco columnas
(`results/modelo_C_s2_sin_atencion_val.csv`). Ya son dos semillas con gamma inicial 1, más la
piloto con gamma inicial 0: tres corridas independientes en las que apagar la atención cruzada
no cambia un solo vóxel. La afirmación deja de ser una anécdota de una corrida.

Estado con dos semillas de C:

| | Dice (positivos) | FPV (mL) | FNV (mL) | FPV negativos |
|---|---|---|---|---|
| A (3 semillas) | 0,621 ± 0,016 | 20,9 ± 2,5 | 6,0 ± 0,4 | 36 |
| B (3 semillas) | 0,612 ± 0,014 | 22,8 ± 3,1 | 5,4 ± 0,8 | 39 |
| C (2 semillas) | 0,611 ± 0,011 | 20,1 ± 5,6 | 6,5 ± 1,7 | 40 |

Los tres modelos caben dentro del mismo intervalo. C_s3 lanzada; con ella se cierra el acto 1.

## 2026-09-08. Acto 1 cerrado: nueve corridas, tres ablaciones, una conclusión

`runs/C_s3`, 6 h 36 min (algo más lenta que las otras por acortamiento térmico, sin
consecuencias), mejor checkpoint en la iteración 22 000. En los 26 con exclusión: Dice 0,615
(mediana 0,713), FPV 29,4 mL, FNV 4,7 mL, FPV en negativos 53 mL. **Tercera ablación:
diferencia exactamente cero** en las 26 filas y las cinco columnas.

**Resultado principal del proyecto (validación, 26 estudios, 3 semillas por modelo):**

| | Dice (positivos) | FPV (mL) | FNV (mL) | FPV negativos (mL) |
|---|---|---|---|---|
| Referencia clásica (umbral SUV 2,5) | 0,180 | 1 192 | 5,6 | 1 224 |
| **A** · fusión temprana | **0,621 ± 0,016** | 20,9 ± 2,5 | 6,0 ± 0,4 | 36 |
| **B** · dos codificadores + concatenación | **0,612 ± 0,014** | 22,8 ± 3,1 | 5,4 ± 0,8 | 39 |
| **C** · B + atención cruzada | **0,612 ± 0,008** | 23,2 ± 6,7 | 5,9 ± 1,6 | 45 |

B y C coinciden hasta la tercera cifra; A queda 0,009 por encima, menos que su propia
desviación entre semillas. Por diagnóstico, el patrón se repite en los tres modelos y las nueve
corridas: pulmón 0,70–0,78, linfoma 0,67–0,72, melanoma 0,33–0,44. Frente a la referencia
clásica, cualquiera de los tres reduce los falsos positivos unas cincuenta veces.

**Las tres afirmaciones que sostiene el acto 1.**

1. *Cómo se fusionan PET y CT no cambia el resultado.* Con el mismo presupuesto de datos,
   entrenamiento y evaluación, y con tres semillas por brazo, las diferencias entre fusión
   temprana, codificadores separados y atención cruzada caben dentro del ruido de semillas.
2. *La atención cruzada aditiva en el cuello es inerte, y hay un mecanismo.* Tres corridas
   independientes (gamma inicial 0 en la piloto; gamma inicial 1 en las semillas 423, 2 y 3),
   y en las tres apagar el módulo en inferencia no cambia un solo vóxel. Causa medida: la
   atención converge a pesos casi uniformes, su salida es ~99 % constante entre posiciones, y
   la normalización de instancia (presente en toda la red) cancela exactamente cualquier señal
   constante. Gamma no informa: quedó en 0,0125, 1,00002, 0,9996 y 1,0046 en las cuatro
   corridas, es decir, no se movió en ninguna dirección.
3. *El aprendizaje profundo sí aporta, pero por otro lado.* El salto grande no está entre A, B
   y C: está entre cualquiera de ellos y el umbral clásico, y se produce en los falsos
   positivos, no en el Dice.

**Lo que limita el resultado, según los propios datos.** Las lesiones pequeñas (melanoma,
lesiones de 3 a 9 mL) y no la fusión; y unos pocos estudios que los nueve modelos fallan
igual (`f6295a93a6` con 104–128 mL de FP, `94962fe878` con 60–141, `e03b96666f` con 64–89 mL
de FNV). El análisis por órgano del Paso 5 dirá qué son.

**Estado del protocolo.** Nueve corridas terminadas con configuración idéntica salvo modelo y
semilla (verificado en los `resumen.json`); la piloto de C con gamma 0 queda documentada como
tal en `runs/C_piloto_gamma0`; el conjunto de prueba sigue sin abrirse. Siguiente: evaluación
del último checkpoint de las nueve (para acotar el costo del criterio de selección),
TotalSegmentator sobre validación y el análisis por órgano, intervalos por bootstrap,
detección por tamaño de lesión y ensamble de semillas. El test se abre una sola vez, al final,
con todos los brazos, incluidos los de la segunda parte.

## 2026-09-08 (tarde). Paso 5: dónde se equivoca cada quién, por órgano

TotalSegmentator sobre los 26 de validación (26/26 mapas), y `scripts/12` sobre las nueve
corridas más la referencia clásica. Es el análisis que llevábamos semanas esperando y cambia
el plan de la segunda parte.

**Falsos positivos por órgano (mL por estudio, media sobre semillas):**

| grupo | A | B | C | clásica |
|---|---|---|---|---|
| hígado | 0,2 | 1,0 | 1,0 | **349,1** |
| otro (tejido sin órgano asignado) | 6,6 | 7,7 | 8,7 | 217,8 |
| corazón | 0,4 | 1,7 | 1,7 | **141,9** |
| vejiga | 0,6 | 0,1 | 0,4 | **132,4** |
| riñones | 0,4 | 0,6 | 0,7 | **111,8** |
| intestino | 5,1 | 3,0 | 3,0 | 102,8 |
| bazo | 0,0 | 0,0 | 0,0 | 29,3 |
| hueso | 0,4 | 0,4 | 0,3 | 28,9 |
| músculo | 2,6 | 3,3 | 2,8 | 25,8 |
| vasos | 0,2 | 0,1 | 0,1 | 24,9 |
| pulmón | 2,5 | 2,5 | 2,1 | 7,7 |
| fuera del cuerpo | 1,7 | 1,5 | 1,4 | 0,0 |
| **TOTAL** | **20,9** | **22,8** | **23,2** | **1 191,9** |

**Hallazgo 1: el 74 % del fracaso de la referencia clásica es anatomía.** De sus 1 192 mL,
879 caen en órganos con captación fisiológica conocida (hígado, riñones, vejiga, corazón,
bazo, intestino, estómago). El umbral fijo de SUV 2,5 no sabe dónde está.

**Hallazgo 2: las redes ya resolvieron eso, y por eso ganan.** En los mismos órganos, A pone
6,7 de sus 20,9 mL, y la mayor parte es intestino (5,1), el de captación más variable. Hígado
0,2 contra 349. Riñones 0,4 contra 112. Vejiga 0,6 contra 132. Encéfalo y bazo, cero. La
ventaja de cincuenta veces del aprendizaje profundo **es exactamente esto**: aprendió la
anatomía funcional que el umbral ignora. Ahora podemos decirlo con números y no con intuición.

**Hallazgo 3, el que redirige la segunda parte.** El error que le queda a las redes NO está en
los órganos brillantes. Está en "otro" (6,6–8,7 mL: tejido blando sin órgano asignado, que es
donde viven los ganglios), en intestino, en músculo y en pulmón. Consecuencia para la rama N
(atlas de normalidad por órgano): **mejoraría muchísimo el brazo clásico y prácticamente nada
las redes**, porque ataca un problema que las redes ya tienen resuelto. Hay que decirlo antes
de gastar noches, y hay que reformular la rama (ver abajo).

**Los casos difíciles, diseccionados** (media de las nueve corridas):

- `f6295a93a6` (negativo, ~105 mL): **53 mL en pulmón** y 46 en "otro". Un paciente sin lesión
  anotada con algo captando en el pulmón. Candidato a proceso inflamatorio o infeccioso, o a
  un hallazgo no anotado. Hay que mirar la figura.
- `94962fe878` (melanoma, ~86 mL): **69 mL en músculo**. Captación muscular, el artefacto
  clásico del PET (tensión, ejercicio previo, o grasa parda).
- `1a90052cb2` (melanoma, ~74 mL): **37 mL en intestino** más 16 en "otro". Actividad
  intestinal, otro clásico.
- `4a72eeb991` (negativo, ~20 mL): casi todo en "otro".

Es decir: los tres casos que arrastran la media de FP **no son fallos de fusión ni de
arquitectura**; son captación fisiológica variable (músculo, intestino) y un caso pulmonar que
parece patología no tumoral. Ningún cambio de arquitectura los arregla.

**Dónde se pierden lesiones (FNV por órgano):** hueso 1,1–1,3 mL y "otro" 1,3–1,6 son los
mayores, con pulmón 0,9. Y dónde están las lesiones anotadas: "otro" 71,3 mL por estudio (la
carga ganglionar del linfoma), pulmón 36,5, hueso 17,2. O sea, **"otro" es a la vez donde vive
la mayor parte del tumor y donde la red se equivoca más**: es la región genuinamente difícil,
y nuestra agrupación de órganos la deja sin resolver.

**Acciones que salen de aquí.**
1. Desglosar "otro" con las 117 etiquetas finas de TotalSegmentator (ya guardadas en el campo
   `ts` de cada npz). Si buena parte es tejido ganglionar o subcutáneo, el informe puede
   nombrarlo. Cuesta código, no cómputo.
2. Reformular la rama N: el atlas de normalidad por órgano se propone como **mejora de la
   referencia clásica** (donde ataca el 74 % de sus errores), no como mejora de las redes. Eso
   sigue siendo un resultado fuerte y muy del espíritu del curso (híbrido clásico + IA), y es
   honesto.
3. Para las redes, la vía que sugieren estos números es la variabilidad fisiológica de músculo
   e intestino, no la anatomía estática: ahí un modelo de normalidad tendría que capturar
   distribuciones, no promedios.

Figuras: `docs/figuras/fp_por_organo_val.png` (barras apiladas) y `docs/figuras/casos_val.png`
(los cuatro casos con A, B y C, falsos positivos coloreados por órgano).

## 2026-09-09. Decisión: la segunda parte se acota a lo que la anotación sostiene

Persiguiendo el falso positivo de `f6295a93a6` llegamos a un límite del conjunto de datos, y
conviene dejarlo escrito porque cambia el plan.

**El límite.** autoPET anotó lesiones tumorales ávidas de FDG y nada más: la captación
reactiva, inflamatoria o granulomatosa no está marcada, y no hay informes ni contexto clínico
ni seguimiento. Medí el tejido que los modelos marcan en ese estudio: los vóxeles con SUV ≥ 15
tienen HU mediana 65 (RIC 53–76), densidad de partes blandas; solo el 1,1 % pasa de 150 HU, así
que no es grasa, ni contraste, ni calcio. Son ganglios hiliares y mediastínicos captantes en una
mujer de 81 años (estudio `PET-CT Ganzkoerper primaer mit KM`, 2006), con SUVmax 20,7. Sean
reactivos, granulomatosos o un hallazgo no anotado, **el conjunto no permite adjudicarlo**.

**La consecuencia.** Cualquier pregunta del tipo "¿este falso positivo es un error del modelo o
captación real que el protocolo excluyó?" es irresoluble con estos datos. No es que estén mal
anotados: están anotados para segmentar tumor ávido, y nosotros nos deslizamos hacia
interpretar la captación no tumoral, que es otra pregunta.

**Lo que NO cambia.** El acto 1 es internamente válido: A, B y C se compararon contra la misma
anotación, con el mismo protocolo y tres semillas. Que la anotación excluya lo inflamatorio no
favorece a ninguno de los tres. La conclusión se sostiene tal cual.

**Regla nueva para el cierre:** no hacer ninguna pregunta que la anotación no pueda contestar
por sí sola, es decir, que no se responda comparando la máscara del experto con la del modelo.

**Plan acordado (sin más entrenamientos).** Traducir el acto 1 a lenguaje clínico con análisis
que la anotación sostiene al 100 %:

1. Detección lesión por lesión y en función del tamaño (sensibilidad por volumen y por
   diagnóstico). Responde "¿a partir de qué tamaño el modelo encuentra la lesión?".
2. Carga de corrección: mililitros que el médico tendría que borrar y que tendría que añadir,
   frente a dibujar desde cero. Es la utilidad clínica real de la propuesta automática.
3. Concordancia de carga tumoral metabólica (MTV) predicha contra anotada, con Bland-Altman.
   Es el número que se usa para seguir respuesta al tratamiento.
4. Ensamble de las tres semillas por voto mayoritario, y mapa de desacuerdo como incertidumbre.
5. Intervalos de confianza por bootstrap en todas las tablas.
6. Evaluación del último checkpoint de las nueve corridas, para acotar el costo del criterio
   de selección ruidoso.
7. Prueba (49 estudios), **una sola vez**, al final, con todos los brazos.

Descartado por ahora: las ramas D, E y N del documento de traspaso, y cualquier brazo que
dependa de distinguir falso positivo real de anotación incompleta. Queda escrito como trabajo
futuro con la razón por la que no se hizo, que es un resultado en sí mismo: **para estudiar
falsos positivos fisiológicos en PET hace falta un conjunto anotado también para lo benigno**.

## 2026-09-09. Los resultados en lenguaje clínico (`scripts/16`)

Primer bloque del cierre, sin entrenar nada: todo sale de las máscaras ya guardadas y de la
anotación, que es lo único que estos datos pueden sostener.

**1. Detección lesión por lesión, por tamaño.** Cada componente 26-conexa de la anotación es
una lesión; se cuenta detectada si la predicción la toca. Sobre las 256 lesiones evaluables de
los 26 estudios de validación:

| tamaño de la lesión | lesiones | A | B | C |
|---|---|---|---|---|
| < 1 mL | 100 | 0,22 | 0,23 | 0,21 |
| 1–3 mL | 75 | 0,58 | 0,63 | 0,56 |
| 3–10 mL | 43 | 0,81 | 0,83 | 0,86 |
| 10–30 mL | 24 | 1,00 | 1,00 | 0,99 |
| 30–100 mL | 8 | 1,00 | 1,00 | 1,00 |
| ≥ 100 mL | 6 | 1,00 | 1,00 | 1,00 |

Este es el resultado más útil del proyecto para un clínico, y es el mismo en los tres modelos:
**por encima de 10 mL el modelo no pierde ninguna lesión; por debajo de 1 mL pierde cuatro de
cada cinco.** La transición está entre 1 y 10 mL. Explica de una vez el Dice bajo en melanoma
(lesiones de 3 a 9 mL, justo en la zona de transición) sin recurrir a "el modelo es peor en
melanoma", que era una lectura equivocada: es peor en lesiones pequeñas, y el melanoma las
tiene pequeñas.

**2. Carga de corrección** (mL por estudio, media sobre semillas):

| | borrar | añadir | corregir en total | dibujar desde cero | ahorro |
|---|---|---|---|---|---|
| A | 20,9 | 43,7 | 64,6 | 151,7 | 57 % |
| B | 22,8 | 43,5 | 66,3 | 151,7 | 56 % |
| C | 23,2 | 45,9 | 69,1 | 151,7 | 55 % |

Aviso honesto: compara **volúmenes**, no esfuerzo. Borrar un componente entero es más rápido
que delinear ese mismo volumen, así que el ahorro real probablemente sea mayor; pero esto es
un sustituto, no un estudio de tiempos. Se reporta como tal.

**3. Ensamble de las tres semillas por voto mayoritario** (solo inferencia, sin entrenar):

| | Dice (IC 95 %) | FPV | FNV | desacuerdo entre semillas |
|---|---|---|---|---|
| A | **0,662** (0,559–0,757) | 17,1 | 6,4 | 53 mL/estudio |
| B | 0,630 (0,521–0,731) | 17,9 | 5,4 | 60 mL/estudio |
| C | 0,643 (0,541–0,737) | 18,9 | 5,4 | 80 mL/estudio |

El ensamble sube A de 0,621 a **0,662** y baja el FPV de 20,9 a 17,1, gratis, a costa de tres
veces el tiempo de inferencia. Que un ensamble supere a sus miembros es esperable y conocido;
lo interesante es que el orden entre modelos no cambia y que C es el que más varía entre
semillas (80 mL de desacuerdo contra 53 de A), coherente con su mayor desviación en FPV. El
mapa de desacuerdo tiene además una lectura clínica directa: es dónde las tres semillas no se
ponen de acuerdo, es decir, dónde conviene que mire el médico.

**4. Concordancia de carga tumoral metabólica (MTV).** Sesgo medio −30,2 mL (el modelo
subestima), límites de concordancia de −244,5 a +184,1 mL. Son límites **anchos**, dominados
por los pocos casos de carga enorme. Conclusión honesta y negativa: con este rendimiento la
MTV automática no sirve todavía para seguir respuesta al tratamiento en pacientes de carga
alta, que es justo donde se usaría. Es una limitación que hay que declarar, no esconder.

Los intervalos son anchos porque solo hay 20 positivos evaluables en validación; en test habrá
39, y ahí las cifras serán más firmes.

Salidas: `results/deteccion_lesiones_val.csv`, `deteccion_por_tamano_val.csv`,
`correccion_val.csv`, `ensamble_val.csv`, `resumen_clinico_val.csv`;
figura `docs/figuras/clinico_val.png`.
