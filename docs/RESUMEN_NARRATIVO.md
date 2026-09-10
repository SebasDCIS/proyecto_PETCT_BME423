# El proyecto contado de principio a fin

*Mini-proyecto BME423 — Procesamiento de Imágenes Médicas · Sebastián Inostroza · versión del 2026-09-10*

Este documento existe para una sola cosa: que cualquiera que lo lea —incluido yo mismo dentro de
tres meses, frente al profesor— entienda **qué busca el proyecto, qué problema resuelve, cómo lo
resuelve y con qué materiales**. Está escrito como narración, no como informe técnico, y cada
término complejo se define la primera vez que aparece. Los números y las decisiones detrás de cada
afirmación están en `BITACORA.md`, `docs/PROTOCOLO_CONGELADO.md` y `docs/GLOSARIO.md`.

---

## 1. La escena que da origen a todo

Un paciente con linfoma llega a control. Le inyectan un azúcar marcado, esperan una hora y lo
pasan por una máquina que produce dos imágenes del cuerpo entero al mismo tiempo. El médico
nuclear se sienta frente a la pantalla y tiene que contestar preguntas que suenan simples y no lo
son: *¿cuántas lesiones hay? ¿dónde? ¿cuánto tumor activo tiene este paciente en total? ¿es más o
menos que hace tres meses?*

Para responder la tercera pregunta —la del total— hay que **dibujar** cada lesión, vóxel por
vóxel, sobre las imágenes.

> **Vóxel**: la versión tridimensional de un píxel. Si un píxel es un cuadradito de una foto, un
> vóxel es un cubito de un volumen. En este proyecto cada vóxel mide 3 × 3 × 3 mm.

Dibujar todas las lesiones de un estudio de cuerpo entero a mano toma entre 30 y 90 minutos de
trabajo de un especialista. En la práctica, casi nadie lo hace: se mide la lesión más grande, se
anota "múltiples focos" y se sigue. La medida que de verdad correlaciona con el pronóstico —el
volumen total de tumor activo— **se pierde por costo de tiempo**.

Ese es el problema que el proyecto ataca.

---

## 2. Qué son las dos imágenes que llegan

La máquina se llama **PET/CT** y produce dos volúmenes distintos del mismo cuerpo, en la misma
sesión y en la misma posición.

**El PET** (*Positron Emission Tomography*, tomografía por emisión de positrones) mide **actividad
metabólica**: qué tan rápido consume azúcar cada tejido. Se logra inyectando **FDG**
(fluorodesoxiglucosa), una molécula de glucosa a la que se le cambió un átomo por un isótopo
radiactivo. Las células que consumen mucho azúcar acumulan más FDG y "brillan". Los tumores
consumen mucho azúcar; por eso brillan.

El brillo se cuantifica con el **SUV** (*Standardized Uptake Value*, valor de captación
estandarizado): es la concentración de radiofármaco en un punto, dividida por la dosis inyectada y
corregida por el peso del paciente. Es un número sin unidades que hace comparables a pacientes
distintos. Como referencia: el músculo en reposo está cerca de SUV 1, el hígado alrededor de 2,
un tumor activo puede pasar de 10.

> **La trampa del PET**: hay tejidos sanos que también consumen mucho azúcar y brillan igual.
> El cerebro (SUV 8–12, es su combustible normal), el corazón, el hígado, el intestino, la
> médula ósea, y sobre todo el **riñón y la vejiga**, porque el FDG se elimina por la orina.
> Un PET solo, sin nada más, tiene decenas de puntos brillantes que no son tumor.

**El CT** (*Computed Tomography*, tomografía computarizada, en Chile "TAC" o "escáner") mide
**densidad**: cuánto absorbe rayos X cada tejido. Su escala son las **HU** (*Hounsfield Units*,
unidades Hounsfield), calibrada de manera que el agua vale 0 y el aire −1000. La grasa está cerca
de −100, el músculo alrededor de +50, el hueso pasa de +300.

> El CT no sabe nada de metabolismo. Ve la forma, no la actividad. Pero sabe **dónde está cada
> cosa**: distingue riñón de tumor, pulmón de mediastino, hueso de partes blandas.

Y ahí está la idea que sostiene todo el proyecto: **las dos imágenes son complementarias**. El PET
dice *"acá pasa algo"*; el CT dice *"acá es el riñón"*. Juntas, y solo juntas, permiten decidir si
un punto brillante es un tumor o es orina.

Eso se llama **fusión**: combinar las dos fuentes de información para tomar una decisión que
ninguna de las dos podría tomar sola.

---

## 3. El intento clásico y por qué no alcanza

La forma tradicional de automatizar esto es un **umbral**: pintar como lesión todo vóxel con SUV
por encima de un valor fijo, típicamente 2,5. Es simple, es antiguo, es lo que usa buena parte del
software comercial. Y usa **solo el PET**.

Lo medimos en nuestros datos, en 26 estudios de validación. El resultado:

| | Coincidencia con el experto | Volumen pintado de más |
|---|---|---|
| Umbral SUV 2,5 | **0,180** | **1.192 mL** |

Mil ciento noventa y dos mililitros de falso positivo. Más de un litro de tejido sano marcado como
tumor por estudio. Cuando repartimos ese error por órgano usando un mapa anatómico automático,
**el 74 % (879 de 1.192 mL) cae en órganos que captan FDG normalmente**: hígado, riñones, vejiga,
cerebro, corazón, intestino.

El método clásico no está roto. Está **ciego**: no tiene forma de saber que ese brillo es un riñón,
porque nunca mira el CT.

---

## 4. Qué propone el proyecto

La propuesta es reemplazar el umbral por una **red neuronal** que aprenda a mirar las dos imágenes
a la vez.

> **Red neuronal**: un programa con millones de números ajustables (los *parámetros*) que no se
> programan a mano, se **ajustan por ejemplo**. Se le muestran miles de casos con la respuesta
> correcta, y en cada intento se corrigen un poquito los números en la dirección que reduce el
> error. Después de suficientes intentos, acierta en casos que nunca vio.

La arquitectura que usamos se llama **U-Net**, y su forma explica lo que hace. Tiene dos mitades:

- **El embudo** (codificador): la imagen se va achicando y a la vez se va describiendo con más
  detalle abstracto. Al principio la red solo distingue bordes y manchas; al fondo del embudo la
  imagen es diminuta pero cada valor representa algo como "región de alta captación rodeada de
  tejido blando en el tórax". Se pierde *dónde*, se gana *qué*.
- **La trompeta** (decodificador): el proceso inverso, agrandando hasta volver al tamaño original,
  para poder decir exactamente qué vóxeles son lesión. Se recupera el *dónde*.
- **Los puentes** (*skip connections*): atajos que llevan el detalle fino desde el embudo
  directamente a la trompeta, para que el contorno no salga borroso.

La salida de la red es una **máscara**: un volumen del mismo tamaño que las imágenes donde cada
vóxel vale 1 (lesión) o 0 (no lesión). Es exactamente el dibujo que el especialista haría a mano.

### La pregunta científica

Decir "usemos las dos imágenes" no es una respuesta, es el comienzo de la pregunta. **¿En qué
momento del proceso conviene juntarlas?** Hay varias opciones razonables y no es obvio cuál es
mejor. El proyecto compara tres:

| | Nombre | Qué hace | Analogía |
|---|---|---|---|
| **A** | Fusión temprana | Las dos imágenes entran juntas como dos canales, desde el primer paso. Un solo embudo. | Dos personas que hablan al mismo tiempo desde el minuto cero. |
| **B** | Fusión intermedia | Dos embudos independientes, uno para PET y otro para CT. Se juntan recién al fondo, pegando sus descripciones lado a lado. | Dos peritos que analizan por separado y recién al final comparan informes. |
| **C** | Fusión con atención cruzada | Igual que B, pero al fondo se agrega un mecanismo donde cada zona del PET "pregunta" al CT qué hay en ese lugar y en lugares relacionados. | Los dos peritos, además de comparar, se hacen preguntas dirigidas. |

> **Atención cruzada** (*cross-attention*): el mecanismo que está detrás de los modelos de
> lenguaje modernos. Para cada posición de una fuente, calcula cuánto le importa cada posición de
> la otra fuente, y arma un resumen ponderado. Es "mirar selectivamente" en vez de "mirar todo por
> igual".

La hipótesis inicial era la intuitiva: **C > B > A**. Más mecanismo, mejor resultado.

---

## 5. Con qué se hace: los insumos

Esta es la parte que se suele omitir y es la que hace el trabajo reproducible.

### 5.1 Los datos

**autoPET** (colección `FDG-PET-CT-Lesions` del TCIA, *The Cancer Imaging Archive*), en su versión
pública *defaced*, con licencia CC BY 4.0. Es el conjunto de datos de referencia mundial para este
problema: es el que usa un desafío internacional anual, lo que hace que nuestros resultados sean
comparables con los de la literatura.

> **Defaced**: "sin cara". Por privacidad, la región facial fue borrada digitalmente de las
> imágenes, porque de un CT de cabeza se puede reconstruir el rostro del paciente. Esto obliga a
> excluir esa zona al medir, y lo hacemos de forma idéntica para todos los métodos.

De la colección tomamos **251 estudios, uno por paciente**:

| | Total | Cáncer de pulmón | Linfoma | Melanoma | Sin lesión |
|---|---|---|---|---|---|
| Entrenamiento | 176 | 47 | 47 | 47 | 35 |
| Validación | 26 | 7 | 7 | 7 | 5 |
| Prueba | 49 | 13 | 13 | 13 | 10 |

Los 50 estudios **sin lesión** son deliberados: sirven para medir cuántas cosas inventa el sistema
cuando no hay nada que encontrar.

Lo más valioso del conjunto es que cada estudio trae la **anotación de referencia**: la máscara
dibujada a mano por un especialista. Sin eso no habría con qué enseñar ni con qué medir.

> **La limitación central del conjunto, declarada desde el principio**: la anotación marca
> **únicamente lesión tumoral ávida de FDG**. Todo lo demás —una captación inflamatoria, un
> ganglio reactivo, una infección— está sin marcar, indistinguible del fondo. Por eso el proyecto
> adoptó una regla de cierre: *no hacer ninguna pregunta que la anotación no pueda contestar sola*.

### 5.2 La preparación de las imágenes

Los estudios vienen en tamaños y resoluciones distintos, y hay que dejarlos comparables:

1. **Remuestreo a 3 mm isotrópico**: todos los vóxeles pasan a medir 3 × 3 × 3 mm.
2. **Ventana de CT −200 a +300 HU**, reescalada a [0, 1]: se descartan aire y hueso denso, que no
   aportan, y se aprovecha todo el rango numérico en las partes blandas, que es donde se decide.
3. **SUV dividido por 30**, con tope: lleva el PET al mismo rango [0, 1] que el CT, para que
   ninguna de las dos domine por escala.
4. **Máscara corporal y recorte**: se elimina el aire alrededor del paciente. Reduce el volumen a
   procesar y evita que la red gaste capacidad en la nada.

Todas estas constantes son **fijas**, no se calculan sobre los datos. Eso importa porque garantiza
que ninguna información de validación o prueba se filtra hacia el entrenamiento.

### 5.3 El mapa de órganos

**TotalSegmentator**: una red ya entrenada, de uso público, que a partir del CT identifica 117
estructuras anatómicas. Las agrupamos en 17 grupos de órganos.

No entra a nuestras redes ni participa del entrenamiento. Se usa **solo para el análisis de
errores**: permite decir "de los 20,9 mL que el modelo A pinta de más, 0,2 están en hígado y 6,6
en tejido no clasificado", en vez de un número global que no explica nada.

### 5.4 Lo material

Todo corre en un **MacBook con chip Apple Silicon**, usando el acelerador gráfico integrado
(`mps`). Sin nube, sin clúster, sin GPU dedicada. Software: Python, PyTorch, MONAI (biblioteca de
imagen médica), SimpleITK, NumPy. Cada entrenamiento toma unas **9 horas**; el proyecto completo
son **nueve entrenamientos** (tres modelos × tres semillas), más las evaluaciones.

> **Semilla**: el número que inicializa el generador de azar. Una red se inicializa al azar y ve
> los ejemplos en orden azaroso, así que dos entrenamientos idénticos dan resultados levemente
> distintos. Repetir con tres semillas y reportar promedio ± desviación es lo que permite
> distinguir una diferencia real de una casualidad. Es el equivalente a no sacar conclusiones de
> una sola medición.

---

## 6. Cómo se mide si funciona

Tres números, y cada uno responde una pregunta distinta:

- **Dice** (coeficiente de Dice, o índice de Sørensen–Dice): cuánto se superponen el dibujo de la
  red y el del experto. Va de 0 (nada) a 1 (idénticos). Fórmula: dos veces la intersección,
  dividida por la suma de ambos volúmenes. Responde *"¿dibuja bien lo que hay?"*.
- **FPV** (*False Positive Volume*, volumen de falso positivo, en mL): cuánto tejido sano marcó
  como lesión. Responde *"¿cuánto inventa?"*.
- **FNV** (*False Negative Volume*, volumen de falso negativo, en mL): cuánto tumor real dejó
  pasar. Responde *"¿cuánto se le escapa?"*.

Se separan a propósito, porque un solo número los esconde: un sistema que no marca nada tiene cero
falsos positivos y es inútil.

Además, **regla de oro del proyecto**: el conjunto de **prueba (49 estudios) se abre una sola
vez, al final**. Mientras se toman decisiones se mira solo validación. Si uno mira la prueba y
después ajusta algo, la prueba deja de ser una prueba y pasa a ser parte del entrenamiento
disfrazado. A la fecha de este documento, **sigue cerrada**.

Y para cualquier módulo nuevo que se agregue, **ablación obligatoria**: apagarlo y volver a medir.
Si al apagarlo no cambia nada, el módulo no estaba haciendo nada, por muy elegante que sea en el
diagrama.

---

## 7. Qué pasó

**Las tres fusiones empatan.**

| | Dice (val, 26 estudios) | FPV (mL) | FNV (mL) |
|---|---|---|---|
| Umbral clásico SUV 2,5 | 0,180 | 1.192 | 5,6 |
| **A** — fusión temprana | **0,621 ± 0,016** | 20,9 | 6,0 |
| **B** — dos codificadores | **0,612 ± 0,014** | 22,8 | 5,4 |
| **C** — atención cruzada | **0,612 ± 0,008** | 23,2 | 5,9 |

La diferencia entre A, B y C es menor que la variación entre semillas del mismo modelo. Dicho
claro: **cambiar la semilla cambia más el resultado que cambiar la arquitectura.** La hipótesis
C > B > A no se sostuvo.

Más aún: la ablación mostró que en C la atención cruzada era **literalmente inerte**. Al apagarla,
la predicción no cambió **ni un vóxel** en ninguno de los 26 estudios, en las tres semillas. La
causa se pudo medir: la atención producía una salida casi constante en el espacio, y la
normalización interna de la red cancela exactamente las constantes. El módulo estaba conectado
pero su aporte se borraba una capa después.

Esto coincide con la conclusión oficial del desafío internacional autoPET III, que en su resumen
de resultados afirma que *"la heterogeneidad y dificultad de los casos impulsa la variación de
rendimiento sustancialmente más que la elección de algoritmo entre los equipos mejor
clasificados"*. Nuestro resultado negativo no es una anomalía local: es el consenso del campo,
reproducido de forma independiente en un laptop.

---

## 8. Entonces, ¿qué problema resuelve el proyecto?

Conviene separar lo que resuelve de lo que no.

**Lo que sí resuelve, con números:**

1. **La ceguera anatómica del método clásico.** Pasar de 1.192 mL de falso positivo a 20,9 mL es
   una reducción de 57 veces. Donde el umbral pone 349 mL en hígado, las redes ponen 0,2. Donde
   pone 132 mL en vejiga, ponen 0,6. La fusión PET/CT **funciona**; lo que da lo mismo es *cómo*
   se implemente.
2. **El costo de tiempo del dibujo manual.** Corregir la salida de la red requiere tocar 64,6 mL
   por estudio (borrar lo sobrante más agregar lo faltante) contra 151,7 mL de dibujar desde
   cero: **57 % menos trabajo**.
3. **Una frontera de competencia explícita.** El sistema detecta el 100 % de las lesiones sobre
   10 mL (≈ 27 mm de diámetro), el 81–86 % entre 3 y 10 mL, y solo el 21 % bajo 1 mL (≈ 12 mm).
   Saber *dónde* un sistema deja de ser confiable es más útil que un promedio que lo esconde.

**Lo que no resuelve, y hay que decirlo:**

- No distingue tumor de captación benigna en órganos que captan normalmente (riñón, vejiga,
  intestino), porque **el conjunto de datos no contiene esa información**. No es un límite del
  método, es un límite del material.
- No detecta lesiones pequeñas, y la resolución de trabajo (3 mm por vóxel) es parte de la causa.
- No reemplaza al especialista. Produce un borrador que hay que revisar.

**Y lo que aporta como conocimiento, que es lo que en el fondo se pide en un proyecto de curso:**

Un resultado negativo bien medido. Se probó una hipótesis razonable, se la refutó con evidencia
suficiente (tres semillas, ablación con diferencia exactamente cero, análisis del mecanismo), y se
explicó *por qué* falló, no solo *que* falló. Esa explicación —la fusión aditiva es cancelable por
la normalización de instancia, la multiplicativa no lo sería— es una hipótesis concreta y
verificable para quien siga la línea.

---

## 9. Dónde está cada cosa

| Documento | Qué contiene |
|---|---|
| `BITACORA.md` | Diario cronológico: cada decisión, con fecha y razón |
| `docs/PROTOCOLO_CONGELADO.md` | Datos, configuración exacta y auditoría de fugas de información |
| `docs/GLOSARIO.md` | Todos los términos con analogías |
| `docs/TRASPASO_RAMAS.md` | Líneas de trabajo futuro con su justificación |
| `notas_personales/CUADERNO_DE_DEFENSA.md` | Preguntas probables y sus respuestas (fuera del repositorio) |
| `results/` | Todas las tablas de resultados en CSV |
| `docs/figuras/` | Figuras y visores interactivos |
