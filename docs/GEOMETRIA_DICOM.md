# Geometría DICOM del proyecto: posiciones de corte, espaciado y medidas (PET y CT)

Este documento cubre el punto del Laboratorio 1 que dice "construya el volumen ordenando los
cortes según `ImagePositionPatient`, determine el espaciado efectivo, compárelo con el
`SliceThickness` declarado y corrija la relación de aspecto", pero aplicado a los datos
reales del proyecto. Todo lo que sigue se midió sobre los tres primeros estudios de autoPET
con `src/petct/geometry.py` y `scripts/06_geometria_series.py`; la tabla completa está en
`results/geometria_series.csv` y la figura en `docs/figuras/geometria_posiciones_y_aspecto.png`.

Referencias del curso: estándar DICOM, Parte 3, módulo "Image Plane" (sección C.7.6.2) y
módulo "PET Image"; "Why Does the DICOM Standard Exist?"; documentación de pydicom.

## 1. El sistema de coordenadas del paciente

DICOM no mide en píxeles sino en milímetros dentro de un sistema fijo al paciente, llamado
LPS: el eje x crece hacia la izquierda del paciente (Left), el eje y hacia su espalda
(Posterior) y el eje z hacia su cabeza (Superior). El origen es un punto arbitrario que el
equipo fija al inicio del examen. `PatientPosition = HFS` (head first, supine) dice cómo
entró el paciente al gantry, y los tres estudios revisados lo declaran así.

Lo importante para el proyecto: PET, CT y segmentación de un mismo estudio comparten el
`FrameOfReferenceUID`, es decir, el mismo origen y los mismos ejes. Verificado en los tres
pacientes. Por eso se pueden superponer sin registro: un punto en mm del PET es el mismo punto
en mm del CT, aunque las grillas de píxeles sean distintas.

Analogía: dos mapas de la misma ciudad a escalas distintas. Las coordenadas GPS (mm) son las
mismas; lo que cambia es cuántos centímetros de papel ocupa cada cuadra (el espaciado).

## 2. Los atributos que describen un corte

| Atributo | Qué es | PET (los 3 estudios) | CT (varía por estudio) |
|---|---|---|---|
| `Rows`, `Columns` | tamaño de la matriz | 400 × 400 | 512 × 512 |
| `PixelSpacing` | (entre filas, entre columnas), mm | 2,036 × 2,036 | 0,758 a 0,873 |
| campo de visión en el plano | `Rows × PixelSpacing` | 815 mm | 388 a 447 mm (= `ReconstructionDiameter`) |
| `ImagePositionPatient` | (x, y, z) en mm del centro del primer píxel de cada corte | z de −1104 a −256 (ejemplo) | mismo rango de z que el PET |
| `ImageOrientationPatient` | cosenos de columnas y de filas | 1,0,0 / 0,1,0 (axial puro) | 1,0,0 / 0,1,0 |
| `SliceThickness` | grosor nominal del corte | 3,0 mm | 2,0 o 3,0 mm |
| `SpacingBetweenSlices` | distancia declarada entre cortes | ausente | ausente |
| espaciado efectivo (medido) | diferencia entre posiciones consecutivas | 3,0 mm, uniforme | 1,0 o 2,5 mm, uniforme |
| cortes | | 284 | 340 u 852 |
| extensión en z | | 852 mm | 851 a 853 mm |

Dos detalles que confunden a todo el mundo la primera vez. `PixelSpacing` viene en orden
(fila, columna), o sea (Δy, Δx); en estos datos son iguales, pero el código nunca debe
suponerlo. Y `ImageOrientationPatient` trae primero la dirección en que avanzan las columnas
(el eje x del píxel) y después la de las filas (el eje y del píxel); la normal al corte es el
producto cruz de ambas y en axial puro da (0, 0, 1): cada corte siguiente está más arriba.

## 3. La ecuación que une índices y milímetros

Para el píxel de la fila i, columna j del corte k:

    P(i, j, k) = ImagePositionPatient_k + j · Δcol · dir_col + i · Δfila · dir_fila

y, si los cortes están equiespaciados a Δz a lo largo de la normal n,
`ImagePositionPatient_k = ImagePositionPatient_0 + k · Δz · n`. Es una transformación afín:
una matriz 3 × 3 (espaciado por dirección) más un origen. SimpleITK la guarda exactamente así
(`GetOrigin`, `GetSpacing`, `GetDirection`) y es lo que lee `convert.py`. NIfTI guarda la
misma matriz pero en el sistema RAS (x hacia la derecha, y hacia adelante), así que al pasar
de DICOM a NIfTI los signos de x e y se invierten; SimpleITK lo hace solo y `nibabel`
muestra la matriz ya en RAS. Un vóxel es un vóxel en ambos; lo que cambia es el rótulo de los
ejes.

En el proyecto: `index_to_mm` en `geometry.py` implementa la ecuación y una prueba la
verifica con números a mano.

## 4. El orden de los cortes: nombre, `InstanceNumber` o posición

El Laboratorio 1 advierte que el orden alfabético de los archivos no garantiza el orden
anatómico. En autoPET los archivos se llaman `1-001.dcm`, `1-002.dcm`, … y el hallazgo es
que **el PET viene de los pies a la cabeza y el CT de la cabeza a los pies**: en el PET el
archivo 001 tiene la z más baja (−1104 mm) y en el CT el archivo 001 tiene la z más alta
(−256 mm). `InstanceNumber` sigue el mismo orden que el nombre en ambos, así que tampoco
sirve como criterio único. El único criterio robusto es proyectar `ImagePositionPatient` sobre
la normal y ordenar por ese número, que es lo que hace `series_geometry` y lo que hace
SimpleITK al leer una serie. La figura lo muestra: la z del PET sube con el índice del
archivo, la del CT baja.

Consecuencia práctica ya documentada en la bitácora: en los NIfTI el índice 0 del eje z es el
corte más inferior (`head_at_end = True`), y toda regla que dependa de "arriba" o "abajo" lo
lee de la geometría, no lo supone.

## 5. Espaciado efectivo frente a grosor de corte

Son dos cosas distintas. El grosor (`SliceThickness`) es cuánto tejido promedia cada corte
reconstruido; el espaciado es cada cuántos milímetros hay un corte. En el PET coinciden:
cortes de 3 mm cada 3 mm, contiguos, sin hueco ni solape. En el CT no: dos estudios tienen
cortes de 3 mm cada 2,5 mm y el tercero cortes de 2 mm cada 1 mm. Es reconstrucción con
solape, habitual en CT helicoidal: cada corte comparte medio milímetro (o un milímetro
entero) con el vecino. Nada está mal en los datos; lo que estaría mal es usar el grosor como
espaciado para armar el volumen, porque el cuerpo saldría un 20 % (o un 100 %) más largo de lo
que es.

`SpacingBetweenSlices` no viene en ninguna de las seis series, así que el espaciado hay que
medirlo siempre. En las seis series el muestreo es uniforme (desviación estándar de las
diferencias igual a cero al centésimo de milímetro).

Analogía: el grosor es el ancho de la brocha; el espaciado es cuánto se desplaza la brocha
entre pasadas. Con pasadas más cortas que la brocha, la pintura se solapa.

## 6. Medidas en el plano y campo de visión

El PET reconstruye un campo de visión de 815 mm con píxeles de 2,04 mm; el CT, entre 388 y
447 mm con píxeles de 0,76 a 0,87 mm, y el diámetro se elige por paciente
(`ReconstructionDiameter`). Por eso el CT no cubre todo el campo del PET: cuando `CTres`
remuestrea el CT sobre la grilla del PET, los vóxeles del PET que quedan fuera del CT reciben
−1024 HU (aire). Es correcto y esperable; lo que hay que recordar es que un vóxel de PET
"fuera del CT" no es cuerpo aunque tenga actividad (brazos en el borde, camilla).

Una distancia en el plano axial se mide multiplicando píxeles por `PixelSpacing`. Un vóxel del
PET tiene 2,036 × 2,036 × 3 = 12,4 mm³ (0,0124 mL); un vóxel del CT de este estudio
0,80 × 0,80 × 2,5 = 1,6 mm³. Todas las métricas en mL del proyecto (MTV, FPV, FNV) se
calculan con el volumen del vóxel de la grilla en que se está, nunca contando vóxeles a secas.

## 7. Relación de aspecto y el error que se comete al ignorarla

En un corte coronal o sagital, el eje vertical es z y el horizontal es x o y. Si se dibuja el
arreglo tal cual, con píxeles cuadrados, cada corte ocupa un píxel de alto aunque mida 3 mm, y
la imagen sale aplastada. El factor de corrección es Δz / Δplano: 1,47 para el PET y 3,13
para el CT de 0,80 mm (1,32 para el CT de 0,76 × 1,0 mm). La figura muestra los cuatro casos.

El error de medida es directo. Un segmento vertical de longitud L medido en una imagen sin
corregir aparece con L · (Δplano / Δz): en el PET un tumor de 30 mm de alto "mide" 20 mm (32 %
menos); en el CT de 2,5 mm, 9,6 mm (68 % menos). Un segmento horizontal no se afecta y uno
oblicuo queda entre ambos extremos; `measurement_error_if_aspect_ignored` en `geometry.py`
calcula el error para cualquier ángulo y una prueba lo verifica. En el proyecto esta
corrección deja de ser un problema después del Paso 2, porque todo se remuestrea a 3 mm
isotrópicos: ahí un vóxel es un cubo y cualquier vista se dibuja con aspecto 1.

## 8. El caso especial de la segmentación (DICOM SEG)

La máscara no viene como una serie de cortes sino como un único objeto multiframe: un archivo
con 284 frames, cada uno con su propia `ImagePositionPatient` en `PerFrameFunctionalGroups` y
la orientación y el espaciado compartidos en `SharedFunctionalGroups`. Hallazgo importante:
los frames vienen con las filas en sentido contrario al PET (`ImageOrientationPatient`
1,0,0,0,−1,0) y la posición del frame es la de la última fila del PET. Si se apilan sin mirar
la orientación, la máscara queda reflejada y cae fuera de las lesiones (SUV medio 0,9 en vez
de 4). `seg_to_mask` ubica las dos esquinas físicas de cada frame en la grilla del PET y
voltea filas o columnas cuando la esquina "última" cae antes que la "primera". El fantoma de
las pruebas reproduce esa orientación desde entonces.

## 9. Resumen de los tres estudios

| Paciente | Serie | Cortes | Píxel (mm) | Grosor (mm) | Espaciado medido (mm) | Solape | Orden alfabético = anatómico | Aspecto coronal |
|---|---|---|---|---|---|---|---|---|
| PETCT_0117d7f11f | PT | 284 | 2,036 | 3,0 | 3,0 | no | sí (pies → cabeza) | 1,47 |
| PETCT_0117d7f11f | CT | 852 | 0,758 | 2,0 | 1,0 | 1,0 mm | no (cabeza → pies) | 1,32 |
| PETCT_04606080a0 | PT | 284 | 2,036 | 3,0 | 3,0 | no | sí | 1,47 |
| PETCT_04606080a0 | CT | 340 | 0,799 | 3,0 | 2,5 | 0,5 mm | no | 3,13 |
| PETCT_37472e737f | PT | 284 | 2,036 | 3,0 | 3,0 | no | sí | 1,47 |
| PETCT_37472e737f | CT | 340 | 0,873 | 3,0 | 2,5 | 0,5 mm | no | 2,86 |

Otros datos de la cabecera que conviene saber decir: PET Siemens reconstruido con PSF + TOF,
2 iteraciones y 21 subconjuntos, filtro gaussiano de 2 mm, corrección de atenuación medida con
el CT; CT a 120 kV con kernel B31f (tejido blando).

## 10. Para la defensa, en una frase cada una

Cómo se ordenan los cortes: por la proyección de `ImagePositionPatient` sobre la normal al
plano; ni por nombre ni por `InstanceNumber`, porque en autoPET el CT viene invertido respecto
del PET.

Cómo se mide el espaciado: restando posiciones consecutivas ya ordenadas; en estos datos es
uniforme, 3 mm en PET y 1 o 2,5 mm en CT, con cortes de CT que se solapan porque el grosor es
mayor que el espaciado.

Por qué PET y CT se superponen sin registrar: comparten `FrameOfReferenceUID`; la
correspondencia es por milímetros, y `CTres` es el CT remuestreado sobre la grilla del PET.

Qué pasa si se ignora la relación de aspecto: en coronal y sagital las distancias verticales se
acortan por Δplano/Δz (32 % en PET, hasta 68 % en CT); en el proyecto se evita remuestreando a
3 mm isotrópicos.

Qué tiene de particular la segmentación: es un objeto multiframe con orientación de filas
invertida; se convierte por posición física de cada frame, no por orden.
