# Las fusiones no empataban: el presupuesto las estaba igualando

*Rama `extendido`, 2026-09-17. A, B y C entrenados con 825 estudios y 100 000 iteraciones,
una semilla cada uno, evaluados sobre los mismos 26 estudios de validación.*

## El resultado

| brazo | parámetros | Dice⁺ | mediana | FPV mL | FNV mL |
|---|---|---|---|---|---|
| A · fusión temprana | 12,9 M | 0,681 | 0,806 | 15,76 | 3,91 |
| **B · codificador dual, concatenación** | **24,0 M** | **0,714** | 0,774 | **12,06** | 3,78 |
| C · codificador dual, atención cruzada | 24,4 M | 0,710 | 0,767 | 13,48 | 3,11 |

| comparación | Dice | IC95% | p | gana en |
|---|---|---|---|---|
| **B − A** | **+0,033** | **[+0,008, +0,060]** | **0,030** | **15/20** |
| C − A | +0,029 | [−0,011, +0,078] | 0,65 | 11/20 |
| B − C | +0,004 | [−0,028, +0,034] | 0,47 | 12/20 |

## La inversión

Este es el hallazgo, y no estaba buscado:

| brazo | 25 000 iteraciones | 100 000 iteraciones |
|---|---|---|
| A | **0,615** | 0,681 |
| B | 0,607 | **0,714** |
| C | 0,610 | 0,710 |

**Con presupuesto corto gana el modelo más chico. Con presupuesto adecuado ganan los
grandes, y el orden se invierte por completo.** B pasa de estar 0,008 por debajo de A a estar
0,033 por encima, con el intervalo de confianza fuera del cero.

La explicación es mecánica y no requiere nada sofisticado: B y C tienen casi el doble de
parámetros que A (24,0 y 24,4 M contra 12,9 M). Cuanto más grande el modelo, más entrenamiento
necesita para converger. Compararlos con A a igualdad de iteraciones parece una comparación
justa —mismo presupuesto para todos— pero no lo es: es igualdad de recursos con desigualdad de
convergencia. Los dos modelos grandes estaban evaluándose a medio camino.

**Consecuencia:** la conclusión de `main`, *"las tres fusiones empatan"*, es cierta **solo bajo
ese presupuesto**. Con presupuesto suficiente, el codificador dual sí aporta.

Y la consecuencia general, que excede este proyecto: **una comparación de arquitecturas con
presupuesto de entrenamiento insuficiente puede invertir el orden de los resultados.** No los
comprime hacia el empate, los da vuelta. Cualquier trabajo que compare arquitecturas de
distinto tamaño con un presupuesto fijo y corto corre ese riesgo.

## La atención cruzada está muerta, y ahora se sabe por qué

La ablación se repitió sobre la corrida de 100 000 iteraciones:

- **gamma aprendido: 0,992.** El parámetro de mezcla quedó prácticamente en 1, o sea la red
  mantuvo la atención plenamente encendida.
- **Diferencia máxima al apagarla: 0,000** en todas las columnas de los 26 estudios. Las dos
  tablas son idénticas, vóxel a vóxel.

Que gamma sea 0,992 y no 0 es más informativo que si hubiera colapsado. La red **no aprendió a
ignorar la atención**: aprendió a producir una salida de atención **espacialmente constante**,
y una constante sumada a todos los vóxeles la normalización de instancia la elimina de forma
exacta —resta la media y divide por la desviación—. De ahí el cero exacto, que de otro modo
haría sospechar de un error de cableado.

El mecanismo queda cerrado: la atención cruzada, colocada antes de una normalización de
instancia, no puede contribuir. No era falta de entrenamiento; con cuatro veces más sigue
siendo exactamente cero.

Y eso explica que C ≈ B (+0,004, p 0,47): **sin atención efectiva, C es B con 0,4 M de
parámetros extra.** Toda la ganancia de C viene del codificador dual, no de la atención.

## Dónde queda el trabajo

| | Dice⁺ | FPV |
|---|---|---|
| ganador autoPET 2022 | 0,623 | 2,84 mL |
| nnU-Net sin modificar | 0,690 | 5,78 mL |
| **B · 825 estudios · 100k** | **0,714** | 12,06 mL |

El Dice supera a las dos referencias. El falso positivo sigue siendo el doble que el de
nnU-Net, y ahí es donde apunta el paso siguiente (ensamble de cinco pliegues).

## La limitación honesta

**Una sola semilla por brazo en el régimen de 100 000 iteraciones.** Las corridas de 25 000
tienen tres cada una; estas, una. La inversión del orden es una señal fuerte —B se mueve
0,041 respecto de A entre los dos regímenes— pero afirmarla con el rigor de la Parte 1 exige
repetir con dos semillas más por brazo: seis corridas, unas 150 horas de cómputo.

Mientras eso no se haga, el resultado se reporta como lo que es: una observación de una
semilla, consistente con un mecanismo explicable y con un efecto que el intervalo de confianza
del pareado por estudio respalda en el caso de B.
