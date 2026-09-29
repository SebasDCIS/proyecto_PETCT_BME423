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
