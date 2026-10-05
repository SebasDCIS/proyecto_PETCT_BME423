# Paso 3: enseñarle anatomía al residente

*Rama `extendido`, 2026-09-24. Escrito ANTES de correr nada: acá quedan fijadas la hipótesis,
los criterios de éxito y el presupuesto. Los resultados se agregan al final cuando existan.*

## De dónde sale

Después de tres semillas en régimen largo (docs/PASO2_ARQUITECTURAS.md), el objetivo original
del proyecto —que la captación fisiológica (hígado, vejiga, corazón, riñones...) no confunda a la
red— está en gran parte cumplido por la vía menos glamorosa: más entrenamiento. Sobre los 26
estudios de validación, el modelo B (media de tres semillas) inventa **14,2 mL** de falso
positivo por estudio, repartidos así:

| dónde cae el falso positivo | mL / estudio | fracción |
|---|---|---|
| "otro" (tejido sin etiqueta: grasa, piel, ganglios, tejido blando) | 5,74 | 40 % |
| pulmón | 3,20 | 23 % |
| "fuera" (bordes del cuerpo, zona borrada) | 2,23 | 16 % |
| **órganos con captación fisiológica** (12 grupos, ver abajo) | **2,55** | **18 %** |
| hueso + otros órganos | 0,46 | 3 % |

Los 12 grupos "fisiológicos" (`petct.organs.ORGANOS_FISIOLOGICOS`): hígado, bazo, riñones,
vejiga, corazón, estómago, intestino, páncreas/suprarrenales, músculo, vasos,
tiroides/esófago/tráquea, encéfalo. Dentro de ellos hay también **25 mL de lesión anotada
por estudio** (hígado 5,8; músculo 6,4; vasos 6,0; corazón 4,0: metástasis hepáticas y
ganglios mediastínicos que el mapa asigna a vasos y corazón), de los que hoy B pierde 0,65 mL.

Lo que esto dice: **el residente ya casi no confunde la vejiga con un tumor**. Lo que le
queda es el error difuso: marcas en grasa, en pulmón, en los bordes. Y eso es un problema
de *contexto anatómico*, no de un órgano en particular.

## La idea, con la analogía de siempre

Hasta ahora el residente aprendió anatomía y oncología al mismo tiempo, mirando solo
estudios donde alguien marcó tumores. Nunca tuvo un curso de anatomía por separado. Dos
intervenciones, independientes y combinables:

**1. Curso de anatomía previo (preentrenamiento del codificador de CT).** Se toma el
codificador de CT del modelo B —la mitad de la red que mira solo el CT— y antes de enseñarle
tumores se lo entrena a responder "¿qué órgano hay en cada vóxel?" sobre los 825 CT de
entrenamiento, con TotalSegmentator como profesor (17 grupos). No ve el PET ni la máscara de
lesión. Después B arranca con ese codificador ya sabiendo dónde está cada cosa y aprende todo
lo demás desde cero como siempre. Es lo que en la literatura se llama preentrenamiento
supervisado del *backbone*; acá tiene sentido especial porque el modelo B ya separa el CT en
un codificador propio, así que el trasplante es limpio: mismo `Encoder`, mismos canales.

**2. Errores que cuestan más (pérdida pesada por órgano).** Durante el entrenamiento de
lesiones, un vóxel de fondo dentro de un órgano fisiológico que la red marca como tumor
cuesta 3 veces más que cualquier otro error. El mapa de órganos se usa solo para corregir,
no como entrada: en inferencia la red no lo tiene. Es el tutor diciendo "marcar el hígado
sano como tumor es más grave que marcar un pliegue de grasa".

**Techo declarado de la intervención 2:** solo actúa sobre los 2,55 mL de los órganos
fisiológicos. Aunque los borrara todos, el FPV bajaría un 18 %. Y tiene un riesgo concreto:
los 25 mL de lesión real que viven en esos órganos. Se corre igual porque es barata (un día),
porque el objetivo declarado del proyecto es exactamente ese, y porque combinada con la 1
puede sumar. Pero la apuesta grande es la intervención 1, la única que puede tocar "otro" y
pulmón.

## Diseño

Tres corridas nuevas del modelo B, todo lo demás idéntico a `B_ext_largo` (825 estudios,
100 000 iteraciones, semilla 423, lote 2, parche 96³, AdamW 3e-4 poli 0,9):

| corrida | curso de anatomía | errores pesados ×3 |
|---|---|---|
| B_ext_largo (ya existe, 3 semillas) | – | – |
| B_ext_largo_peso | – | sí |
| B_ext_largo_pre | sí | – |
| B_ext_largo_pre_peso | sí | sí |

Es un 2×2 con B como control, una semilla por celda en esta primera pasada. Previo:
TotalSegmentator sobre los 649 estudios de entrenamiento que no tenían mapa (~10 h, sin
GPU) y el preentrenamiento del codificador (20 000 iteraciones, ~4 h).

## Criterios de éxito, fijados antes de correr

Referencia: B_ext_largo, media de tres semillas: Dice⁺ 0,705 ± 0,011; FPV 13,25 mL (14,2 por
órgano sobre los 26); FP en órganos fisiológicos 2,55 mL; FN en órganos fisiológicos 0,65 mL.

- **Intervención 1 (preentrenado) funciona si:** FPV baja **≥ 3 mL** (más del doble de la
  dispersión entre semillas, ~1 mL) **y** el Dice⁺ no cae por debajo de **0,694** (media − 1 sd).
  Si además sube el Dice⁺ por encima de 0,716, mejor; no se exige.
- **Intervención 2 (pesada) funciona si:** FP en los 12 órganos fisiológicos baja **a la
  mitad o más** (≤ 1,3 mL) **y** FN en esos mismos órganos **no se duplica** (≤ 1,3 mL) **y**
  Dice⁺ ≥ 0,694.
- **Fracaso honesto:** si ninguna celda cumple, se documenta y se cierra. No se ajusta el peso
  ni se cambian criterios a posteriori.
- **Qué pasa si funciona:** la celda ganadora se repite con semillas 2 y 3 antes de afirmar
  nada (la lección del paso 2: la primera semilla de B sobreestimó su efecto 3×). Recién con
  tres semillas se decide si entra a la comparación con C y si vale llevarlo a 2 mm.

Métricas como siempre: Dice⁺ solo en positivos (`mtv_gt_ml > 0`, n = 20), FPV/FNV por
componentes 26-conexas, métrica corregida (sin zona borrada) y cruda del reto. Validación:
los 26 de siempre. **El test sigue cerrado.**

## Cómo se corre

Todo en cola detrás del script 27 (que termina con A+ semilla 3), en una segunda terminal:

    caffeinate -i bash scripts/30_anatomia_cola.sh --esperar 2>&1 | tee -a runs/anatomia_cola.log

Etapas (cada una se salta si su resultado ya existe): mapas de órganos → B_peso →
preentrenamiento → B_pre → B_pre_peso → análisis por órgano de todo. Costo: ~10 h + ~4 h +
3 × ~24 h ≈ 4 días.

Piezas de código (commit de esta fecha): `petct.losses.OrganWeightedDiceCE`;
`PatchDataset(organs_dir=...)` que devuelve también el parche de órganos;
`scripts/29_preentrenar_ct_anatomia.py`; `scripts/07_entrenar.py --enc-ct-preentrenado
--peso-organos`; `scripts/30_anatomia_cola.sh`. Con peso 1 la pérdida nueva es numéricamente
la de siempre (verificado); las corridas anteriores no se ven afectadas.

## Resultados

### Etapas 0 y 2: el material y el curso (2026-09-28)

TotalSegmentator sobre los 649 estudios sin mapa: 3 h 50 en la GPU, 0 errores; los 851
estudios de train + val tienen mapa. Preentrenamiento del codificador (`runs/ct_anatomia`):
20 000 iteraciones, 3,5 h, **Dice anatómico medio 0,861** sobre 40 parches fijos de validación
(17 grupos, sin "fuera"). El curso de anatomía funcionó: el codificador sabe leer órganos.

### Etapa 1: B con errores caros (una semilla, 2026-09-28)

| | B (3 semillas) | B_peso |
|---|---|---|
| Dice⁺ | 0,705 (0,694–0,714) | 0,711 |
| FPV mL | 13,25 (12,1–14,5) | 12,47 |
| FPV mediana | 4,29 | 3,75 |
| FNV mL | 3,78 | 3,42 |
| FP en órganos fisiológicos | 2,55 | **3,57** |
| FN en órganos fisiológicos | 0,65 | 0,62 |
| FP en otro + pulmón + bordes | 11,18 | 9,03 |

Pareado: Dice +0,005 (gana 10/20, p 0,99); FPV −0,8 mL (baja en 15/26, p 0,24).

**Veredicto según el criterio fijado: no cumple.** El FP en los órganos fisiológicos no bajó a
la mitad; subió, por dos estudios ya conocidos como difíciles: `94962fe878` (músculo: 41 mL
contra 4–20 en las semillas de B) y `73fda3a382` (riñón: 15 contra 5–9). En los otros 24
estudios los órganos fisiológicos quedaron igual o algo mejor. Lo que sí bajó (19 %) fue el
FP fuera de esos órganos, donde la pérdida no actúa: −2,1 mL en tejido sin etiqueta, pulmón y
bordes. Con una semilla, y con B moviéndose 12,1–14,5 entre semillas, esa baja no se puede
distinguir del ruido. No perjudicó (Dice y FN iguales o mejores), no hizo lo que se le pidió,
y no se repite con más semillas: se cierra como negativo.

### Etapa 3: B con el codificador preentrenado (una semilla, 2026-09-29)

| | B (3 semillas) | B_pre |
|---|---|---|
| Dice⁺ | 0,705 (0,694–0,714) | **0,724** |
| Dice⁺ mediana | 0,780 | 0,774 |
| FPV mL | 13,25 (12,1–14,5) | 12,55 |
| FPV mediana | 4,29 | **2,78** |
| FNV mL | 3,78 | 3,42 |
| FP en órganos fisiológicos | 2,55 | 2,21 |
| FP en otro + pulmón + bordes | 11,18 | 10,74 |

Pareado: Dice +0,018 (gana 12/20, p 0,41); FPV −0,7 mL (baja en 14/26, p 0,33). Por órgano
baja hígado (0,35 → 0,13) e intestino (0,52 → 0,29); "otro", pulmón y bordes casi no se mueven.

**Veredicto según el criterio fijado: no cumple.** El criterio pedía FPV −3 mL; bajó 0,7, dentro
del rango entre semillas de B. Lo que sí apareció, y no era el criterio, es el Dice⁺ más alto
de las dieciséis corridas largas (0,724; el mejor anterior era C con 0,715), con la mediana de
FPV más baja (2,78 mL). Una semilla. Este proyecto ya vio dos veces (B semilla 1, A+ semilla 2)
que una corrida sola engaña, así que el 0,724 no se interpreta: se anota. Si se quiere saber
si es real, corresponde una hipótesis nueva declarada antes de correr (Dice⁺ ≥ 0,716, la media
de B más una desviación, en dos semillas más), no ampliar el criterio de esta a posteriori.

### Etapa 4: B con las dos cosas (una semilla, 2026-10-01) y cierre del 2×2

| | B (3 semillas) | B_peso | B_pre | B_pre_peso |
|---|---|---|---|---|
| Dice⁺ | 0,705 (0,694–0,714) | 0,711 | **0,724** | 0,708 |
| Dice⁺ mediana | 0,780 | 0,804 | 0,774 | 0,750 |
| FPV mL | 13,25 (12,1–14,5) | 12,47 | 12,55 | **11,92** |
| FPV mediana | 4,29 | 3,75 | 2,78 | **2,51** |
| FNV mL | 3,78 | 3,42 | 3,42 | 3,95 |
| FP en órganos fisiológicos | 2,55 | 3,57 | 2,21 | 3,05 |
| FP en otro + pulmón + bordes | 11,18 | 9,03 | 10,74 | 9,25 |

Pareado pre_peso − B: Dice +0,003 (gana 11/20, p 0,87); FPV −1,3 mL (baja en 16/26, p 0,05).

**Veredicto del 2×2 según los criterios fijados: ninguna celda cumple.** La combinación es la
que más baja el FPV (−1,3 mL, con el pareado al borde de la significancia y la mediana más
baja de todas, 2,5 mL), pero sigue lejos de los −3 mL exigidos, y en Dice es B. Los efectos de
las dos intervenciones no se suman: la pérdida pesada arrastra otra vez el músculo (1,66 mL,
el mismo estudio `94962fe878`) y borra la ganancia de Dice del preentrenado. Patrón del
cuadro completo: el preentrenamiento mueve el Dice; la pérdida pesada mueve un poco el FPV
difuso y empeora los órganos fisiológicos; ninguna toca pulmón de forma apreciable
(3,2 → 2,6–2,9). El 80 % del error sigue donde estaba.

### Hipótesis nueva, declarada antes de correr (2026-10-01)

El Dice⁺ 0,724 de B_pre es una observación de una semilla y no era el criterio de la etapa 3.
Para saber si es real se declara una hipótesis nueva, con su criterio, antes de lanzar nada:

**H:** arrancar B con el codificador de CT preentrenado en anatomía sube el Dice⁺ de forma
repetible. **Se acepta si** las semillas 2 y 3 de B_pre (`runs/B_ext_largo_pre_s2`, `_s3`;
mismo `enc_ct.pt`, misma receta que B_ext_largo_s2/_s3) dan **ambas** Dice⁺ ≥ 0,716 (la media
de B más una desviación: 0,705 + 0,011) **y** FPV ≤ 14,5 mL (la peor semilla de B). Con eso la
media de tres semillas de B_pre quedaría ≥ 0,719, por encima de todas las semillas de B y de C.
**Se rechaza si** cualquiera de las dos queda por debajo de 0,716: entonces el 0,724 fue una
semilla afortunada y la anatomía se cierra como negativo completo. No hay zona gris ni
tercera semilla extra.

Lo que se varía es solo la semilla de B (inicialización y orden de parches); el codificador
preentrenado es el mismo archivo en las tres, porque la hipótesis es sobre *arrancar con él*,
no sobre el preentrenamiento en sí. Costo: dos corridas, ~48 h de Mac (`scripts/31`).

### Veredicto de la hipótesis (2026-10-04): rechazada

B_pre semilla 2: **Dice⁺ 0,700** (criterio ≥ 0,716: no cumple), FPV 12,99 mL (≤ 14,5: cumple).
Como la regla exigía que AMBAS semillas cumplieran, la hipótesis queda rechazada con la
semilla 2, sin importar lo que dé la 3. El 0,724 de la semilla 423 fue una semilla
afortunada: la tercera vez en este proyecto que una corrida sola sobreestima un efecto.

Comparado contra B con la MISMA semilla (lo único que cambia es el preentrenamiento):
semilla 423 +0,010 (gana 8/20, p 0,99); semilla 2 −0,010 (gana 10/20, p 0,70). El efecto del
preentrenamiento sobre el Dice es cero dentro del ruido. Un solo estudio (`2d70838805`, una
lesión de 3 mL: 0,66 en una semilla, 0,21 en la otra) mueve el promedio de Dice⁺ en 0,023: el
Dice⁺ medio sobre 20 estudios está dominado por lesiones chicas.

**Métrica por lesión** (nueva en esta rama; lesiones = componentes 26-conexas de la anotación,
fuera de la zona borrada, 256 en los 26 estudios; detectada = la toca alguna predicción):

| corrida | detectadas | < 1 mL | 1–3 mL | 3–10 mL | > 10 mL | marcas falsas / estudio |
|---|---|---|---|---|---|---|
| B s423 | 163/256 (0,64) | 0,31 | 0,73 | 0,91 | 1,00 | 4,8 |
| B s2 | 160/256 (0,63) | 0,28 | 0,71 | 0,95 | 1,00 | 4,9 |
| B s3 | 158/256 (0,62) | 0,27 | 0,72 | 0,91 | 1,00 | 5,8 |
| B_pre s423 | 167/256 (0,65) | 0,32 | 0,76 | 0,93 | 1,00 | 5,2 |
| B_pre s2 | 161/256 (0,63) | 0,28 | 0,73 | 0,93 | 1,00 | 5,4 |

Por lesión tampoco hay diferencia: los cinco detectan entre 158 y 167 de 256 lesiones, todas las
mayores de 10 mL y menos de un tercio de las menores de 1 mL. La anatomía se cierra como
negativo completo. El brazo que entra al ensamble es **B** (`BRAZO=B`).

### Cierre con tres semillas (2026-10-05)

La semilla 3 terminó: Dice⁺ 0,698, FPV 12,59 mL; por lesión 163/256 (0,64), 4,9 marcas falsas
por estudio. Tampoco cumple. Tabla final:

| | Dice⁺ (media ± sd) | por semilla | FPV mL | FPV mediana | FNV mL |
|---|---|---|---|---|---|
| B | 0,705 ± 0,011 | 0,714 · 0,709 · 0,694 | 13,25 | 4,29 | 3,78 |
| B_pre | 0,707 ± 0,014 | 0,724 · 0,700 · 0,698 | 12,71 | 4,23 | 3,62 |

Pareado sobre el promedio de tres semillas: Dice +0,002, IC95 [−0,029, +0,035], gana 10/20,
p 0,78; FPV −0,54 mL, baja en 14/26, p 0,38. Por semilla emparejada: +0,010, −0,010, +0,005.
**Arrancar con el codificador de CT preentrenado en anatomía no cambia nada medible.** Lo que
queda como dato menor: las tres semillas de B_pre tienen un FPV más parejo (12,6–13,0 contra
12,1–14,5 de B), sin efecto en el promedio.

