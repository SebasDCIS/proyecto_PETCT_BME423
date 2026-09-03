# Glosario del proyecto, con analogías

Crece con cada paso. Cada entrada tiene tres capas: qué es (definición corta), la analogía,
y qué debes saber decir si te lo preguntan en la defensa. Los términos del Paso 0–1 están
primero; los de pasos posteriores se agregan al final con su fecha.

---

## Paso 0 · Herramientas de trabajo

**Repositorio git / GitHub.** Un cuaderno de laboratorio con máquina del tiempo: cada
*commit* es una foto del proyecto con fecha y explicación, y GitHub es la copia en la nube
que el profesor puede abrir. *Para la defensa:* el historial de commits demuestra trabajo
sistemático; la rúbrica lo evalúa.

**Bitácora (`BITACORA.md`).** El diario del cuaderno: qué se hizo, por qué, qué se decidió,
qué falló. *Para la defensa:* de aquí sale la sección "riesgos y ajustes" de la entrega
parcial sin tener que reconstruir nada de memoria.

**`configs/default.yaml`.** El panel de control: todos los números (semilla, resolución,
ventana, tamaño de parche) en un solo archivo. Analogía: los diales del scanner escritos en
la hoja de protocolo, no repartidos por los cajones. *Para la defensa:* "cambié un
parámetro" siempre es un cambio en este archivo, visible en git.

**Pruebas unitarias (`tests/`, pytest).** Fantomas de control de calidad para el código:
objetos con respuesta conocida (una esfera de SUV 8 sobre fondo 1) que se pasan por el
pipeline para verificar que sale lo esperado. Igual que el fantoma de calidad del PET cada
mañana. *Para la defensa:* "el pipeline se validó con un fantoma sintético antes de tocar
datos reales; 8 pruebas automáticas".

**Semilla (`seed = 423`).** El número que fija el "azar": con la misma semilla, el sorteo
de pacientes y la partición salen idénticos en cualquier computador. Analogía: barajar
siempre con la misma secuencia de movimientos. *Para la defensa:* reproducibilidad.

---

## Paso 1 · Datos, DICOM y SUV

**DICOM.** El formato universal de imagen médica: un archivo por corte que lleva los
píxeles y una ficha con cientos de etiquetas (paciente, geometría, dosis, hora). Analogía:
cada corte es una foto con su reverso escrito a mano. *Para la defensa:* el SUV se calcula
leyendo ese reverso; sin las etiquetas correctas no hay SUV.

**Serie, estudio, paciente.** Paciente → estudio (una visita al scanner) → series (el CT,
el PET, la segmentación). En TCIA cada serie tiene un identificador único
(`SeriesInstanceUID`) y se descarga como una carpeta.

**NIfTI (`.nii.gz`).** Un solo archivo por volumen 3D con su geometría (origen, espaciado,
orientación). Es el formato con el que trabajan MONAI, nibabel y SimpleITK. Analogía: el
libro encuadernado en vez de las hojas sueltas del DICOM.

**Bq/mL.** Becquerel por mililitro: cuántas desintegraciones por segundo hay en cada
mililitro de tejido. Es lo que el PET reconstruye físicamente. Un becquerel es una
desintegración por segundo.

**SUV (Standardized Uptake Value).** Actividad del vóxel dividida por la actividad que
habría si la dosis inyectada se repartiera uniforme en el cuerpo:
`SUV = A[Bq/mL] / (dosis_corregida[Bq] / peso[g])`. Analogía: repartir un frasco de
tinta en una piscina; el SUV dice cuántas veces más concentrada está la tinta en un rincón
que el promedio de la piscina. *Para la defensa:* SUV 1 = captación promedio; el umbral
clásico de sospecha es 2,5; el encéfalo y la vejiga lo superan siempre, por eso el umbral
solo no sirve.

**SUVbw.** SUV normalizado por peso corporal (*body weight*); existen variantes por masa
magra (SUVlbm) y superficie corporal (SUVbsa). autoPET usa bw.

**Corrección de decaimiento.** El ¹⁸F pierde la mitad de su actividad cada 109,8 min. Si
se inyectó a las 10:00 y se escaneó a las 11:00, en el cuerpo queda `2^(−60/109,8) ≈ 68 %`
de la dosis; el SUV usa esa dosis restante. Analogía: el hielo que se derrite entre que lo
compras y lo usas. *Para la defensa:* `DecayCorrection = START` significa que el scanner ya
refirió las cuentas al inicio de la serie, por eso se usa `SeriesTime`.

**RescaleSlope / RescaleIntercept.** Los píxeles del DICOM son enteros; estas dos etiquetas
los convierten a unidades físicas (`valor = píxel × slope + intercept`). SimpleITK lo
aplica solo al leer. Analogía: la escala del mapa.

**Etiquetas del SUV.** `PatientWeight`, `RadionuclideTotalDose`, `RadionuclideHalfLife`,
`RadiopharmaceuticalStartTime`, `SeriesTime`, `Units = BQML`. Si alguna falta, el estudio se
descarta y se registra en `errores_conversion.csv`.

**Remuestreo (CTres).** Volver a muestrear el CT (vóxeles de ~1 × 1 × 3 mm) sobre la grilla
del PET (2 × 2 × 3 mm) para que ambos tengan las mismas dimensiones y cada vóxel del PET
tenga "su" vóxel de CT. Analogía: re-fotografiar un mapa detallado con la cámara de menor
resolución para superponerlo exactamente. *Para la defensa:* la red necesita que PET y CT
sean tensores del mismo tamaño y alineados vóxel a vóxel; el registro entre PET y CT ya
viene hecho por el equipo híbrido.

**Interpolación lineal.** Cómo se calcula el valor de un vóxel nuevo a partir de los
vecinos originales: un promedio ponderado por distancia. Para máscaras (0/1) se usa
*vecino más cercano* para no inventar valores intermedios.

**DICOM SEG.** El objeto DICOM que guarda una segmentación: una pila de *frames* binarios,
cada uno con la posición física del corte al que pertenece. *Para la defensa:* se convierte
ubicando cada frame por su posición (`ImagePositionPatient`), no por su orden en el archivo;
el test lo verifica con frames desordenados a propósito.

**Máscara binaria.** Volumen de ceros y unos: 1 = lesión, 0 = resto. Es lo que la red
aprende a producir y contra lo que se calcula el Dice.

**Estratificación.** Elegir el subconjunto respetando las proporciones de cada grupo
(pulmón, linfoma, melanoma, negativos). Analogía: una encuesta que entrevista a personas de
cada región en proporción, no solo a las de la capital.

**Partición por paciente (train / val / test).** Entrenamiento (la red aprende), validación
(se eligen hiperparámetros y se decide cuándo parar) y prueba (se reporta una sola vez, al
final). Se parte **por paciente** para que los cortes de una misma persona no queden en dos
lados. Analogía: no se puede estudiar con las mismas preguntas del examen. *Para la defensa:*
"fuga de datos" (*data leakage*) es el error clásico que infla resultados; la partición por
paciente lo evita.

**TCIA / NBIA.** The Cancer Imaging Archive y su servidor de descarga. La API pública
permite listar pacientes y series y bajar carpetas DICOM sin cuenta para colecciones CC BY.
`tcia_utils` es el paquete Python que envuelve esa API.

**CC BY 4.0.** Licencia que permite usar y redistribuir los datos con atribución. La versión
*defaced* (rostro anonimizado) de FDG-PET-CT-Lesions está bajo esta licencia; la original,
no.

---

## Términos que aparecerán en los próximos pasos (para ir leyendo)

**Ventaneo HU** (Paso 2), **normalización**, **recorte del cuerpo**, **parche 3D**,
**muestreo sesgado a lesiones**, **apertura/cierre morfológico**, **U-Net 3D**, **canal de
entrada**, **cuello de botella**, **codificador/decodificador**, **atención cruzada (Q, K,
V)**, **pérdida Dice + entropía cruzada**, **precisión mixta**, **checkpoint**, **ventana
deslizante**, **Dice**, **HD95**, **FPV/FNV**, **bootstrap**. Cada uno se agrega aquí con su
analogía cuando se implemente.

---

## Agregados el 2026-09-03 (tarde) · Entorno y cuadernos

**Cuaderno (notebook, `.ipynb`).** Un documento donde se alternan celdas de texto y
celdas de código, y el código se ejecuta ahí mismo mostrando su salida debajo.
Analogía: el cuaderno de laboratorio donde al lado de cada cálculo escribes por qué lo
hiciste y qué salió. *Para la defensa:* los cuadernos son la explicación paso a paso;
el código "de verdad" vive en `src/petct` y se prueba con `pytest`, para que un
cuaderno mal ejecutado no rompa el proyecto.

**Kernel.** El proceso de Python que ejecuta las celdas del cuaderno. En VS Code se
elige el kernel del entorno virtual `.venv` para que encuentre los paquetes instalados.

**Entorno virtual (`.venv`).** Una carpeta con su propia copia de Python y sus
paquetes, separada del resto del computador. Analogía: una caja de herramientas por
proyecto, para que las versiones de uno no rompan al otro.

**CUDA.** La plataforma de NVIDIA que PyTorch usa para calcular en la GPU. Es lo que
tiene Colab. Es el camino más maduro para redes 3D.

**MPS (Metal Performance Shaders).** La puerta de PyTorch al chip gráfico de los Mac con
chip M. Funciona para desarrollar y entrenar cosas medianas; algunas operaciones 3D
todavía caen a la CPU y no hay tanta madurez como en CUDA. *Para la defensa:* "el
desarrollo y las pruebas cortas se hicieron en un Mac con MPS; los entrenamientos
completos, en Colab con CUDA; los tiempos de cada uno están en la bitácora".

**Memoria unificada.** En los Mac con chip M la CPU y la GPU comparten la misma RAM.
Ventaja: la GPU puede usar mucha memoria (no está limitada a los 16 GB de una T4).
Desventaja: el sistema y la GPU compiten por ella.

**MIP (proyección de intensidad máxima).** La "foto" clásica del PET: para cada línea
que atraviesa el cuerpo se toma el vóxel más brillante y se dibuja en 2D. Sirve para ver
de un vistazo dónde hay captación alta y si las lesiones anotadas caen sobre zonas
calientes. Se calcula con `suv.max(axis=1)` para la vista coronal.


---

## Paso 2 · Preprocesamiento, métricas y referencia clásica

**Vóxel isotrópico.** Vóxel con el mismo tamaño en las tres direcciones (3 × 3 × 3 mm).
Analogía: ladrillos cúbicos en vez de ladrillos alargados; una esfera se ve como esfera y
no como huevo. *Para la defensa:* las convoluciones 3D asumen que un desplazamiento de un
vóxel significa lo mismo en x, y, z.

**Ventaneo HU.** Recortar el rango del CT a un intervalo (−200 a 300 HU) y llevarlo a
[0, 1]. Es exactamente la ventana de tejido blando de la consola. *Para la defensa:* es
una operación puntual (módulo 3 del curso); no cambia la forma, solo el contraste.

**Tope del SUV (clip).** SUV/30, y todo lo que pasa de 30 se queda en 1. La vejiga y los
riñones no dominan la escala. *Para la defensa:* el SUV real se recupera multiplicando por
30; las métricas se calculan siempre con SUV real.

**Máscara del cuerpo.** Todo lo que no es aire en el CT, componente más grande (elimina
la camilla), con huecos rellenados. Sirve para recortar y para que los parches "de fondo"
caigan dentro del paciente.

**Componente conexa.** Un grupo de vóxeles encendidos que se tocan (aquí, por caras,
aristas o vértices: 26 vecinos). Analogía: las islas de un archipiélago. Todo el
análisis de falsos positivos y negativos se hace por isla, no por vóxel.

**Apertura morfológica.** Erosión seguida de dilatación con un elemento estructurante
(una bola de radio 1). Borra islas más chicas que la bola y separa islas unidas por un
puente delgado. Módulo 9 del curso.

**Parche 3D y muestreo sesgado.** Cubo de 96³ vóxeles recortado del estudio. Con
probabilidad 0,7 se centra en un vóxel de lesión. Analogía: para enseñar a alguien a
reconocer una especie rara de ave no le muestras el bosque entero al azar; le muestras
muchos árboles donde sí está el ave y algunos donde no.

**Dice.** `2 |A ∩ B| / (|A| + |B|)`. 1 es perfecto, 0 es nada. Solo se calcula donde hay
lesión anotada. *Para la defensa:* es sensible al tamaño; una lesión de 8 vóxeles con dos
vóxeles corridos ya baja mucho el Dice.

**FPV (false positive volume).** Mililitros de islas predichas que no tocan ninguna
lesión anotada. Lo que la red inventó. **FNV (false negative volume).** Mililitros de
lesiones anotadas que ninguna predicción tocó. Lo que la red no vio. *Para la defensa:*
son las métricas del reto porque un radiólogo puede corregir un borde impreciso, pero no
una lesión inventada en el cerebro ni una que falta.

**MTV.** Volumen tumoral metabólico: mililitros de la máscara. **SUVmax.** El vóxel más
caliente dentro de la máscara. Son los biomarcadores que un falso positivo distorsiona.

**Referencia clásica (baseline).** La receta sin red: umbral, apertura, tamaño mínimo,
exclusión anatómica. *Para la defensa:* "en el paciente sintético el umbral solo da FPV
de casi un litro; la exclusión anatómica lo lleva a cero. Los modelos con CT intentan
aprender esa regla en vez de codificarla a mano."

**Máscaras heurísticas de órganos.** Reglas provisionales (posición relativa en el eje
z, volumen, SUV máximo) para encéfalo y vejiga. Se reemplazan por segmentación del CT
(TotalSegmentator) cuando haya estudios reales.

---

## Geometría DICOM (ver `docs/GEOMETRIA_DICOM.md` para el desarrollo completo)

**Sistema LPS.** Los ejes del paciente en DICOM: x hacia la izquierda, y hacia atrás, z
hacia la cabeza, en mm. NIfTI usa RAS (x derecha, y adelante): mismos vóxeles, signos de x
e y invertidos. *Para la defensa:* "PET, CT y SEG comparten el sistema y el
`FrameOfReferenceUID`; por eso se superponen por milímetros sin registrar".

**`ImagePositionPatient`.** Coordenadas (x, y, z) en mm del centro del primer píxel de
cada corte. Es el único criterio robusto para ordenar cortes. Analogía: la coordenada GPS
de la esquina de cada foto.

**`ImageOrientationPatient`.** Seis cosenos: hacia dónde avanzan las columnas y hacia dónde
las filas. Su producto cruz es la normal al corte. En el SEG de autoPET las filas van al
revés que en el PET.

**`PixelSpacing`.** Tamaño del píxel en mm, en orden (fila, columna). El campo de visión es
`Rows × PixelSpacing`: 815 mm en el PET, 388 a 447 mm en el CT.

**Grosor de corte frente a espaciado.** `SliceThickness` es cuánto tejido promedia un corte;
el espaciado es cada cuántos mm hay uno. En el CT de autoPET los cortes de 3 mm van cada
2,5 mm (solape). Analogía: ancho de la brocha frente a desplazamiento entre pasadas.

**Espaciado efectivo.** Diferencia entre posiciones consecutivas ya ordenadas. Se mide
porque `SpacingBetweenSlices` no viene. Uniforme en las seis series revisadas.

**Relación de aspecto.** Δz / Δplano: 1,47 en PET, hasta 3,13 en CT. Si se ignora, las
medidas verticales en coronal o sagital se acortan hasta un 68 %. A 3 mm isotrópicos vale 1.

**Solape de reconstrucción.** Cortes más gruesos que el espaciado; cada corte comparte
tejido con el vecino. Es normal en CT helicoidal y no es un error de los datos.

**Multiframe (SEG).** Un solo archivo con muchos frames, cada uno con su posición.
Se convierte ubicando cada frame por sus esquinas físicas.
