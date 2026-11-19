# Paso 1: no eran los datos, era el tiempo de entrenamiento

*Rama `extendido`, 2026-09-13. Tres corridas del modelo A que se diferencian solo en el
conjunto de entrenamiento y en el número de iteraciones. Validación: los mismos 26 estudios
de siempre. El conjunto de prueba sigue cerrado.*

## El resultado

| corrida | estudios | iteraciones | Dice⁺ | mediana | FPV mL | FNV mL |
|---|---|---|---|---|---|---|
| A (3 semillas) | 176 | 25 000 | 0,615 | 0,665 | 21,74 | 5,85 |
| A_ext | 825 | 25 000 | 0,636 | 0,744 | 24,70 | 5,11 |
| **A_ext_largo** | **825** | **100 000** | **0,681** | **0,806** | **15,76** | **3,91** |

El criterio de éxito, fijado antes de correr nada, era **Dice⁺ > 0,66**. Se cumplió.

## La atribución, que es lo que importa

Tres puntos permiten separar las dos variables que al principio estaban mezcladas:

**Más datos, mismo entrenamiento → nada.** De 176 a 825 estudios con las mismas 25 000
iteraciones: Dice +0,021, IC95% [−0,031, +0,078], p 0,87, gana en 9 de 20 estudios. El FPV
incluso sube. Dentro del ruido entre semillas.

**Mismos datos, cuatro veces más entrenamiento → sí.** De 25 000 a 100 000 iteraciones con
los mismos 825 estudios: **Dice +0,045, IC95% [+0,007, +0,081], p 0,0136, gana en 17 de 20.**

**Contra la línea base original:** Dice **+0,066**, IC95% [+0,018, +0,114], **p 0,0136**,
gana en **16 de 20**; FPV −5,98 mL (p 0,056); FNV −1,94 mL (p 0,19).

Es la primera diferencia del proyecto cuyo intervalo de confianza no cruza el cero. Y es la
primera vez que **las tres métricas se mueven a favor a la vez**: hasta acá, cada mejora en
una se pagaba con otra.

### Por qué no pasaba nada con más datos

Las 25 000 iteraciones estaban fijas, así que el número de veces que la red mira cada estudio
cambia con el tamaño del conjunto:

- 176 estudios: 50 000 parches ÷ 176 = **284 parches por estudio**
- 825 estudios: 50 000 parches ÷ 825 = **61 parches por estudio**

Se le dieron cinco veces más casos y el mismo tiempo para estudiarlos. Con 100 000
iteraciones vuelve a 242 por estudio, parecido a la línea base, y ahí sí aparece la mejora.

Para referencia: nnU-Net entrena por defecto **250 000 iteraciones** (1 000 épocas × 250),
diez veces nuestro presupuesto original.

## Dos efectos secundarios

**El problema del criterio de checkpoint desaparece.** Con 100 000 iteraciones, `mejor.pt` y
`ultimo.pt` dan Dice 0,677 y 0,681, y FPV 15,40 y 15,76. En las corridas de 25 000, esa misma
elección llegó a cambiar el FPV cuatro veces (11,8 contra 31,3 en el modelo E). Al entrenar lo
suficiente la curva de validación se aplana y deja de haber un máximo afortunado que elegir.
El hallazgo metodológico de `main` sigue siendo cierto —y ahora se sabe también cómo se
neutraliza.

**Dónde queda el trabajo.** nnU-Net sin modificar reporta Dice 0,690 con FPV 5,78; el ganador
de autoPET 2022, Dice 0,623 con FPV 2,84. Con 0,681 el Dice ya no es la brecha. **Lo que
sigue lejos es el falso positivo**, 2,7 veces el de nnU-Net.

## El control cerró la atribución: era el tiempo, no los datos

*Añadido el 2026-09-14, con `runs/A_176_largo` evaluado.*

Con las cuatro corridas queda un diseño factorial completo — dos tamaños de conjunto por dos
presupuestos de entrenamiento:

| | Dice⁺ | mediana | FPV mL | FNV mL |
|---|---|---|---|---|
| 176 estudios · 25 000 | 0,615 | 0,665 | 21,74 | 5,85 |
| 176 estudios · 100 000 | 0,655 | 0,706 | 15,49 | 5,21 |
| 825 estudios · 25 000 | 0,636 | 0,744 | 24,70 | 5,11 |
| 825 estudios · 100 000 | 0,681 | 0,806 | 15,76 | 3,91 |

Y separando los dos factores, pareado por estudio:

| efecto | Dice | IC95% | p | gana en | FPV |
|---|---|---|---|---|---|
| **iteraciones, con 176 estudios** | **+0,041** | [−0,013, +0,093] | **0,019** | **17/20** | **−6,24** |
| **iteraciones, con 825 estudios** | **+0,045** | [+0,007, +0,081] | **0,014** | **17/20** | **−8,94** |
| datos, con 25 000 iteraciones | +0,021 | [−0,031, +0,078] | 0,87 | 9/20 | +2,96 |
| datos, con 100 000 iteraciones | +0,025 | [−0,035, +0,093] | 0,45 | 12/20 | +0,26 |

**El efecto del presupuesto de entrenamiento se replica a sí mismo en las dos condiciones**:
+0,041 y +0,045, los dos significativos, los dos ganando en 17 de 20 estudios, y los dos
bajando el falso positivo entre 6 y 9 mL. Replicación interna, que es lo más parecido a una
prueba que permite este montaje.

**El efecto del tamaño del conjunto no aparece en ninguna de las dos.** Gana en 9 y en 12 de
20 estudios —cara o cruz— y no mueve el falso positivo.

### Conclusión del paso 1

Quintuplicar el conjunto de entrenamiento no cambió el resultado. Cuadruplicar el presupuesto
de entrenamiento sí, y de forma consistente. **El cuello de botella era cuánto entrenaba la
red, no cuántos casos tenía.**

Los 649 estudios adicionales no fueron un desperdicio: sin ellos no habría sido posible
demostrar que no importaban, y siguen disponibles para el ensamble y para los 2 mm, donde las
condiciones son distintas.

### Lo que esto le hace al resto del proyecto

La comparación de arquitecturas de `main` —A, B y C con 25 000 iteraciones— se hizo con un
presupuesto que ahora está demostrado insuficiente. Si un presupuesto corto ocultó una
diferencia de +0,066 dentro del propio modelo A, no hay razón para suponer que no haya
ocultado también las diferencias entre arquitecturas. **B, con 24,0 M de parámetros contra los
12,9 M de A, era el más castigado**: cuanto más grande el modelo, más entrenamiento necesita
para converger, y se lo comparó con A en igualdad de iteraciones creyendo que eso era
igualdad de condiciones.

Eso convierte la conclusión "las tres fusiones empatan" en una conclusión **condicionada al
presupuesto**, y obliga a reproducirla con 100 000 iteraciones. Pase lo que pase se gana:

- Si siguen empatando, la conclusión pasa de *"empatan con este presupuesto"* a *"empatan aun
  con presupuesto suficiente"*, que es mucho más fuerte.
- Si se separan, el hallazgo es que **la comparación de arquitecturas en segmentación médica
  es sensible al presupuesto de entrenamiento**, y buena parte de la literatura que compara
  arquitecturas con presupuestos cortos podría estar midiendo ruido.

Para el modelo C hay además una predicción falsable concreta: repetir la ablación
`--sin-atencion` sobre la corrida larga. La atención arrancaba con gamma 1 —plenamente
activa— y aun así apagarla no cambiaba un vóxel, lo que sugiere que la red la neutralizó por
mecanismo y no por falta de tiempo. Si con 100 000 iteraciones sigue inerte, queda cerrado.

---

## Apéndice: lo que faltaba cuando se escribió este documento

Queda un control: **A con los 176 estudios originales y 100 000 iteraciones** (`runs/A_176_largo`).

- Si iguala a A_ext_largo, los datos nunca aportaron y todo era presupuesto de entrenamiento.
- Si queda por debajo, los datos sí aportan, pero solo cuando hay tiempo para aprovecharlos.

Y para afirmar esto con el mismo rigor con que se cerró la Parte 1 harían falta dos semillas
más de A_ext_largo, que son 42 horas de cómputo. Con p 0,0136 y 16 de 20 estudios a favor la
señal es sólida, pero una sola semilla sigue siendo una sola semilla.

## Archivos

- `results/modelo_A_ext_largo_ultimo_val.csv` · `..._mejor_val.csv`
- `results/modelo_A_ext_ultimo_val.csv` — la corrida corta con el mismo conjunto
- `runs/A_ext_largo/validacion.csv` — 100 validaciones rápidas
