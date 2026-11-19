# Métricas complementarias sobre `test`

*Generado por `scripts/41_resumen_complementarias.py` a partir de `scripts/40`. Análisis secundario, declarado después de abrir la prueba y sin parámetros ajustables. Métrica corregida (sin la zona anonimizada) salvo en el contraste con el script oficial.*

## 1. Hausdorff 95 (mm), estudios positivos

| brazo | estudios con HD95 | predicción vacía (corridas) | mediana | p25 | p75 | media |
|---|---|---|---|---|---|---|
| Clásica | 38/38 | 0 | 252,9 | 145,7 | 387,0 | 261,4 |
| Clásica + exclusión de órganos | 38/38 | 0 | 306,2 | 158,8 | 412,9 | 299,9 |
| Acto 1 · A | 38/38 | 0 | 93,3 | 51,1 | 184,7 | 176,4 |
| Acto 1 · B | 38/38 | 0 | 123,7 | 47,7 | 201,1 | 181,7 |
| Acto 1 · C | 38/38 | 0 | 95,2 | 49,7 | 192,8 | 169,2 |
| Acto 1 · E | 38/38 | 0 | 110,5 | 50,4 | 181,8 | 167,2 |
| Extendido · A | 38/38 | 0 | 67,7 | 22,1 | 208,7 | 154,4 |
| Extendido · A+ | 38/38 | 0 | 59,5 | 28,9 | 183,4 | 162,7 |
| Extendido · B | 38/38 | 0 | 64,1 | 24,8 | 175,1 | 142,4 |
| Extendido · C | 38/38 | 0 | 52,2 | 18,8 | 249,3 | 152,6 |
| Extendido · B preentrenada | 38/38 | 0 | 61,7 | 16,9 | 168,1 | 138,8 |
| Ensamble + TTA (u 0,5) | 38/38 | 0 | 31,0 | 11,5 | 138,6 | 107,3 |
| Sistema final (u 0,6) | 38/38 | 0 | 23,5 | 9,8 | 97,7 | 97,8 |

Comparaciones pareadas (diferencia por estudio, en mm; negativo = bordes más cerca de la verdad):

| comparación | estudios | mediana de la diferencia | IC95 | mejora en | p (Wilcoxon) |
|---|---|---|---|---|---|
| Sistema final (u 0,6) − Extendido · B | 38 | -16,5 | [-26,2, -0,7] | 27/38 | 0,000 |
| Ensamble + TTA (u 0,5) − Extendido · B | 38 | -7,9 | [-21,2, -0,7] | 30/38 | 0,000 |
| Extendido · B − Extendido · A | 38 | -0,1 | [-4,9, 1,0] | 19/38 | 0,464 |
| Extendido · C − Extendido · A | 38 | -0,4 | [-3,6, 0,3] | 21/38 | 0,446 |
| Extendido · A+ − Extendido · A | 38 | 0,2 | [-1,5, 11,4] | 17/38 | 0,307 |
| Acto 1 · B − Acto 1 · A | 38 | 1,7 | [-0,9, 8,3] | 16/38 | 0,373 |
| Acto 1 · C − Acto 1 · A | 38 | 1,5 | [-7,9, 5,3] | 18/38 | 0,989 |
| Acto 1 · E − Acto 1 · A | 38 | -0,2 | [-14,7, 5,5] | 20/38 | 0,720 |
| Extendido · A − Acto 1 · A | 38 | -12,3 | [-38,6, 1,5] | 24/38 | 0,051 |
| Acto 1 · A − Clásica + exclusión de órganos | 38 | -89,9 | [-168,0, -56,9] | 33/38 | 0,000 |

## 2. Error de SUVmax por paciente, estudios positivos

SUVmax dentro de la predicción contra SUVmax dentro de la anotación. El SUV del preprocesamiento tiene tope en 30: 4 de 38 estudios positivos tienen un SUVmax anotado en el tope, y en ellos el error queda subestimado.

| brazo | estudios | error mediano (SUV) | error absoluto mediano | dentro de ±10 % | sesgo | límites de concordancia |
|---|---|---|---|---|---|---|
| Clásica | 38 | 7,38 | 7,38 | 32 % | 7,99 | -5,43 a 21,42 |
| Clásica + exclusión de órganos | 38 | 0,00 | 0,00 | 71 % | -0,45 | -10,67 a 9,76 |
| Acto 1 · A | 38 | 0,04 | 0,25 | 82 % | 1,35 | -5,19 a 7,89 |
| Acto 1 · B | 38 | 0,36 | 0,48 | 68 % | 1,82 | -4,58 a 8,23 |
| Acto 1 · C | 38 | 0,39 | 0,44 | 74 % | 1,45 | -4,02 a 6,93 |
| Acto 1 · E | 38 | 0,00 | 0,21 | 76 % | 1,19 | -3,67 a 6,04 |
| Extendido · A | 38 | 0,00 | 0,00 | 84 % | 1,16 | -5,46 a 7,79 |
| Extendido · A+ | 38 | 0,00 | 0,00 | 84 % | 1,10 | -5,48 a 7,68 |
| Extendido · B | 38 | 0,00 | 0,00 | 79 % | 1,50 | -5,84 a 8,83 |
| Extendido · C | 38 | 0,00 | 0,00 | 79 % | 1,38 | -6,10 a 8,87 |
| Extendido · B preentrenada | 38 | 0,00 | 0,00 | 82 % | 0,97 | -4,97 a 6,91 |
| Ensamble + TTA (u 0,5) | 38 | 0,00 | 0,00 | 84 % | 0,93 | -5,59 a 7,44 |
| Sistema final (u 0,6) | 38 | 0,00 | 0,00 | 87 % | 0,62 | -4,90 a 6,15 |

## 3. Contraste con el script oficial de autoPET (métrica cruda)

El oficial usa componentes con conectividad 18; el nuestro, 26. Mismas máscaras, sin excluir la zona anonimizada.

| brazo | Dice⁺ oficial | Dice⁺ nuestro | FPV oficial | FPV nuestro | FNV oficial | FNV nuestro | estudios con alguna diferencia | mayor diferencia en FPV (mL) |
|---|---|---|---|---|---|---|---|---|
| Clásica | 0,177 | 0,177 | 835,11 | 832,50 | 3,17 | 3,11 | 17/49 | 35,56 |
| Acto 1 · A (s423) | 0,596 | 0,596 | 38,26 | 38,26 | 7,93 | 7,92 | 4/49 | 0,03 |
| Extendido · B (s423) | 0,677 | 0,677 | 17,43 | 17,41 | 3,04 | 3,03 | 7/49 | 0,62 |
| Sistema final (u 0,6) | 0,705 | 0,705 | 9,50 | 9,50 | 4,91 | 4,90 | 3/49 | 0,00 |

## 4. Referencia clásica con y sin exclusión de órganos (TotalSegmentator)

| partición | variante | Dice⁺ | FPV (mL) | FNV (mL) | FPV en controles (mL) |
|---|---|---|---|---|---|
| val | Clásica | 0,180 | 1191,9 | 5,59 | 1224,4 |
| val | Clásica + exclusión de órganos | 0,366 | 108,7 | 18,01 | 77,4 |
| test | Clásica | 0,182 | 832,5 | 2,12 | 987,1 |
| test | Clásica + exclusión de órganos | 0,379 | 94,8 | 28,60 | 110,3 |
