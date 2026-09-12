# Proyecto extendido: de un mini-proyecto a algo que compita

*Rama `extendido`, abierta el 2026-09-12 desde el tag `resultados-validacion-4-brazos`.*

## Qué es esta rama y qué no es

`main` contiene el mini-proyecto de BME423: cuatro estrategias de fusión comparadas con tres
semillas cada una, dos hipótesis descartadas con ablaciones limpias, y el hallazgo sobre la
selección de checkpoint. **Está terminado y se entrega en diciembre. No se toca desde acá.**

Esta rama es el proyecto siguiente: llevar el mismo montaje a un nivel comparable con lo
publicado, con la mira puesta en autoPET VI (previsible alrededor de abril de 2027).

## El diagnóstico del que sale todo

| | Dice⁺ | FPV | FNV |
|---|---|---|---|
| ganador autoPET 2022 | 0,623 | **2,84 mL** | 0,54 mL |
| nnU-Net sin modificar | 0,690 | 5,78 mL | 6,27 mL |
| modelo A de `main` | 0,621 | **20,93 mL** | 6,02 mL |

**El Dice ya está.** La brecha es el falso positivo: siete veces peor que el ganador. Y hay un
segundo problema que el Dice escondía y que la contabilidad por lesión destapó: **la red detecta
solo el 52 % de las lesiones anotadas** (133 de 256 en validación). Las que se pierden son
chicas.

Cuatro arquitecturas ya empataron. El problema no es cómo se fusionan PET y CT.

## Los pasos, en orden de ejecución

### Paso 1 — Ampliar el conjunto de entrenamiento

Hoy se entrena con 176 estudios de los 1 014 que el dataset tiene. Es la diferencia más grande
respecto de cualquier publicación.

**Restricción dura:** los 49 estudios de prueba y los 26 de validación siguen siendo
**exactamente los mismos**. Los estudios nuevos entran solo a entrenamiento. Si la partición
cambia, se pierde la prueba limpia que se viene cuidando desde el principio.

- Espacio: 12 MB por estudio preprocesado; los 1 014 completos son ~12 GB. El cuello es la
  descarga (~280 GB de NIfTI), que se procesa por lotes borrando el NIfTI después.
- Éxito: Dice⁺ por encima de 0,66 con el mismo modelo A y el mismo presupuesto.

### Paso 2 — Validación cruzada de cinco pliegues y ensamble

Cinco particiones distintas del conjunto de entrenamiento, un modelo por pliegue, y el promedio
de las probabilidades como predicción. Es lo que hacen todos los ganadores de autoPET.

Ataca el falso positivo por construcción: las lesiones verdaderas las encuentran los cinco
modelos y sobreviven al promedio; las marcas espurias de cada modelo son propias y se diluyen.
De paso elimina el problema del criterio de checkpoint documentado en `main`, porque el
resultado deja de depender de una corrida.

- Costo: cinco corridas.
- Éxito: FPV por debajo de 12 mL sin perder Dice.

### Paso 3 — Cómo se presentan los datos

Dos cambios, ninguno toca la arquitectura:

- `prob_parche_con_lesion` de 0,7 a 0,33 (nnU-Net usa un tercio; siete de cada diez parches con
  tumor le enseñan a la red que el tumor es frecuente).
- Aumento de datos completo: rotaciones, escalado, ruido gaussiano, gamma, simulación de baja
  resolución. Hoy solo hay volteos en dos ejes.

- Costo: una noche por variante.
- Éxito: cualquier caída de FPV sin pérdida de Dice. **Es el paso con más valor científico**: si
  funciona, la conclusión pasa a ser que la presentación de los datos pesa más que la fusión.

### Paso 4 — Cascada: detectar y después confirmar

Dos etapas. Una red de detección con umbral bajo y sensibilidad alta, que no deje escapar nada.
Y un clasificador chico que mira **un candidato a la vez** con su contexto y decide si va.

Por qué puede funcionar donde falló el modelo E: la segunda red resuelve un problema de
clasificación sobre un candidato, no de segmentación sobre un cubo donde el tumor es el 0,5 % de
los vóxeles. Y ahí entran de forma natural, como características de entrada, las cosas que ya
están construidas: el órgano de TotalSegmentator, el atlas de normalidad, y el brillo referido al
hígado del propio paciente.

Esto es lo propio del proyecto, y apunta a la métrica **DMM por instancia** que autoPET V puso en
el centro.

- Éxito: a igual número de marcas falsas por estudio, detectar más lesiones que la red sola.

### Paso 5 — Bajar a 2 mm

Ataca el 48 % de lesiones no detectadas. Caro: 3,4× más vóxeles, y para no perder contexto hay
que subir el parche a 128³. En el Mac son ~20 h por corrida; requiere GPU alquilada.

Va al final, cuando lo demás esté decidido.

## Trabajo ya hecho en esta rama

`experimentos/` contiene lo que se exploró antes de abrir la rama, movido acá para quedar
registrado sin contaminar `main`:

- `21_barrido_umbral.py` — barrido del umbral de decisión, once puntos en una sola inferencia,
  con detección por lesión para el FROC. **Escrito, no ejecutado.**
- `22_filtro_atlas.py` — rechazo de islas por percentil del órgano. **Ejecutado sobre A.**
  Resultado: baja el FPV solo un 7 %. El falso positivo no vive en islas tibias.
- `23_curva_rechazo.py` — tabla por isla y por lesión. **Ejecutado sobre A, B y C.**
  Resultado: rechazar las islas que no llegan a 2× el hígado del propio paciente **elimina el
  40 % de las marcas falsas perdiendo el 2,3 % de las lesiones detectadas**. Es la información
  del modelo E aplicada como regla de salida en vez de como canal de entrada, y ahí sí funciona.
  Los tres modelos siguen empatando cuando se los compara a igual número de marcas falsas.

## La regla de fusión

Esta rama vuelve a `main` **solo** si se cumplen las tres condiciones:

1. Los resultados superan de forma clara y medida a los de `main` (no una diferencia dentro del
   ruido entre semillas — ese error ya se cometió una vez con el modelo E).
2. La partición original está intacta: los mismos 49 estudios de prueba, los mismos 26 de
   validación.
3. El conjunto de prueba sigue sin abrirse, o se abre una sola vez con todo decidido.

Mientras tanto, `main` es lo que se entrega en diciembre y esta rama no lo afecta.
