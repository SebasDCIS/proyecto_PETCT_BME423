# Ruta del proyecto: dónde estamos y qué sigue

*Actualizado el 2026-09-11. Este documento se reescribe cada vez que cambia el plan.*

El proyecto tiene dos mitades. La primera está **cerrada**. La segunda está **en curso**, y es
la que puede tocar cualquier cosa hoy.

---

## PARTE 1 — La comparación de fusiones · CERRADA

Nueve entrenamientos (A, B, C × semillas 423, 2, 3), ~9 horas cada uno. Resultado:

- Las tres fusiones empatan: A 0,621 ± 0,016 · B 0,612 ± 0,014 · C 0,612 ± 0,008.
- La atención cruzada de C es **inerte**: apagarla no cambia ni un vóxel.
- Todas contra el umbral clásico SUV 2,5 (Dice 0,180, FPV 1.192 mL): la fusión reduce el
  falso positivo **57 veces**.

**Esto no se vuelve a tocar.** Está documentado en `PROTOCOLO_CONGELADO.md`,
`RESUMEN_NARRATIVO.md`, `BITACORA.md` y `results/`. Lo único que le falta a la Parte 1 es
abrirse contra el conjunto de prueba, y eso se hace al final, una sola vez, junto con todo
lo demás.

---

## PARTE 2 — ¿Sirve decirle a la red en qué órgano está? · EN CURSO

**La pregunta:** todo lo que el proyecto gana viene de distinguir captación fisiológica
normal de captación tumoral. Hoy la red tiene que deducir el órgano mirando el CT, con solo
176 estudios. ¿Y si se lo damos ya masticado?

Había dos formas de dárselo. **El 2026-09-11 quedó elegida la segunda**, con la evidencia de
los pasos 2 a 4:

- **E1 — canal de órgano.** Un canal extra que dice "esto es hígado". Descartado: el órgano es
  deducible del CT dentro del parche, y se midió que la normalización poblacional por órgano no
  cambia el AUC dentro de un mismo órgano.
- **E — canal de SUV referido al hígado propio.** Un canal extra que dice "este brillo es 3,6
  veces el hígado de este paciente". Es la lógica de la escala de Deauville. **Elegido**,
  porque es información que un parche de 288 mm no puede contener.

Y la regla que nos dimos, que funcionó: **medir antes de entrenar.** Los pasos 1 a 4 no
gastaron ni una noche de GPU y decidieron por nosotros.

---

### ~~Paso 1 — Mapas de órganos del entrenamiento~~ · ✅ hecho

202 de 202 (176 de entrenamiento + 26 de validación), en unas 3 horas.

### ~~Paso 2 — Construir el atlas de normalidad~~ · ✅ hecho

Dos tablas de "cuánto capta normalmente cada órgano": una con los 35 controles sin lesión,
otra con los 176 completos excluyendo los vóxeles anotados.

```
python scripts/17_atlas_normalidad.py --subconjunto controles
python scripts/17_atlas_normalidad.py --subconjunto train
```

- **Cuesta:** minutos · **Quién:** tú lo lanzas, me pegás la salida

### ~~Paso 3 — Comparar los dos atlas~~ · ✅ hecho

```
python scripts/17_atlas_normalidad.py --comparar
```

Si coinciden, la contaminación de la cohorte oncológica es despreciable y usamos el de 176
por tener cinco veces más pacientes. Si no coinciden, el desacuerdo mide cuánta captación
anómala no anotada hay. **Las dos salidas son información, ninguna es un fracaso.**

- **Cuesta:** segundos

### ~~Paso 4 — La prueba decisiva~~ · ✅ hecho

```
python scripts/18_poder_separacion.py --atlas controles
```

Toma los hallazgos que las nueve corridas ya produjeron sobre validación, los marca como
verdaderos o falsos con la definición de autoPET, y compara tres formas de puntuarlos:
SUVmáx crudo, SUVmáx / p95 del órgano, y z robusto del órgano.

- **Cuesta:** minutos

### ~~🔀 PUNTO DE DECISIÓN~~ · resuelto el 2026-09-11: **se entrena E**

Resultados en `docs/ANALISIS_ATLAS.md`. En una línea: la referencia por órgano gana +0,030 de
AUC (0,813 → 0,844) y gana en las nueve corridas sin excepción; y el desglose por órgano mostró
que **toda esa ganancia viene de la referencia interna del paciente**, no de la tabla
poblacional, porque dividir por una constante del órgano es una transformación monótona que no
cambia el orden. Sumado a que un parche de 288 mm no puede ver el hígado desde la pelvis, es
información que la red no tiene forma de deducir.

De paso quedó cerrada la pregunta de si bajar más estudios: **no**. Quintuplicar la muestra
mueve la referencia menos del 3 % en once de quince órganos.

### 📍 Paso 5 — Entrenar el modelo E · **AQUÍ ESTAMOS**

**Modelo E** = la arquitectura de A sin ningún cambio, con un tercer canal de entrada: el SUV
de cada vóxel dividido por el SUV hepático de ese paciente, con tope en 8 veces. Mismo tamaño
(12,9 M parámetros), mismo presupuesto de entrenamiento. **La única variable que se mueve es la
entrada.**

Antes de entrenar, una vez:

```
python scripts/19_referencias_internas.py
```

Después, las tres corridas (una por noche, el Mac enchufado):

```
caffeinate -i python scripts/07_entrenar.py --modelo E --semilla 423 --salida runs/E
caffeinate -i python scripts/07_entrenar.py --modelo E --semilla 2   --salida runs/E_s2
caffeinate -i python scripts/07_entrenar.py --modelo E --semilla 3   --salida runs/E_s3
```

- **Cuesta:** ~9 h cada una · **Quién:** tu Mac, enchufado
- **Ablación obligatoria:** `--sin-referencia` en la evaluación sustituye la referencia de cada
  paciente por la constante poblacional. El canal sigue existiendo, pero deja de contener
  información individual. Si la predicción no cambia, el canal está inerte, igual que le pasó a
  la atención cruzada de C.

### Paso 6 — Evaluar y repartir el error por órgano

Las mismas métricas de siempre sobre validación, más la tabla de falsos positivos por órgano,
para ver si el canal nuevo secó específicamente hígado, riñón y vejiga.

### Paso 7 — FROC: convertir esto en un detector

Curva de detección por lesión (falsos positivos por paciente contra fracción de lesiones
encontradas), que es el estándar de los sistemas de detección asistida. Necesita una
confianza por hallazgo: la da el paso 4, o una re-inferencia guardando probabilidades (~2 h,
sin entrenar).

### Paso 8 — Abrir el conjunto de prueba · UNA SOLA VEZ

49 estudios que ningún modelo ha visto. Se abre con **todos** los brazos a la vez (A, B, C y
E si existe), al final, cuando ya no queda ninguna decisión por tomar. ~2 h de inferencia.

**Regla de oro: si se abre antes, deja de ser una prueba.**

### Paso 9 — Informe para el profesor Veloz

Ensamblaje, no redacción desde cero: el material ya está escrito y verificado. Falta la pauta
del ramo (extensión, formato, secciones, rúbrica) para armar el esqueleto.

---

## Quién hace qué

| | Sebastián (Terminal del Mac) | Claude |
|---|---|---|
| Pasos 1–4 | lanzar los comandos, pegar la salida | escribir los scripts, leer los resultados, decidir |
| Decisión | elegir con la evidencia a la vista | proponer con los números |
| Paso 5 | dejar el Mac entrenando de noche, enchufado | preparar el código del brazo nuevo |
| Pasos 6–8 | lanzar, pegar salida | analizar, escribir tablas y figuras |
| Paso 9 | conseguir la pauta, revisar y firmar | redactar |
| Siempre | `git push` (GitHub va atrasado) | commits locales, bitácora, glosario, Notion |

---

## Lo que hay que hacer AHORA MISMO

1. `python scripts/19_referencias_internas.py` — un minuto, y hay que leer lo que imprime:
   la diferencia entre calcular la referencia con y sin la anotación es la comprobación de que
   el canal no tiene fuga.
2. Lanzar la primera corrida de E esta noche, con el Mac enchufado.
3. Si querés adelantar el paso 9: buscá la pauta del informe y pasámela.
