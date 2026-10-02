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

## Resultados

*(pendiente)*
