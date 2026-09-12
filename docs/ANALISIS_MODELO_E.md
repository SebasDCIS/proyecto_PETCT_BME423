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

## 5. Cierre del paso 5: las tres semillas

*2026-09-12. Tres semillas de E entrenadas y evaluadas con los dos checkpoints. Doce
corridas en total entre los cuatro brazos.*

### El resultado sobre el modelo E

**Criterio `mejor.pt`, el del protocolo congelado:**

| brazo | Dice⁺ | FPV mL | FNV mL | FPV por semilla |
|---|---|---|---|---|
| A | 0,621 ± 0,016 | 20,93 ± 2,50 | 6,02 | 18,0 · 22,2 · 22,5 |
| B | 0,612 ± 0,014 | 22,78 ± 3,08 | 5,36 | 20,3 · 26,2 · 21,9 |
| C | 0,612 ± 0,008 | 23,18 ± 6,65 | 5,93 | 16,1 · 24,0 · 29,4 |
| E | 0,640 ± 0,022 | 21,97 ± 9,77 | 7,27 | 11,8 · 31,3 · 22,8 |

**Criterio `ultimo.pt`, las 25 000 iteraciones en los cuatro brazos:**

| brazo | Dice⁺ | FPV mL | FNV mL | FPV por semilla |
|---|---|---|---|---|
| A | 0,615 ± 0,020 | 21,74 ± 0,49 | 5,85 | 21,8 · 21,2 · 22,2 |
| B | 0,607 ± 0,002 | 22,11 ± 2,79 | 4,44 | 25,0 · 19,4 · 21,9 |
| C | 0,610 ± 0,007 | 21,50 ± 1,76 | 4,45 | 21,2 · 19,9 · 23,4 |
| E | 0,638 ± 0,006 | 23,63 ± 2,84 | 5,70 | 22,6 · 21,4 · 26,8 |

El pareado por estudio, promediando las tres semillas de cada brazo:

| | Dice | IC95% | p | E gana en |
|---|---|---|---|---|
| E − A | +0,024 | [−0,003, +0,051] | 0,23 | 11/20 |
| E − B | +0,031 | [−0,019, +0,090] | 0,73 | 9/20 |
| E − C | +0,029 | [−0,015, +0,080] | 0,57 | 11/20 |

Y con el criterio del protocolo, E gana en 8, 6 y 8 estudios de 20 — **menos de la mitad**.
El FPV no se distingue en ninguna comparación (todas las p por encima de 0,30).

**Conclusión del paso 5: el canal de referencia interna no cambia el resultado.** La
ventaja aparente de Dice es ruido de muestreo: apunta siempre en la misma dirección pero
ningún intervalo excluye el cero y E no gana en la mayoría de los estudios. La hipótesis
—darle a la red cuántas veces el hígado del propio paciente brilla cada vóxel— queda
descartada con el mismo rigor con que quedó descartada la atención cruzada de C.

Con una diferencia importante entre las dos: la atención de C estaba **muerta** (apagarla
no movía un vóxel); el canal de E está **vivo** (cambia 23 de 26 predicciones) pero su
efecto neto se cancela. Son dos fracasos distintos y conviene contarlos distinto.

### El resultado que no buscábamos

La dispersión de FPV entre semillas, según qué criterio elija el checkpoint:

| brazo | con `mejor` | con `ultimo` | factor |
|---|---|---|---|
| A | 2,50 | 0,49 | **5,1×** |
| B | 3,08 | 2,79 | 1,1× |
| C | 6,65 | 1,76 | **3,8×** |
| E | 9,77 | 2,84 | **3,4×** |

**En los cuatro brazos la dispersión baja al dejar de elegir checkpoint**, y en tres de
cuatro baja entre tres y cinco veces. Dicho de otro modo: **seleccionar el checkpoint con
una validación rápida de doce estudios mete en el resultado más variabilidad que la propia
semilla de inicialización** — que era justamente el ruido contra el que se corrieron tres
semillas por brazo.

El mecanismo es directo y se puede defender sin apelar a nada sofisticado: el criterio
busca el máximo de Dice en una curva ruidosa y arrastra consigo lo que haya acompañado a
ese máximo. El FPV es lo que más se mueve entre mediciones consecutivas, así que queda
decidido por azar. **El criterio optimiza una métrica y deja las otras dos sueltas.** El
caso extremo es E, donde las tres semillas eligieron checkpoint en las iteraciones 9 000,
16 000 y 18 000, con FPV de 5,0, 17,6 y 20,6 mL en la validación rápida.

Es el mismo error que elegir el punto de corte de un marcador en la misma muestra donde se
lo descubrió: en aprendizaje automático se hace de forma rutinaria y casi nunca se reporta.

### Qué queda

El paso 5 está cerrado. Lo que sigue es una decisión, no un cálculo: abrir el conjunto de
prueba con los cuatro brazos tal como están, o antes de eso correr lo que quedó escrito en
la rama `exploracion/umbral-y-atlas` (ver `docs/EXPLORACION_PENDIENTE.md`). Sea cual sea la
elección, **el test se abre una sola vez, al final, cuando no quede ninguna decisión
pendiente.**
