# Resultados en validación: los cuatro brazos

*2026-09-12. Doce corridas de entrenamiento (cuatro arquitecturas × tres semillas), cada una
evaluada sobre los 26 estudios de validación con los dos checkpoints. El conjunto de prueba
sigue cerrado.*

Este documento es el corte de resultados del proyecto. Todo lo que viene después —si viene—
es exploración y está fuera de esta línea.

## Los brazos

| | qué es | parámetros |
|---|---|---|
| **A** | fusión temprana: SUV y CT como dos canales de una U-Net 3D | 12,9 M |
| **B** | fusión intermedia: dos codificadores, concatenación en el cuello de botella | 24,0 M |
| **C** | fusión intermedia: dos codificadores, atención cruzada PET→CT | 24,4 M |
| **E** | A más un tercer canal: SUV referido al hígado del propio paciente | 12,9 M |
| clásica | umbral SUV ≥ 2,5, apertura morfológica, exclusión anatómica | — |

Mismo preprocesamiento, mismo muestreo de parches, mismas 25 000 iteraciones, mismo lote,
mismo optimizador, mismas semillas. **La única variable que cambia es la arquitectura.**

## Resultados

**Criterio `mejor.pt`** (el del protocolo congelado: el checkpoint con mejor Dice en la
validación rápida de 12 estudios). Media ± desviación entre las tres semillas:

| brazo | Dice⁺ | FPV mL | FNV mL |
|---|---|---|---|
| A | 0,621 ± 0,016 | 20,93 ± 2,50 | 6,02 |
| B | 0,612 ± 0,014 | 22,78 ± 3,08 | 5,36 |
| C | 0,612 ± 0,008 | 23,18 ± 6,65 | 5,93 |
| E | 0,640 ± 0,022 | 21,97 ± 9,77 | 7,27 |
| **clásica** | **0,180** | **1 191,87** | **5,59** |

**Criterio `ultimo.pt`** (las 25 000 iteraciones completas, sin elegir):

| brazo | Dice⁺ | FPV mL | FNV mL |
|---|---|---|---|
| A | 0,615 ± 0,020 | 21,74 ± 0,49 | 5,85 |
| B | 0,607 ± 0,002 | 22,11 ± 2,79 | 4,44 |
| C | 0,610 ± 0,007 | 21,50 ± 1,76 | 4,45 |
| E | 0,638 ± 0,006 | 23,63 ± 2,84 | 5,70 |

## Las cuatro conclusiones

**1. Las cuatro fusiones empatan.** Ninguna diferencia entre arquitecturas resiste el
pareado por estudio: todos los intervalos de confianza del 95 % cruzan el cero y ninguna p
baja de 0,23. Con 176 estudios de entrenamiento y este presupuesto, **cómo se fusionan el
PET y el CT no cambia el resultado.**

**2. Todas superan al método clásico por un margen enorme.** El umbral SUV ≥ 2,5 deja
1 192 mL de falso positivo por estudio; las redes, alrededor de 21. Es un factor de **57
veces**, con un Dice tres veces y media mayor. El aporte del aprendizaje profundo en esta
tarea no está en la arquitectura, está en haber dejado de usar un umbral.

**3. Dos mecanismos propuestos no funcionaron, y fallaron de maneras distintas.**
- La **atención cruzada** de C está *muerta*: forzar su factor de mezcla a cero no cambia
  un solo vóxel de la predicción. La normalización de instancia cancela las señales
  espacialmente constantes que la atención intentaba introducir.
- El **canal de referencia interna** de E está *vivo*: sustituir el hígado del paciente por
  una constante poblacional cambia 23 de 26 predicciones. Pero su efecto neto es de 1,4 mL
  de FPV, que se pierde en el ruido entre semillas.

Detalle en `docs/ANALISIS_MODELO_E.md`.

**4. El criterio de selección del checkpoint mete más ruido que la semilla.** La desviación
del FPV entre semillas, al usar el checkpoint final en vez del "mejor", baja 5,1× en A,
3,8× en C y 3,4× en E. Elegir el máximo de Dice en una curva medida sobre doce estudios
arrastra consigo lo que haya acompañado a ese máximo, y el FPV queda decidido por azar: el
criterio optimiza una métrica y deja las otras dos sueltas. Es el equivalente a elegir el
punto de corte de un marcador en la misma muestra donde se lo descubrió.

**Este cuarto punto no estaba en el plan y es el hallazgo más sólido de la fase**: está
medido sobre doce corridas independientes y afecta a los cuatro brazos por igual.

## Archivos

| | |
|---|---|
| `results/corridas.csv` | una fila por corrida: semilla, iteraciones, dónde cayó el mejor checkpoint, minutos |
| `results/comparacion_modelos.csv` | media ± sd por modelo |
| `results/modelo_<X>[_s<n>][_ultimo]_val.csv` | una fila por estudio, 24 tablas |
| `results/modelo_C*_sin_atencion_val.csv` | ablación de la atención de C |
| `results/modelo_E_sin_ref_val.csv` | ablación del canal de E |
| `results/referencia_clasica.csv` | el umbral SUV 2,5 |
| `results/fp_por_organo_val*.csv` | reparto del falso positivo por órgano |
| `docs/figuras/curvas_entrenamiento.png` | pérdida y Dice contra iteración, las doce corridas |

## Lo que falta

Abrir el conjunto de prueba, **una sola vez**, con los cuatro brazos a la vez, cuando no
quede ninguna decisión pendiente. 49 estudios que ningún modelo ha visto.
