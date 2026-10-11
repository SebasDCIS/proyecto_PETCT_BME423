# Paso 4: cinco residentes que votan

*Rama `extendido`, 2026-10-02. Escrito antes de correr: hipótesis, criterio y presupuesto
quedan fijados acá. Los resultados se agregan al final.*

## Qué cambia respecto de los pasos anteriores

Los pasos 1 a 3 fueron preguntas controladas (¿datos o tiempo?, ¿qué fusión?, ¿sirve la
anatomía?). Este no es una pregunta: es construir, con lo aprendido, el mejor sistema que se
puede entregar, el que irá al test cerrado y el que podría competir en autoPET. Y ataca el
error que ninguna idea propia tocó: el falso positivo difuso en tejido sin etiqueta, pulmón y
bordes (el 80 % de los 13 mL por estudio que quedan).

## La idea

Hoy tenemos un residente leyendo solo. Cuando ve un foco inflamatorio en el pulmón lo marca o
no según cómo le tocó aprender: las tres semillas de B marcan 12, 14 y 13 mL en promedio, y en
el paciente `94962fe878` una marca 4 mL de músculo y otra 20. Esa variabilidad entre residentes
es la medida de lo inseguros que están. El ensamble pone a cinco a leer el mismo estudio y marca
lesión donde el promedio de sus probabilidades supera 0,5. Las lesiones verdaderas las ven los
cinco y sobreviven; las marcas dudosas son idiosincrasias de cada uno, no coinciden, y se
diluyen. Es el mecanismo más usado contra el falso positivo en segmentación y lo que hacen
todos los finalistas de autoPET.

Con aumento en inferencia (TTA) cada residente además lee la imagen y sus tres espejos
laterales (los mismos volteos que vio en entrenamiento; z no se voltea): 20 lecturas por
estudio.

## Diseño

Los 825 estudios de entrenamiento se reparten en cinco pliegues de ~165, estratificados por
diagnóstico, semilla 423, un paciente por estudio (`scripts/32_pliegues.py`). Validación (26)
y prueba (49) no se tocan. Cinco corridas del modelo B, cada una entrenada con cuatro pliegues
y la receta de siempre (100 000 iteraciones, lote 2, parche 96³, AdamW 3e-4). Qué B entra lo
decide el veredicto de `scripts/31` (la hipótesis del codificador preentrenado): si las dos
semillas cumplen, `BRAZO=pre`; si no, `BRAZO=B`. No se corre el ensamble con los dos.

Cada corrida se evalúa en tres lugares: su pliegue no visto (oof, ~165 estudios; la primera
estimación del proyecto sobre más de 26 estudios), los 26 de validación sola, y los 26 de
validación como ensamble de las cinco, con y sin TTA (`scripts/33_ensamble.py`). Con un solo
checkpoint y sin TTA el script 33 reproduce exactamente al 09 (verificado).

Nota declarada: si entra `BRAZO=pre`, el codificador de CT preentrenado vio los CT (no las
máscaras de lesión) de todos los pliegues; la evaluación oof es limpia respecto de la etiqueta
de lesión, no respecto de la anatomía. Para la métrica final (val, test) no hay diferencia.

## Criterio de éxito, fijado antes de correr

Referencia: B_ext_largo, media de tres semillas: Dice⁺ 0,705, FPV 13,25 mL, mediana 4,29.

- **El ensamble funciona si** FPV < 9 mL (−1/3 respecto de B, más de cuatro veces la dispersión
  entre semillas) **y** Dice⁺ ≥ 0,705 (no pierde solapamiento), sobre los 26 de validación,
  métrica corregida. Se mira primero sin TTA; el TTA se reporta aparte y no rescata un
  ensamble que no cumpla solo.
- **Lo que se reporta además, sin criterio:** Dice⁺ y FPV oof por pliegue (la dispersión entre
  pliegues es la primera medida honesta de generalización dentro del entrenamiento), la
  métrica cruda del reto, y la curva FPV–umbral sobre las probabilidades guardadas (para el
  FROC del `experimentos/21`).
- **Si cumple:** el ensamble es "el modelo" de la rama. Se le agrega el postproceso de la regla
  del doble del hígado propio (`experimentos/23`) como capa opcional, comparado a igual número
  de marcas falsas, y con todo decidido se abre el test una vez.
- **Si no cumple:** se reporta igual; el test se abre con el mejor brazo individual.

## Costo y cómo se corre

Cinco corridas de ~24 h más ~1 h de evaluaciones: cinco días y medio de Mac. Detrás del 31:

    BRAZO=pre caffeinate -i bash scripts/34_ensamble_cola.sh 2>&1 | tee -a runs/ensamble_cola.log
    # o BRAZO=B, según el veredicto del 31

Reanudable como los anteriores. Las máscaras y las probabilidades promedio del ensamble
quedan en `runs/ensambles/<etiqueta>/`.

## Resultados (2026-10-10)

Cinco corridas de B (una por pliegue, ~660 estudios cada una, 100 000 iteraciones), 25,6 h
cada una; ensamble evaluado sobre los 26 de validación, métrica corregida.

| | Dice⁺ | mediana | FPV mL | FPV mediana | FNV mL | FPV en controles |
|---|---|---|---|---|---|---|
| B (825 estudios, 3 semillas) | 0,706 | 0,780 | 13,25 | 4,29 | 3,78 | 31,6 |
| Miembros del ensamble, solos (media de 5) | 0,718 | 0,791 | 11,85 | 3,33 | 4,09 | 26,8 |
| **Ensamble** | **0,744** | 0,821 | **9,96** | 1,30 | 3,93 | 24,6 |
| **Ensamble + TTA** | **0,754** | 0,821 | **9,21** | 1,17 | 3,83 | 23,3 |

Métrica cruda del reto: ensamble 0,676 / FPV 10,52; ensamble + TTA 0,687 / FPV 9,61.

**Veredicto según el criterio fijado (FPV < 9 mL y Dice⁺ ≥ 0,705): no cumple.** El FPV quedó en
9,96 sin TTA y 9,21 con TTA, a menos de 1 mL del umbral. Se reporta como no cumplido, sin
mover el umbral.

**Lo que sí muestra, y con un tamaño que ningún paso anterior tuvo.** Pareado por estudio:

| comparación | ΔDice⁺ | IC95 | gana | p | ΔFPV mL | IC95 | baja en | p |
|---|---|---|---|---|---|---|---|---|
| ensamble − B (3 semillas) | +0,039 | [+0,015, +0,071] | 14/20 | 0,005 | −3,29 | [−5,53, −1,66] | 22/26 | < 0,001 |
| ensamble − sus 5 miembros | +0,026 | [+0,010, +0,047] | 18/20 | 0,001 | −1,89 | [−2,86, −1,06] | 24/26 | < 0,001 |
| ensamble+TTA − B (3 semillas) | +0,048 | [+0,024, +0,079] | 16/20 | < 0,001 | −4,03 | [−6,56, −2,24] | 24/26 | < 0,001 |
| ensamble+TTA − sus 5 miembros | +0,036 | [+0,019, +0,054] | 19/20 | < 0,001 | −2,64 | [−4,19, −1,47] | 24/26 | < 0,001 |

Es la primera mejora de la rama con intervalos fuera del cero en Dice y en FPV a la vez, y la
comparación contra sus propios miembros (mismos datos, misma receta) la atribuye al voto y no a
los datos de cada pliegue.

**Por lesión** (256 lesiones fuera de la zona borrada): el ensamble detecta las mismas que B
(159–160 contra 158–163; < 1 mL 28 %, 1–3 mL 71–72 %, 3–10 mL 93 %, > 10 mL 100 %), pero
deja **2,8–2,9 marcas falsas por estudio contra 4,8–5,8** (−40 a −50 %). Es exactamente el
mecanismo esperado: no encuentra más tumores, inventa menos.

**Por órgano** (mL por estudio, incluida la zona borrada): tejido sin etiqueta + pulmón +
bordes B 11,2 → ensamble+TTA 7,9 (−29 %); órganos fisiológicos 2,55 → 1,41; intestino
0,52 → 0,06; pulmón 3,20 → 2,45. Es la primera intervención que mueve el error difuso.
El caso que domina sigue siendo el control `f6295a93a6` (foco inflamatorio pulmonar): 114 mL.

**Fuera de pliegue (825 estudios, cada uno evaluado por el único modelo que no lo vio).** Dice⁺
0,689 (mediana 0,766) en 405 positivos; FPV 14,7 mL (mediana 2,3); por diagnóstico pulmón
0,76, linfoma 0,67, melanoma 0,60; pliegues 0,669–0,711. Coincide con la validación de 26: los
números del proyecto no estaban inflados por el tamaño de la validación. En los 420 estudios
sin lesión evaluable, 14 controles con más de 100 mL de FPV aportan el 37 % de todo el FPV
(el peor, `adc49adb3d`, 37 años, 2,4 L, con 3,3 L de tejido sobre SUV 2,5: probable grasa parda
o captación muscular difusa, sin confirmar).

**Curva de umbral** (probabilidades del ensamble+TTA guardadas; informativa, no criterio):

| umbral | Dice⁺ | FPV mL | FNV mL |
|---|---|---|---|
| 0,5 (el declarado) | 0,754 | 9,21 | 3,83 |
| 0,6 | 0,774 | 7,68 | 4,06 |
| 0,7 | 0,784 | 6,51 | 4,75 |
| 0,8 | 0,783 | 5,06 | 5,93 |

Subir el umbral baja el FPV y, hasta 0,7, sube el Dice. Pero esa curva se miró sobre los mismos
26 estudios; elegir el umbral ahí y declarar cumplido el criterio sería ajustar después de ver.
Queda como dato para decidir el umbral del test **antes de abrirlo**, no para reinterpretar este
veredicto.
