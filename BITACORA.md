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
