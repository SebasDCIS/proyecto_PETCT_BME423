# Ruta del proyecto: dónde estamos y qué sigue

*Actualizado el 2026-09-10, 16:02. Este documento se reescribe cada vez que cambia el plan.*

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

Hay dos formas de dárselo, y todavía no sabemos cuál (ni si alguna sirve):

- **E1 — canal de órgano.** Un canal extra que dice "esto es hígado". Precedente publicado
  (Frontiers 2026: +16 % en detección de linfoma, con reducción de falsos positivos
  concentrada en cerebro, tiroides y corazón).
- **E2 — canal de SUV relativo.** Un canal extra que dice "este brillo es 3,6 veces lo normal
  de este órgano". Es la escala de Deauville automatizada y generalizada a 17 órganos. Es
  el aporte propio, sin precedente directo.

Y la regla que nos dimos: **medir antes de entrenar.** Los pasos 1 a 4 no gastan ni una noche
de GPU y nos dicen si vale la pena seguir.

---

### 📍 Paso 1 — Mapas de órganos del entrenamiento · **AQUÍ ESTAMOS**

TotalSegmentator sobre los 176 estudios de entrenamiento (los 26 de validación ya estaban).

- **Estado:** 40 de 202 · va a ~40 s por estudio · faltan ~1 h 45 min
- **Comando:** `nohup caffeinate -i python scripts/11_organos_totalsegmentator.py --particion train >> logs/organos_train.log 2>&1 &`
- **Vigilar:** `ls data/processed_organos/*.npz | wc -l` · listo cuando llegue a **202**
- **Quién:** tu Mac, solo. No hay nada que hacer mientras tanto.

### Paso 2 — Construir el atlas de normalidad

Dos tablas de "cuánto capta normalmente cada órgano": una con los 35 controles sin lesión,
otra con los 176 completos excluyendo los vóxeles anotados.

```
python scripts/17_atlas_normalidad.py --subconjunto controles
python scripts/17_atlas_normalidad.py --subconjunto train
```

- **Cuesta:** minutos · **Quién:** tú lo lanzas, me pegás la salida

### Paso 3 — Comparar los dos atlas

```
python scripts/17_atlas_normalidad.py --comparar
```

Si coinciden, la contaminación de la cohorte oncológica es despreciable y usamos el de 176
por tener cinco veces más pacientes. Si no coinciden, el desacuerdo mide cuánta captación
anómala no anotada hay. **Las dos salidas son información, ninguna es un fracaso.**

- **Cuesta:** segundos

### Paso 4 — La prueba decisiva: ¿separa o no separa?

```
python scripts/18_poder_separacion.py --atlas controles
```

Toma los hallazgos que las nueve corridas ya produjeron sobre validación, los marca como
verdaderos o falsos con la definición de autoPET, y compara tres formas de puntuarlos:
SUVmáx crudo, SUVmáx / p95 del órgano, y z robusto del órgano.

- **Cuesta:** minutos

### 🔀 PUNTO DE DECISIÓN

Según el AUC del paso 4:

| Si… | Entonces |
|---|---|
| El SUV relativo gana claramente al crudo (+0,03 o más) | **Entrenamos E2**, 3 semillas, 3 noches |
| Empatan, pero el mapa de órganos se ve sólido | **Entrenamos E1**, 3 semillas, 3 noches |
| Ninguno aporta | **No entrenamos nada.** Es un resultado, y refuerza la tesis: el techo está en la anotación, no en el modelo |

En cualquiera de los tres casos, el análisis de los pasos 2 a 4 **entra al informe**. No se
tira nada.

### Paso 5 — Entrenar el brazo elegido *(solo si el paso 4 lo justifica)*

Tres corridas, ~9 h cada una, arquitectura A (la mejor y la más barata), cambiando **solo la
entrada**. Ablación obligatoria: poner el canal nuevo en cero y volver a medir.

- **Cuesta:** 3 noches · **Quién:** tu Mac, enchufado

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

**Nada.** Esperar a que el contador llegue a 202. Mientras tanto, si querés adelantar: buscá
la pauta del informe y pasámela.
