# Modelo E: qué hizo el canal de referencia interna

*2026-09-11. Semilla 423, la única entrenada hasta ahora. Validación completa, 26 estudios
(20 positivos según el criterio del reto, `mtv_gt > 0`).*

El modelo E es la arquitectura de A sin ningún cambio, con un tercer canal de entrada: el SUV de
cada vóxel dividido por el SUV hepático **de ese mismo paciente**, con tope en 8 veces. Es la
lógica de la escala de Deauville. La pregunta que este documento responde es si ese canal sirve.

## 1. El canal no está inerte

La ablación sustituye la referencia hepática de cada paciente por la constante poblacional
(2,165, la mediana de los 176 de entrenamiento). Los pesos son los mismos; lo único que cambia es
el contenido del tercer canal.

**23 de las 26 predicciones cambian.** A diferencia de la atención cruzada del modelo C, que no
movía un solo vóxel al apagarla, este canal sí entra en el cálculo.

| | con el hígado del paciente | con la constante poblacional | diferencia |
|---|---|---|---|
| Dice⁺ | 0,635 | 0,628 | +0,007 · IC95% [−0,002, +0,017] · p 0,40 |
| FPV | 11,81 mL | 13,25 mL | −1,44 mL · IC95% [−3,77, +0,22] · p 0,37 |
| FNV | 8,76 mL | 9,05 mL | −0,30 mL · no empeora en ningún estudio |

Las tres diferencias apuntan en la dirección esperada y ninguna excluye el cero. **El aporte
propio del canal es del orden de 1,4 mL de falso positivo**, concentrado en tres estudios que ya
tenían un FPV alto (55 → 80 mL en el mayor de ellos).

## 2. La comparación con A dependía del checkpoint, no del canal

La primera lectura, con el checkpoint que el protocolo elige (`mejor.pt`), parecía espectacular:

| | E (`mejor`, iter 9 000) | A (`mejor`, 3 semillas) | diferencia |
|---|---|---|---|
| Dice⁺ | 0,635 | 0,621 | +0,013 · p 1,00 |
| FPV | 11,81 mL | 20,93 mL | **−9,12 mL** · IC95% [−16,2, −2,9] · p 0,0024 |
| FNV | 8,76 mL | 6,02 mL | +2,74 mL · p 0,11 |

Pero la ablación ya había dicho que el canal explica 1,4 mL, no 9. Los otros 7,7 tenían que venir
de otro lado, y venían del checkpoint: **el de E es de la iteración 9 000 y los de A son de 22 000
a 24 000**. Un modelo menos entrenado predice menos volumen, y menos volumen es automáticamente
menos falso positivo y más falso negativo.

Se comprueba mirando el volumen que cada uno dibuja, contra los 151,7 mL de MTV medio anotado:

| | Dice⁺ | mediana | FPV | FNV | MTV predicho |
|---|---|---|---|---|---|
| E, iteración 9 000 | 0,635 | 0,703 | 11,81 mL | 8,76 mL | 110,5 mL |
| E, iteración 25 000 | 0,632 | 0,739 | 22,64 mL | 6,15 mL | 146,5 mL |
| A, iteración 25 000 | 0,615 | 0,665 | 21,74 mL | 5,85 mL | 137,7 mL |

El checkpoint de 9 000 subsegmenta: dibuja 110 mL donde hay 152. Eso le regala un FPV bajo.

## 3. A igual presupuesto de entrenamiento, E y A son indistinguibles

| E a 25 000 contra A a 25 000 | diferencia |
|---|---|
| Dice⁺ 0,632 vs 0,615 | +0,017 · IC95% [−0,013, +0,047] · p 0,29 |
| FPV 22,64 vs 21,74 mL | +0,90 mL · IC95% [−2,42, +4,76] · p 0,84 |
| FNV 6,15 vs 5,85 mL | +0,30 mL · p 0,25 |

**La ventaja de falso positivo desaparece por completo.** Queda una diferencia de Dice de +0,017
que no es significativa, pero que apunta en la misma dirección en los dos checkpoints (+0,013 y
+0,017) y es mayor en la mediana (0,739 contra 0,665).

## 4. Lo que hay que decir en la defensa

1. **El canal está vivo, y eso ya distingue a E de C.** La atención cruzada no movía un vóxel;
   la referencia interna cambia 23 de 26 predicciones. Que el efecto sea pequeño es un resultado,
   no un fracaso de implementación.
2. **La hipótesis fuerte no se sostiene con una semilla.** "Decirle a la red cuántas veces el
   hígado del propio paciente brilla este vóxel" no bajó el falso positivo de forma medible a
   igual entrenamiento.
3. **Aparece un hallazgo metodológico que vale por sí mismo:** seleccionar el checkpoint con una
   validación rápida de 12 estudios es ruidoso, y el ruido no es inocente. La misma red, según
   qué checkpoint elija ese criterio, informa 11,8 o 22,6 mL de FPV. Cualquier comparación entre
   arquitecturas que no controle esto puede estar midiendo el azar de la curva de validación.
4. **Más semillas no van a volver significativo el +0,017 de Dice.** El ancho del intervalo está
   dominado por los 20 estudios positivos de validación, no por la semilla. Las semillas 2 y 3
   sirven para poder afirmar "E no difiere de A" con el mismo rigor con que se afirmó "A, B y C
   empatan", no para convertir una diferencia chica en una grande.

## Archivos

- `results/modelo_E_val.csv` — E con `mejor.pt`
- `results/modelo_E_sin_ref_val.csv` — la ablación
- `results/modelo_E_ultimo_val.csv` — E con `ultimo.pt`
- `results/comparacion_criterio_checkpoint_val.csv` — mejor contra último en las nueve corridas previas

---

## 5. Con la segunda semilla: el criterio de checkpoint es el verdadero hallazgo

*Añadido el 2026-09-11, tras evaluar `runs/E_s2` con los dos checkpoints.*

La semilla 2 llegó a su mejor validación rápida en la iteración 16 000, no en la 9 000.
El pico temprano de la semilla 423 no se repitió: en esta corrida la iteración 9 000 es uno
de los peores puntos de toda la curva (Dice 0,360 contra 0,587 del mejor).

### Lo que aparece al poner los cuatro brazos lado a lado

**Criterio `mejor.pt`, el del protocolo** (media ± sd entre semillas, y los valores crudos):

| brazo | Dice⁺ | FPV mL | FPV por semilla |
|---|---|---|---|
| A | 0,621 ± 0,016 | 20,93 ± 2,50 | 18,0 · 22,2 · 22,5 |
| B | 0,612 ± 0,014 | 22,78 ± 3,08 | 20,3 · 26,2 · 21,9 |
| C | 0,612 ± 0,008 | 23,18 ± 6,65 | 16,1 · 24,0 · 29,4 |
| E | 0,628 ± 0,010 | 21,56 ± **13,78** | **11,8 · 31,3** |

**Criterio `ultimo.pt`, las 25 000 iteraciones completas en los cuatro brazos:**

| brazo | Dice⁺ | FPV mL | FPV por semilla |
|---|---|---|---|
| A | 0,615 ± 0,020 | 21,74 ± **0,49** | 21,8 · 21,2 · 22,2 |
| B | 0,607 ± 0,002 | 22,11 ± 2,79 | 25,0 · 19,4 · 21,9 |
| C | 0,610 ± 0,007 | 21,50 ± 1,76 | 21,2 · 19,9 · 23,4 |
| E | 0,638 ± 0,009 | 22,03 ± **0,86** | 22,6 · 21,4 |

La dispersión de FPV entre semillas, criterio contra criterio:

| brazo | con `mejor` | con `ultimo` |
|---|---|---|
| A | 2,50 | 0,49 |
| B | 3,08 | 2,79 |
| C | 6,65 | 1,76 |
| E | 13,78 | 0,86 |

**En los cuatro brazos la dispersión baja al dejar de elegir checkpoint.** El caso de E es
el extremo — el mismo brazo informa 11,8 o 31,3 mL de FPV según qué semilla se mire — pero
la dirección es la misma en todos. Dicho de otro modo: **seleccionar el checkpoint con una
validación rápida de 12 estudios mete más variabilidad en el resultado que la propia
semilla de inicialización.** Eso está medido sobre once corridas, no es una anécdota.

La razón es mecánica: la validación rápida mide Dice, pero al elegir el máximo de una
curva ruidosa se arrastra cualquier cosa que haya acompañado a ese máximo, y el FPV es
justamente lo que más se mueve entre mediciones consecutivas. El criterio optimiza una
métrica y deja las otras dos al azar.

### Y sobre E

Con las 25 000 iteraciones, E queda en Dice 0,638 y es el único brazo por encima de 0,62.
Pero el pareado por estudio no sostiene la ventaja:

| | diferencia de Dice | IC95% | p | E mejor en |
|---|---|---|---|---|
| E − A | +0,023 | [−0,003, +0,050] | 0,13 | 12/20 |
| E − B | +0,031 | [−0,017, +0,089] | 0,67 | 11/20 |
| E − C | +0,029 | [−0,014, +0,080] | 0,47 | 11/20 |

El FPV es idéntico en los cuatro (diferencias por debajo de 0,6 mL, todas con p > 0,6).

Que E gane en 11 o 12 estudios de 20 —cuando un empate perfecto daría 10— dice que la
ventaja no es sistemática: viene de ganar por bastante en unos pocos estudios, no de ser
mejor en la mayoría. Con la tercera semilla se cierra, pero la lectura hoy es que **el
canal de referencia interna no cambia el resultado de forma demostrable**, y que lo que sí
apareció en el camino es un problema del protocolo de selección que afecta a los cuatro
brazos por igual.
