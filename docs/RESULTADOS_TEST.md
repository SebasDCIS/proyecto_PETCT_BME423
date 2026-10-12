# Resultados en el conjunto de prueba

*2026-10-12. El test (49 estudios, 38 positivos evaluables) se abrió una sola vez, a las 00:36 UTC,
con el preregistro del commit `90a35e1`. Todo lo que se mide y cómo se decide estaba escrito antes
(`docs/TEST_PREREGISTRO.md`). Las tablas completas están en `results/test_final/resumen.md`; aquí va
la lectura.*

## Las dos hipótesis preregistradas se confirman

| | ΔDice⁺ contra B | IC95 | ΔFPV contra B (mL) | IC95 | veredicto |
|---|---|---|---|---|---|
| H1 · ensamble + TTA, umbral 0,5 | +0,028 | [+0,011, +0,048] | −7,01 | [−12,35, −3,38] | confirmada |
| H2 · sistema final (umbral 0,6, sin regla del hígado) | +0,029 | [+0,006, +0,054] | −9,38 | [−16,44, −4,47] | confirmada |

B es la fusión intermedia de la etapa extendida (825 estudios, 100 000 iteraciones, media de tres
semillas). El falso positivo baja en los 49 estudios, sin excepción. El sistema final queda en
Dice⁺ 0,727 (mediana 0,806), FPV 9,5 mL y FNV 3,95 mL. Con la métrica cruda del reto, sin excluir
la zona anonimizada: Dice⁺ 0,705, FPV 9,5 mL.

Contra sus propios cinco miembros el ensamble con TTA gana +0,029 [+0,019, +0,041] en 34 de 38
positivos. Por lesión detecta lo mismo que un B solo (330 de 435 contra 327 a 337) con la mitad de
marcas falsas por estudio (7,8 contra 12,8 a 13,6). El sistema final baja a 6,3 marcas a cambio de
8 lesiones menos (322 de 435).

## El acto 1 en el test (S5)

| contra A, acto 1 | ΔDice⁺ | IC95 | ΔFPV (mL) | IC95 | estudios donde baja el FPV | p (Wilcoxon, FPV) |
|---|---|---|---|---|---|---|
| B | +0,015 | [−0,017, +0,054] | −14,86 | [−29,79, −3,21] | 25 de 49 | 0,174 |
| C | −0,008 | [−0,040, +0,031] | −13,60 | [−27,91, −1,92] | 17 de 49 | 0,758 |
| E | −0,020 | [−0,052, +0,013] | −9,89 | [−23,15, +1,00] | 29 de 49 | 0,184 |

En Dice la conclusión de `main` se sostiene: los tres intervalos cruzan el cero. En FPV no del todo.
La media de A en el test es 38,4 mL con mediana 13,2: cuatro estudios concentran el exceso (A pone
entre 212 y 267 mL en `1253499c80`, `05d5a79faf`, `a37c4e231f` y `14929994cf`). Por eso el
bootstrap de la media excluye el cero y la prueba de rangos no, y el FPV baja en menos de la mitad
de los estudios. Lo leo así: los dos codificadores separados (B y C por igual) evitan algunos fallos
grandes de la fusión temprana, pero no mejoran el estudio típico.

Sobre la hipótesis original (C baja el FPV frente a A sin subir el FNV): la media del FPV baja y el
FNV sube 0,9 mL [−0,19, +2,09], no significativo. Pero B logra lo mismo sin atención, y la ablación
de C dio diferencia cero en validación. **Lo que baje el FPV no se puede atribuir a la atención
cruzada; se atribuye al codificador doble.** E sube el FNV 2,4 mL [+0,32, +4,84].

## La etapa extendida en el test (S6, S7)

| contra A extendido | ΔDice⁺ | IC95 | ΔFPV (mL) | IC95 |
|---|---|---|---|---|
| A+ (mismo tamaño que B) | +0,001 | [−0,007, +0,009] | −3,06 | [−7,46, +0,31] |
| B | +0,038 | [+0,006, +0,076] | −7,69 | [−16,85, −1,62] |
| C | +0,034 | [+0,007, +0,069] | −7,63 | [−16,28, −1,84] |
| B preentrenada − B | +0,011 | [−0,002, +0,026] | −2,61 | [−5,39, −0,28] |

Este es el hallazgo nuevo del test. Con 825 estudios de entrenamiento, la fusión intermedia le gana
a la fusión temprana en Dice y en FPV, y no es por tamaño: A+, con los mismos parámetros que B, empata
con A. C sigue empatando con B. En validación (26 estudios) estas diferencias no alcanzaban; con 38
positivos sí. La respuesta a la pregunta que dejó abierta el acto 1 es que el empate de entonces era
falta de datos, al menos para el codificador doble.

## Resumen en tres líneas

1. El sistema final (ensamble de cinco pliegues con TTA a umbral 0,6) mejora a B en Dice y en
   falso positivo, y las dos hipótesis preregistradas se confirman.
2. Separar los codificadores de PET y CT ayuda cuando hay datos suficientes; la atención cruzada en
   el cuello no agrega nada sobre eso.
3. Las mejoras de anatomía (preentrenamiento del CT, pérdida pesada por órgano) no cambian el Dice;
   el preentrenamiento baja levemente el FPV.
