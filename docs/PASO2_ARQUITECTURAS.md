# Las fusiones no empataban: el presupuesto las estaba igualando

*Rama `extendido`, 2026-09-17 (una semilla) y 2026-09-27 (tres semillas más el control A+, al final). A, B y C entrenados con 825 estudios y 100 000 iteraciones,
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

## Con tres semillas por brazo (2026-09-27)

La limitación de "una sola semilla" quedó resuelta con `scripts/27_semillas_largo.sh`: tres
semillas (423, 2, 3) de A, B y C, más el control de capacidad A+ (fusión temprana con
canales ×1,375: 24,3 M, los parámetros de B) también con tres semillas. Doce corridas de
100 000 iteraciones, ~10 días de Mac. Métrica corregida (sin zona borrada) salvo donde se
indica.

| brazo | parámetros | Dice⁺ (media ± sd) | por semilla | FPV mL | FPV mediana | FNV mL |
|---|---|---|---|---|---|---|
| A · fusión temprana | 12,9 M | 0,694 ± 0,013 | 0,681 · 0,695 · 0,706 | 15,1 | 5,7 | 4,1 |
| A+ · fusión temprana ancha | 24,3 M | 0,694 ± 0,020 | 0,693 · 0,714 · 0,675 | 15,8 | 6,8 | 4,2 |
| B · dual + concatenación | 24,0 M | 0,705 ± 0,011 | 0,714 · 0,709 · 0,694 | 13,3 | 4,3 | 3,8 |
| **C · dual + atención** | 24,4 M | **0,713 ± 0,003** | 0,710 · 0,715 · 0,714 | **13,2** | 4,3 | **3,4** |

Pareado por estudio sobre el promedio de las tres semillas (Dice⁺ en los 20 positivos, FPV
en los 26; IC95 por bootstrap; p de Wilcoxon):

| comparación | ΔDice⁺ | IC95 | gana | p | ΔFPV mL | gana | p |
|---|---|---|---|---|---|---|---|
| A+ − A | +0,000 | [−0,014, +0,019] | 6/20 | 0,26 | +0,8 | 9/26 | 0,08 |
| B − A | +0,012 | [−0,005, +0,031] | 13/20 | 0,22 | −1,8 | 14/26 | 0,57 |
| C − A | +0,019 | [−0,006, +0,047] | 12/20 | 0,45 | −1,9 | 13/26 | 0,64 |
| B − A+ | +0,011 | [−0,010, +0,032] | 13/20 | 0,13 | −2,6 | 17/26 | 0,11 |
| C − A+ | +0,019 | [+0,001, +0,037] | 13/20 | 0,09 | −2,7 | 15/26 | 0,24 |
| C − B | +0,008 | [−0,010, +0,030] | 9/20 | 0,96 | −0,1 | 15/26 | 0,57 |

Lo que queda en pie y lo que no:

1. **La primera semilla de B sobreestimó su efecto 3×.** El +0,033 (p 0,03) de la tabla de
   arriba bajó a +0,012 con tres semillas, con el intervalo cruzando cero. La inversión de
   arquitecturas sigue existiendo como tendencia (con 25k gana A; con 100k los dos brazos
   duales quedan por encima en las tres semillas de C y en dos de tres de B), pero **no es
   estadísticamente distinguible del ruido entre semillas** con 20 estudios positivos.
2. **El control A+ responde la pregunta que motivó su existencia: más red sola no ayuda.**
   A+ tiene los parámetros de B y da exactamente el Dice de A (0,694 contra 0,694), con más
   falso positivo, no menos. Lo que B y C tienen de distinto respecto de A+ es la separación
   de PET y CT en dos codificadores, y esa es la única diferencia que se mueve en la dirección
   correcta en las tres métricas (Dice +0,01 a +0,02; FPV −2,6 mL; FNV −0,4 a −0,8 mL). Es
   un efecto chico, consistente y no significativo: se reporta como tal.
3. **La atención cruzada sigue inerte en las tres semillas de C**: apagarla en inferencia da
   diferencia 0,000 en las 26 filas, tres de tres. C es B con otra inicialización. Que C sea
   el brazo más estable (sd 0,003 contra 0,011–0,020) no se le puede atribuir a la atención;
   queda anotado sin explicación.
4. **Dónde vive el falso positivo (media de tres semillas, mL por estudio):** órganos con
   captación fisiológica A 3,2 / A+ 3,8 / B 2,6 / C 2,8; "otro" + pulmón + bordes A 12,1 /
   A+ 12,5 / B 11,2 / C 10,7. El codificador dual baja ambos, sobre todo hígado (0,55 → 0,35)
   y músculo (1,34 → 0,57); sube intestino (0,20 → 0,52). El 80 % del falso positivo restante
   está en tejido sin etiqueta, pulmón y bordes, no en los órganos calientes: ese es el
   problema del paso siguiente (`PASO3_ANATOMIA.md`).

Tabla del reto (cruda, con zona borrada): Dice⁺ A 0,625 / A+ 0,626 / B 0,637 / C 0,641;
FPV 15,8 / 16,9 / 14,2 / 14,0 mL. Todas por encima del ganador de 2022 en Dice (0,623) y
todas con 2–3× su falso positivo (2,84 mL), sin ensamble ni postproceso.

## La limitación honesta

Veinte estudios positivos de validación no alcanzan para detectar una diferencia de 0,01–0,02
de Dice entre brazos: el intervalo de confianza de cualquier comparación mide ±0,02. Con tres
semillas se pudo descartar que la ventaja de B fuera del tamaño del primer reporte, y se pudo
descartar que fuera solo por capacidad; no se pudo demostrar que exista. Lo que sí se
puede afirmar es que **con presupuesto suficiente ninguna fusión es peor que la temprana**,
lo contrario de lo que decía `main` con 25 000 iteraciones, y que la diferencia en falso
positivo (~2 mL, 15 %) es consistente en semillas y en órganos aunque no llegue a
significancia.

El test (49 estudios) sigue cerrado y se abrirá una sola vez, con todos los brazos.
