# Auditoría antes de las semillas: qué resiste y qué no

*Rama `extendido`, 2026-09-17. Revisión línea por línea de `train.py`, `data.py`,
`models.py`, `infer.py`, `metrics.py` y `preprocess.py`, antes de gastar ocho días de cómputo.*

## 1. Errores y riesgos encontrados

| # | Hallazgo | Gravedad | Qué se hace |
|---|---|---|---|
| 1 | **Falta el control de capacidad.** B supera a A, pero B tiene 24,0 M de parámetros y A 12,9 M. Hoy no se puede distinguir "el codificador dual aporta" de "más red aporta". El brazo `A+` (fusión temprana con canales ×1,375 = 24,3 M, los parámetros de B) existe en el registro de modelos y **nunca se entrenó**. | **Alta** — es la primera pregunta de cualquier revisor | Entra en el script 27 como etapa 2 |
| 2 | **La lesión anotada en la zona borrada entra al entrenamiento.** El defacing deja SUV = 0 en cabeza y cuello, pero la anotación se hizo sobre la imagen original. Medido en 40 estudios: **6 % de la lesión anotada está en zona sin imagen**, en 9 de 40 estudios. `sample_patch` centra parches ahí con probabilidad 0,7, y la pérdida le exige a la red predecir "tumor" donde ni PET ni CT tienen señal. | Media — enseña ruido, acotado al 6 % | **No se toca ahora**: cambiarlo rompería la comparabilidad con las tres corridas largas hechas. Queda como corrección para la siguiente generación (enmascarar SUV = 0 en muestreo y pérdida). Se declara como limitación |
| 3 | **La atención cruzada no puede contribuir por diseño.** `fused = q + γ·out` va a `fuse`, que es una conv 1×1×1 seguida de InstanceNorm sin afín. Si la salida de la atención es espacialmente constante (lo que ocurre cuando el softmax se aplana y promedia todo el CT), la InstanceNorm la elimina exactamente. Con γ = 0,992 y diferencia 0,000 al apagarla, es lo que pasó. | Media — es un error de cableado del bloque C, no del código | El resultado sobre C es válido *para C tal como se cableó*. Un "C bien cableado" (atención después de la normalización, o sin InstanceNorm en `fuse`) es una hipótesis nueva, fuera de estas corridas |
| 4 | **Las métricas excluyen la zona borrada; las del reto no.** `exclude_blank=True` por defecto en la evaluación final. Hace nuestras cifras algo más favorables (menos FNV) que la métrica cruda del reto. | Media para la comparación externa | El script 27 evalúa **ambas** (`_ultimo` y `_ultimo_crudo`) para cada corrida |
| 5 | **Sin aumento en tiempo de inferencia (TTA).** nnU-Net promedia la predicción sobre los espejados. Es una mejora casi gratis que no usamos. | Baja | Pendiente; no altera las comparaciones internas |
| 6 | **Fuga entre particiones** | — | **Verificada: no hay.** Mismo paciente nunca en dos grupos; 49 de prueba y 26 de validación intactos tras la ampliación |
| 7 | **Validación rápida con los 12 primeros estudios en orden alfabético** | — | No es aleatoria pero es fija e idéntica en todas las corridas. Y ya no decide nada: con 100 000 iteraciones `mejor` ≈ `ultimo` |
| 8 | **Semilla y determinismo** | — | numpy, torch y el muestreo de parches fijados; el DataLoader va con `shuffle=False` porque el dataset ya es aleatorio internamente. Correcto |

**Ninguno de los ocho invalida los resultados obtenidos.** El 1 limita qué se puede afirmar sobre B hasta que corra A+. El 2 y el 4 son limitaciones a declarar.

## 2. Parámetros de entrenamiento, uno por uno, contra nnU-Net

| parámetro | este proyecto | nnU-Net (default) | veredicto |
|---|---|---|---|
| iteraciones | 25 000 → **100 000** | 250 000 | La causa del resultado del paso 1. Seguimos a 40 % del de nnU-Net; el Mac no da para más sin días de cómputo |
| lote | 2 | 2 | igual |
| parche | 96³ a 3 mm (288 mm) | ~128³ a ~2 mm (~256 mm) | contexto físico parecido; menos detalle |
| resolución | 3 mm iso | ~2 mm iso | declarado por cómputo; explica parte del 52 % de lesiones chicas no detectadas |
| optimizador | AdamW, lr 3e-4, wd 1e-5 | SGD momentum 0,99, lr 1e-2, wd 3e-5 | elección válida y común (MONAI); nnU-Net argumenta que SGD generaliza algo mejor. Diferencia declarable |
| programa de lr | poly, potencia 0,9, hasta 0 | poly, potencia 0,9, hasta 0 | igual |
| recorte de gradiente | norma 12 | norma 12 | igual |
| pérdida | Dice + CE, sin fondo en el Dice | Dice + CE, con supervisión profunda | nnU-Net añade pérdidas en niveles intermedios del decodificador; nosotros no |
| normalización | instancia | instancia | igual |
| sesgo de parche con lesión | 0,7 (efectivo 0,35 con 825 estudios) | 0,33 | equivalente en el montaje actual |
| aumento de datos | espejado en 2 ejes | rotación, escala, ruido, desenfoque, brillo, contraste, baja resolución, gamma, espejado | **la mayor diferencia que queda** después del presupuesto |
| ensamble | 1 modelo | 5 pliegues | pendiente (paso 2 del plan) |
| TTA | no | espejado | pendiente |
| postproceso | no | eliminación de componentes si mejora en CV | pendiente |
| selección de checkpoint | `ultimo.pt` | `checkpoint_final` (y `best` como alternativa) | igual en espíritu |

Cómo defenderlo en una frase: **todo lo que es igual, es igual por diseño; todo lo que es
distinto está declarado y ordenado por cuánto explica.** El presupuesto de entrenamiento
explicaba lo más grande y ya se corrigió; el aumento de datos y el ensamble son lo que sigue.

## 3. Comparación con autoPET: qué es comparable y qué no

| | autoPET 2022 (ganador) | nnU-Net "sin modificar" [4] | este trabajo (B, 100k) |
|---|---|---|---|
| Dice | 0,623 | 0,690 | **0,714** |
| FPV | 2,84 mL | 5,78 mL | 12,06 mL (mediana **2,38**) |
| FNV | 0,54 mL | 6,27 mL | 3,78 mL |
| conjunto | test oculto, 200 estudios, multicéntrico parcial | partición interna propia | **26 de validación**, un solo centro |
| resolución | grilla del PET (2,04 × 2,04 × 3 mm) | 2 mm | 3 mm iso |
| zona borrada | no aplica (test no anonimizado) | no aplica | excluida (versión pública *defaced*) |
| semillas | ensamble de 5 | ensamble de 5 | **1** |

**Lo honesto:**

- El Dice **no es directamente comparable**: 26 estudios contra 200, un centro contra varios,
  y una validación que sirvió para decisiones de diseño (aunque no para elegir checkpoint).
  Lo que sí se puede decir es que el orden de magnitud es el de los trabajos publicados, y que
  el conjunto de prueba de 49 estudios —**todavía cerrado**— es el que dará la cifra citable.
- El FPV **medio** está a 2× de nnU-Net y 4× del ganador. El FPV **mediano** (2,38 mL) está al
  nivel del ganador. La diferencia entre las dos cifras la explica la sección 4.
- Las cifras de [4] son sobre una partición interna que ese grupo definió, no sobre el test
  oficial. Es la referencia más parecida a nuestra situación, no una vara oficial.
- Falta la métrica cruda (sin excluir la zona borrada). La produce el script 27, etapa 0.

## 4. El falso positivo: dónde está, y por qué "no mejora"

Sí mejoró, y bastante. Lo que engaña es el promedio:

| corrida | FPV medio | FPV **mediano** | 3 peores estudios | % del total | media sin los 3 |
|---|---|---|---|---|---|
| A · 176 · 25k | 21,82 | 11,65 | 262 mL | 46 % | 13,26 |
| A · 825 · 100k | 15,76 | 5,79 | 244 mL | 60 % | 7,19 |
| **B · 825 · 100k** | 12,06 | **2,38** | 200 mL | **64 %** | **4,94** |
| C · 825 · 100k | 13,48 | 4,50 | 210 mL | 60 % | 6,09 |

El promedio bajó un 45 %. **La mediana bajó cinco veces**, de 11,7 a 2,4 mL. Y tres
estudios de 26 concentran el 64 % del volumen falso; sin ellos, B queda en 4,94 mL, por
debajo de nnU-Net.

El peor de los tres es un caso que merece nombre propio: **PETCT_f6295a93a6**, mujer de 81
años, etiquetada como control negativo. Las cuatro arquitecturas, en todos los presupuestos,
marcan en ella entre 124 y 183 mL, y siempre con **SUVmáx 20,7**. Con el mapa de órganos: **73
mL en pulmón**, con SUV mediano 2,9 y ese máximo de 20,7. El pulmón sano está en SUV 0,5–1.

Eso no es un error de la red ni captación fisiológica. Es un foco pulmonar hipermetabólico
intenso en una paciente sin diagnóstico oncológico: neumonía, tuberculosis, neumonitis,
sarcoidosis — o un tumor que no está en la anotación. El dataset anota solo lesión maligna
FDG-ávida, así que **la red tiene razón en que hay algo y la anotación tiene razón en que no
es tumor**. Es exactamente la limitación que el informe declara desde el primer párrafo: el
trazador marca consumo de glucosa, no tumor.

Este estudio solo aporta **5 mL al promedio de FPV de 26**. Es el caso para mostrar en la
defensa, y el argumento de por qué el FPV medio, con 26 estudios, no es una métrica estable.

## 5. Lo que corre ahora

`scripts/27_semillas_largo.sh`, reanudable, unos 8 días:

- **Etapa 0**: las evaluaciones que faltan de A, B y C largos — la métrica cruda del reto y
  las máscaras para el análisis por órgano; para C, la ablación ya está.
- **Etapa 1**: segunda semilla de A, B y C.
- **Etapa 2**: **A+**, el control de capacidad. Si A+ ≈ B, la ventaja era el tamaño; si
  A+ < B, era el codificador dual.
- **Etapa 3**: tercera semilla de A, B y C.

El orden está pensado para que un corte a mitad de camino deje siempre comparaciones
completas: primero las segundas semillas de los tres, después el control, después las terceras.
