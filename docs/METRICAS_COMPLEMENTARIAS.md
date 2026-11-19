# Métricas complementarias: Hausdorff 95, SUVmax, script oficial y clásica con órganos

*2026-10-25. Cuatro cosas que la definición de tema comprometía y que no estaban hechas. Las
calculé sobre las máscaras ya guardadas de la prueba (`scripts/40_metricas_complementarias.py`
y `scripts/41_resumen_complementarias.py`), sin entrenar ni volver a predecir nada. No
estaban en el preregistro, así que van como análisis secundario y no cambian los veredictos
de H1 y H2. Las tablas completas están en `results/test_final/complementarias.md`.*

## 1. Hausdorff 95

El HD95 mide qué tan lejos quedan los bordes de la predicción de los bordes de la verdad, en
milímetros. Para cada vóxel del borde predicho busco el borde verdadero más cercano, y al
revés; me quedo con el percentil 95 de cada lado y tomo el mayor (la convención de MONAI).
Lo calculé en los 38 estudios positivos, con la métrica corregida.

| brazo | mediana (mm) | p25 a p75 |
|---|---|---|
| Umbral clásico | 252,9 | 145,7 a 387,0 |
| Acto 1 · A | 93,3 | 51,1 a 184,7 |
| Extendido · B | 64,1 | 24,8 a 175,1 |
| Ensamble + TTA (u 0,5) | 31,0 | 11,5 a 138,6 |
| **Sistema final (u 0,6)** | **23,5** | 9,8 a 97,7 |

Contra B solo, el sistema final baja el HD95 en una mediana de 16,5 mm (IC95 de −26,2 a
−0,7), mejora en 27 de 38 estudios y Wilcoxon da p < 0,001. Entre arquitecturas no hay
diferencia: B contra A extendido da −0,1 mm (p 0,46) y en el acto 1 ninguna comparación se
acerca a la significancia.

Hay que leer bien estos números. El HD95 no mide solo el contorno de la lesión: una isla
falsa a 20 cm de cualquier lesión entra al cálculo y fija la distancia. Por eso los valores
son altos y la cola es larga, y por eso el ensamble, que deja la mitad de marcas falsas, es
lo único que lo baja de verdad.

## 2. Error de SUVmax por paciente

Comparé el SUVmax dentro de la predicción con el SUVmax dentro de la anotación, por
paciente. En el sistema final el error mediano es cero: en la mayoría de los pacientes el
vóxel más caliente que marca la red es el mismo que marcó el experto. El 87 % de los
pacientes queda dentro de un 10 %. De los cinco que quedan fuera, en cuatro la predicción da
un SUVmax mayor: la red marcó algo más caliente que la lesión, una marca falsa. El umbral
clásico sobreestima en 7,4 de mediana, porque se queda con la vejiga o el riñón.

Dos limitaciones. El preprocesamiento pone tope al SUV en 30, y 4 de los 38 estudios tienen
un SUVmax anotado en ese tope, donde el error queda subestimado. Y el SUVmax está medido en
la grilla de 3 mm, no en la resolución original del PET.

## 3. El script oficial de autoPET

Copié sin cambios `val_script.py` de github.com/lab-midas/autoPET (licencia MIT) en
`scripts/oficial_autopet/` y lo corrí sobre las mismas máscaras, en la métrica cruda que es la
que usa el reto.

Encontré una diferencia que hay que declarar: el oficial cuenta las islas con conectividad 18
(cara y arista) y el nuestro con 26 (también esquina). El comentario de `metrics.py` decía que
el oficial usaba 26, y estaba mal; ya está corregido.

En la práctica la diferencia casi no pesa. El Dice sale idéntico. En las redes, el FPV y el
FNV difieren en 3 a 7 de 49 estudios y nunca en más de 0,62 mL; en el sistema final, el FPV
es 9,50 mL con los dos. Solo en el umbral clásico, que deja cientos de islas, la diferencia
llega a 36 mL en un estudio (835,1 contra 832,5 mL de promedio). Ninguna conclusión cambia.

## 4. La clásica con exclusión de órganos

La referencia clásica de todas las tablas es umbral SUV 2,5, apertura de radio 1 y mínimo de
0,5 mL. La definición prometía además apagar los órganos de captación fisiológica, y no lo
había hecho: las reglas a mano del principio borraban lesiones reales. Ahora lo corrí con los
órganos de TotalSegmentator, usando los 12 grupos de `ORGANOS_FISIOLOGICOS` (lista fijada el
24 de septiembre, antes de abrir la prueba). Una isla se apaga si más de la mitad de su volumen
cae en esos órganos.

| | Dice⁺ | FPV (mL) | FNV (mL) |
|---|---|---|---|
| Clásica, validación | 0,180 | 1 191,9 | 5,6 |
| Clásica + órganos, validación | 0,366 | 108,7 | 18,0 |
| Clásica, prueba | 0,182 | 832,5 | 2,1 |
| Clásica + órganos, prueba | 0,379 | 94,8 | 28,6 |
| Sistema final, prueba | 0,727 | 9,5 | 3,95 |

Excluir órganos duplica el Dice y baja el falso positivo nueve veces, como esperaba. Pero el
falso negativo sube de 2 a 29 mL, porque también apaga lesiones reales que caen dentro de un
órgano: metástasis hepáticas y ganglios del mediastino que el mapa asigna a vasos o corazón.
Y aun así deja diez veces el falso positivo del sistema final. El argumento central del
proyecto se sostiene: saber dónde están los órganos ayuda, pero la red aprende algo más fino
que una lista de órganos que apagar.
