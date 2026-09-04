# Herramientas del proyecto: qué es cada una, para qué la uso, por qué esa y no otra

El objetivo final es uno solo: entrenar y comparar tres redes que segmentan lesiones en
PET/CT, medirlas con las métricas del reto autoPET y explicar en qué órganos se equivoca
cada una. Todo lo de esta lista existe para llegar ahí con resultados reproducibles y
defendibles. Las agrupo por la etapa en que entran.

## Infraestructura de trabajo

**Python 3.12 y el entorno virtual (`.venv`).** El lenguaje de todo el proyecto y una
caja de herramientas propia por proyecto: los paquetes se instalan dentro de `.venv` y no
mezclan versiones con otros trabajos. Uso 3.12 y no 3.14 porque las librerías científicas
publican sus binarios con retraso para las versiones nuevas. Analogía: cada proyecto con
su propia caja de herramientas, en vez de un cajón común donde se pierden las piezas.

**VS Code con la extensión Jupyter.** Editor donde escribo código y ejecuto cuadernos.
Ventaja frente a Colab para el trabajo diario: los archivos están en mi disco, el kernel es
mi `.venv`, y git está integrado. Colab entra solo para entrenar con GPU.

**git y GitHub.** Control de versiones y copia en la nube. Cada commit es una foto con
fecha y explicación. Es la evidencia de trabajo sistemático que pide la rúbrica y la forma
en que el profesor puede ver el código. Regla del proyecto: los datos, el entorno virtual,
los modelos y los registros nunca se suben (`.gitignore`); solo código, documentos,
manifiestos y figuras.

**Terminal (zsh).** Donde corren los scripts largos (descarga, conversión), porque no
dependen de que una app siga abierta y `caffeinate` mantiene el Mac despierto.

**pytest.** Corre las pruebas automáticas. Cada función importante tiene una prueba con
un fantoma sintético de respuesta conocida. Analogía: el fantoma de control de calidad
del PET cada mañana. Hoy son 25 pruebas y se ejecutan en un segundo.

**YAML (`configs/default.yaml`).** Formato de texto simple para la configuración. Todos
los números del proyecto viven ahí; cambiar uno es un commit visible.

**Jupyter / nbconvert.** Los cuadernos (`.ipynb`) mezclan texto, código y salidas.
`nbconvert` los ejecuta desde la Terminal para dejarlos con resultados guardados. Los
cuadernos se generan desde `notebooks/build_notebooks.py` para versionarlos como texto.

## Obtención de los datos

**The Cancer Imaging Archive (TCIA) y su API NBIA.** El archivo público donde vive
autoPET. La API permite consultar series y descargar sin cuenta para colecciones CC BY.
Alternativa: el NBIA Data Retriever (aplicación de escritorio), que abre un manifiesto
`.tcia`; la dejé como plan B porque el script cubre lo mismo y es reproducible.

**tcia_utils.** Paquete Python que envuelve la API de NBIA: consultar metadatos de
series por lote y descargarlas por identificador. Elegí esto sobre escribir las llamadas
HTTP a mano porque maneja reintentos, saltos de lo ya descargado y descarga en paralelo.

## Lectura y geometría de imágenes

**pydicom.** Lee y escribe archivos DICOM: metadatos (peso, dosis, horas, posiciones,
orientaciones) y píxeles. Lo uso para el cálculo del SUV, para la geometría y para el
DICOM SEG multiframe. Es la referencia en Python para DICOM y la que usa el curso.

**SimpleITK.** Lee series DICOM como volúmenes con geometría (origen, espaciado,
dirección), aplica `RescaleSlope/Intercept`, remuestrea entre grillas y escribe NIfTI.
Lo elegí sobre `dicom2nifti` porque me da control total de la geometría, y sobre hacerlo
a mano con NumPy porque el remuestreo con interpolación en 3D es exactamente lo que hace
bien. Analogía: la mesa de trabajo donde las imágenes ya vienen con su regla en mm.

**nibabel.** Lector ligero de NIfTI. Lo uso poco (SimpleITK cubre casi todo) pero es lo
que usan MONAI y los cuadernos del curso; conviene conocer su matriz afín en RAS.

**NIfTI (`.nii.gz`).** El formato de destino: un archivo por volumen 3D con geometría.
Es lo que entienden MONAI, nibabel y SimpleITK sin fricción.

## Procesamiento clásico y métricas

**NumPy.** Los arreglos. Todo volumen es un arreglo 3D; todo cálculo (SUV, ventanas,
máscaras, Dice) es aritmética de arreglos. Es la base de todo lo demás.

**SciPy (`scipy.ndimage`).** Componentes conexas (`label`), morfología binaria
(`binary_opening`, `binary_fill_holes`), centros de masa. Lo uso para la máscara del
cuerpo, la limpieza de la referencia clásica y las métricas FPV/FNV por isla.

**scikit-image.** Elementos estructurantes (`ball`) y herramientas de morfología e
imagen del curso. Complementa a SciPy.

**pandas.** Tablas: el CSV clínico, los manifiestos, las tablas de resultados, la
geometría por serie. Es el formato natural para agrupar, filtrar y promediar.

**matplotlib.** Todas las figuras: MIP coronales con contornos, curvas de ventana,
tablas de geometría dibujadas. Simple y suficiente; las figuras del informe salen de aquí.

## Aprendizaje profundo (Paso 3 en adelante)

**PyTorch.** El motor de redes neuronales: tensores, gradientes, capas, optimizadores.
Elegido por ser el estándar en imagen médica y porque MONAI se construye sobre él. En el
Mac usa el chip gráfico de Apple a través de `mps`; en Colab, CUDA.

**MONAI.** Librería de PyTorch para imagen médica: transformaciones 3D, U-Net 3D lista,
pérdida Dice + entropía cruzada, inferencia por ventana deslizante, métricas. Me ahorra
escribir la U-Net y el recorrido del volumen desde cero y es lo que usa la comunidad del
reto. La parte propia del proyecto (los codificadores duales y la atención cruzada) la
escribo yo encima, con `torch.nn`.

**Google Colab.** Cuadernos en la nube con GPU NVIDIA. Entra para los entrenamientos
completos (25 000 iteraciones por modelo), que en la GPU del Mac serían lentos o no
cabrían. Requiere puntos de control frecuentes porque las sesiones se cortan.

**TotalSegmentator (pendiente).** Red preentrenada que segmenta más de cien órganos en
un CT. La usaré para tener máscaras de órganos reales (corazón, riñones, vejiga, hígado,
intestino) y reemplazar las reglas heurísticas: es lo que hace posible el análisis de
falsos positivos por órgano.

## Cómo encajan

TCIA y `tcia_utils` traen los DICOM. `pydicom` y SimpleITK los convierten en NIfTI con SUV
y CT alineado. NumPy, SciPy y scikit-image los dejan a 3 mm, recortados y escalados, y
construyen la referencia clásica. `pandas` y `matplotlib` miden y muestran. PyTorch y
MONAI entrenan los tres modelos, en el Mac para probar y en Colab para el presupuesto
completo. TotalSegmentator aporta la anatomía para saber dónde se equivoca cada uno. Git,
pytest, la bitácora y los cuadernos hacen que todo sea reproducible y explicable.
