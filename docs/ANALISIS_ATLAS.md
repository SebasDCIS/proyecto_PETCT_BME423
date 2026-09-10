# Atlas de captación normal y poder de separación

*2026-09-11. Pasos 2 a 4 de `docs/RUTA.md`. Ningún entrenamiento: todo se calcula sobre los
mapas de órganos y las predicciones que ya existían.*

Este documento tiene tres partes: qué dice el atlas, si hace falta aumentarlo, y si la
captación referida al órgano separa mejor las marcas buenas de las malas que el SUV absoluto.

---

## 1. El atlas reproduce los valores de referencia publicados

Antes de usarlo para nada, la primera pregunta es si el atlas es creíble. Lo es:

| | Nuestro atlas (35 controles) | Literatura (serie de 531 pacientes) |
|---|---|---|
| Hígado | mediana **2,19** · p95 3,23 | SUVmedia **2,34 ± 0,16** |
| Fondo vascular (aorta) | mediana **1,69** · p95 2,64 | SUVmedia **1,57 ± 0,14** |
| Razón hígado / fondo vascular | **1,30** | ≈ 1,5 |

Coincide dentro del margen esperable para medianas contra medias, con equipos y protocolos
distintos. **El atlas no es un invento del proyecto: mide lo que la clínica ya sabe.** Eso
importa porque es lo que permite usarlo como referencia sin pedirle fe a nadie.

El resto de los órganos, ordenados por cuánto captan (mediana de SUV, 35 controles):

```
vejiga  9,09  ·  riñones 2,27  ·  hígado 2,19  ·  corazón 1,97  ·  bazo 1,76
vasos   1,69  ·  páncreas/suprarrenales 1,54  ·  tiroides/esófago/tráquea 1,25
intestino 1,14  ·  otros órganos 1,09  ·  estómago 0,96  ·  hueso 0,91
músculo 0,70  ·  "otro" (grasa, piel, tejido blando) 0,52  ·  pulmón 0,51
```

---

## 2. ¿Hace falta bajar más estudios? **No.** Y está demostrado.

Era una pregunta abierta: el atlas de controles usa 35 pacientes, y autoPET tiene ~513
controles disponibles. La respuesta salió de dos mediciones.

**(a) Quintuplicar la muestra casi no mueve la referencia.** Pasar de 35 controles a los 176
estudios de entrenamiento (excluyendo la lesión anotada y su halo) cambia el p95 así:

| Cambio del p95 al pasar de 35 a 176 pacientes | Órganos |
|---|---|
| menos de 3 % | hígado, riñones, vasos, pulmón, hueso, vejiga, estómago, intestino, otro, páncreas/suprarrenales, otros órganos |
| 3 a 6 % | músculo, tiroides/esófago/tráquea |
| más de 10 % | **bazo +11,8 %** · **corazón −14,6 %** |

Si multiplicar por cinco el número de pacientes mueve la referencia menos de un 3 % en once de
quince órganos, multiplicarlo por diez no va a cambiar nada. **Bajar más estudios sería gastar
una tarde para no mover un número.**

Los dos que sí se movieron dicen algo:

- **Bazo, +11,8 %.** El bazo de la cohorte oncológica capta más que el de los controles. Es lo
  esperable en linfoma —compromiso esplénico difuso que autoPET no siempre anota, o bazo
  reactivo— y es un ejemplo concreto de la limitación del conjunto de datos, medido en vez de
  supuesto. **Para el bazo conviene usar la referencia de los 35 controles, no la de los 176.**
- **Corazón, −14,6 %.** La captación miocárdica depende del ayuno y es enormemente variable
  (CV 0,21). Con 35 pacientes el p95 es inestable; el de 176 es más confiable.

**(b) La variabilidad restante es fisiológica, no muestral.** El coeficiente de variación entre
pacientes ya es ≤ 0,25 en trece de quince órganos con solo 35 controles. Donde es alto
—**vejiga 0,85**, **estómago 0,43**— la causa es real: la vejiga depende de la hidratación y de
si el paciente orinó antes del estudio. Ningún número de pacientes arregla eso.

---

## 3. La referencia interna del paciente: dónde ayuda y dónde no

La escala de Deauville no usa tablas poblacionales: compara contra el hígado *del propio
estudio*. Se midió si eso reduce la variabilidad entre pacientes.

| Órgano | CV absoluto | CV referido al hígado propio | |
|---|---|---|---|
| Fondo vascular | 0,134 | **0,089** | −34 % |
| Tiroides / esófago / tráquea | 0,184 | **0,144** | −22 % |
| Riñones | 0,135 | **0,106** | −21 % |
| Bazo | 0,175 | **0,138** | −21 % |
| Vejiga | 0,850 | 0,710 | −16 %, sigue enorme |
| Intestino, corazón, músculo, pulmón | ≈ igual | ≈ igual | sin efecto |
| Hueso | 0,179 | 0,198 | +11 %, **peor** |
| Páncreas / suprarrenales | 0,130 | 0,153 | +18 %, **peor** |
| "Otro" (grasa, piel, tejido blando) | 0,334 | 0,353 | +6 %, **peor** |

La lectura es fisiológicamente coherente y vale la pena decirla así: **la referencia hepática
sirve para los tejidos cuya captación sigue al hígado —los que se perfunden con la sangre y
siguen la disponibilidad sistémica de glucosa— y estorba en los que tienen su propia
fisiología.** El hueso, el páncreas y la grasa no varían con el hígado, así que dividir por él
solo les agrega el ruido del hígado.

Esto explica por qué Deauville se limita a linfoma ganglionar y no se aplica a cualquier foco
en cualquier parte: la referencia hepática vale donde vale.

---

## 4. La prueba decisiva: ¿separa mejor?

3 117 hallazgos (1 457 verdaderos, 1 660 falsos) de las nueve corridas sobre los 26 estudios de
validación, con la definición de falso positivo de autoPET.

| Puntuación | AUC | vs SUV crudo |
|---|---|---|
| SUVmáx crudo | 0,813 | — |
| Veces el hígado del propio paciente | 0,821 | +0,008 |
| SUVmáx / p95 poblacional del órgano | 0,837 | +0,024 |
| z robusto poblacional del órgano | 0,839 | +0,025 |
| **Veces el hígado propio / p95 del órgano** | **0,844** | **+0,030** |

La ganancia es **modesta pero consistente**: la mejor puntuación supera al SUV crudo en las
nueve corridas, sin excepción. No es ruido. Pero tampoco es espectacular: al fijar el punto de
operación que conserva el 95 % de los hallazgos verdaderos, se pasa de eliminar el **40,3 %** de
los falsos a eliminar el **42,0 %**. Menos de dos puntos.

### El hallazgo que importa está en el desglose por órgano

Dentro de un mismo órgano, `SUVmáx`, `SUVmáx / p95` y `z robusto` dan **exactamente el mismo
AUC** (hueso 0,938 / 0,938 / 0,938; "otro" 0,785 / 0,785 / 0,785; pulmón 0,843 en las tres). No
es casualidad: dividir por una constante del órgano es una transformación monótona, no cambia
el orden, y el AUC solo depende del orden. **Toda la ganancia de la tabla poblacional viene de
hacer comparables entre sí a órganos distintos, no de aportar información nueva dentro de uno.**

Las puntuaciones con referencia interna, en cambio, **sí cambian el AUC dentro del órgano**,
porque el divisor cambia de paciente a paciente:

| Órgano | AUC con SUV crudo | AUC con referencia interna |
|---|---|---|
| Riñones | 0,887 | **1,000** |
| Hígado | 0,698 | **0,778** |
| Pulmón | 0,843 | **0,881** |
| "Otro" | 0,785 | **0,807** |
| Tiroides / esófago / tráquea | 0,979 | **1,000** |

Es decir: **la referencia interna del paciente aporta información que el SUV absoluto no
contiene, y la tabla poblacional no.**

### Y acá está el argumento mecánico

La red se entrena con parches de 96³ vóxeles, o sea **288 mm de lado**. Desde un parche
centrado en la pelvis, la red **no puede ver el hígado**: está fuera del campo. La captación
hepática del paciente es una propiedad global del estudio que **no es deducible del parche**,
por mucho que se entrene.

Esto es exactamente el tipo de razonamiento que explicó por qué la atención cruzada quedó
inerte —la normalización de instancia cancelaba su aporte—, pero apuntando al revés: aquí hay
información que la red demostrablemente no puede tener, y que se le puede entregar por un
canal. El órgano, en cambio, **sí** es deducible del CT dentro del parche, que es probablemente
la razón de que la tabla poblacional no aporte nada dentro del órgano.

---

## 5. Limitaciones encontradas, para declararlas antes de que las pregunten

1. **El SUV está saturado en 30.** El preprocesamiento aplica un tope (SUV/30 con corte), así
   que la vejiga tiene p95 = p99 = 30,0 y el histograma del SUV crudo muestra un pico artificial
   en 30. Afecta a la vejiga y a los focos muy calientes. No invalida las medianas ni los
   percentiles medios, pero sí los extremos, y hay que tenerlo en cuenta si el canal nuevo se
   construye dividiendo un SUV ya saturado.
2. **Encéfalo: cero pacientes.** El *defacing* borra la cabeza, así que no hay atlas cerebral.
   Era esperable y está declarado desde el protocolo.
3. **Páncreas y suprarrenales tienen AUC bajo 0,5** (0,364 crudo, 0,318 con referencia interna,
   con 18 verdaderos y 22 falsos). El puntaje ordena los falsos *por encima* de los verdaderos
   en ese grupo. Con esos números puede ser azar, pero merece mirarse.
4. **231 falsos positivos caen mayoritariamente fuera de la máscara corporal** (grupo "fuera").
   Es un filtro trivial y gratuito que todavía no aplicamos. Aparecen además 25 lesiones
   anotadas cuyo grupo dominante es "fuera", lo que señala que la máscara corporal recorta de
   más en algunos estudios.

---

## 6. Qué queda decidido

- **No se bajan más estudios.** Demostrado en la sección 2.
- **El atlas de referencia es el de los 176**, salvo para el bazo, donde se usa el de los 35
  controles por el sesgo de la cohorte oncológica.
- **La referencia interna del paciente (Deauville) es la única de las cuatro puntuaciones que
  aporta información no deducible del parche**, y por eso es la candidata a canal de entrada.
- La ganancia esperable es modesta. Se entrena para medirla, no porque esté garantizada; y si
  no mejora, el resultado refuerza la tesis de que el techo está en la anotación.

Archivos: `results/atlas_normalidad_controles.csv`, `results/atlas_normalidad_train.csv`,
`results/atlas_por_paciente_*.csv`, `results/comparacion_atlas.csv`,
`results/separacion_hallazgos_val.csv`, `results/separacion_resumen_val.csv`,
`results/separacion_por_organo_val.csv`, `docs/figuras/separacion_val.png`.
