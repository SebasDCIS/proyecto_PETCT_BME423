# Traspaso: estado del proyecto y ramas candidatas (2026-09-07)

Documento puente entre dos hilos de trabajo. **Hilo 1 (este)**: cerrar el protocolo original
(A, B, C × 3 semillas, Paso 5, test una sola vez). **Hilo 2 (chat nuevo)**: ramas adicionales
hacia el informe de diciembre. Quien tome el hilo 2 debe leer esto, `docs/PROTOCOLO_CONGELADO.md`
y las últimas entradas de `BITACORA.md` (2026-09-06 y 2026-09-07).

## Estado en una tabla

| Corrida | Estado | mejor.pt (it) | Dice val 26 | FPV | FNV |
|---|---|---|---|---|---|
| A, A_s2, A_s3 | cerradas | 23k / 24k / 22k | **0,621 ± 0,016** | 20,9 ± 2,5 | 6,0 ± 0,4 |
| B, B_s2, B_s3 | cerradas | 13k / 19k / 22k | **0,612 ± 0,014** | 22,8 ± 3,1 | 5,4 ± 0,8 |
| C piloto (gamma 0) | descartada | 23k | 0,624 | 16,0 | 4,9 |
| C (gamma 1) | cerrada | 9k (pico aislado) | 0,603 | 16,1 | 7,8 |
| C_s2, C_s3 | en curso / cola | | | | |
| Referencia clásica (val) | | | 0,180 | 1 192 | 5,6 |

Test (49) sigue cerrado; se abre una sola vez al final con los nueve `mejor.pt`.

## Hallazgos que condicionan cualquier rama nueva

1. **Defacing**: la SEG conserva lesiones dentro de la caja borrada (4,6 % del volumen anotado).
   Regla de evaluación: excluir vóxeles con SUV = 0 (`evaluate_study(exclude_blank=True)`).
2. **Separar los embudos no cambia nada** (B ≈ A dentro del ruido de semillas).
3. **La atención cruzada aditiva en el cuello es inerte** en esta U-Net: dos ablaciones
   (`scripts/09 --sin-atencion`) idénticas vóxel a vóxel, con gamma inicial 0 (quedó en 0,0125)
   y con gamma inicial 1 (quedó en 1,00002). Mecanismo medido: la atención es casi uniforme
   sobre las 216 posiciones del cuello → su salida es 99 % constante entre posiciones →
   la norma de instancia (en `fuse` y en toda la red) resta la media espacial y la cancela.
   Un contexto global solo puede entrar como patrón espacial o modulando la norma.
4. **El criterio de selección de checkpoint es ruidoso** (12 estudios fijos, orden alfabético:
   3 pulmón, 3 linfoma, 4 melanoma, 2 negativos; incluye uno con Dice cruda 0 fija). En C eligió
   la iteración 9 000. Idéntico en las nueve corridas; no se cambia para no romper la
   comparabilidad. Mitigación barata: evaluar también `ultimo.pt` en las nueve.
5. Casos que todos fallan igual: `f6295a93a6` (negativo, 104–110 mL de FP en A y B; 42 en C),
   `94962fe878` (68–86 mL FP), `e03b96666f` (64–89 mL FNV, mayoría en zona borrada).

## Ramas candidatas (para el hilo 2)

- **D · atención que la norma no cancela.** Misma red que C, pero el vector de contexto de la
  atención modula los parámetros afines de la norma de instancia del cuello (FiLM/AdaIN:
  escala y desplazamiento por canal) y la parte posicional se sigue sumando. Pilotar una
  noche → ablación → si cambia el resultado, tres semillas. Código base: `CrossAttentionFusion`
  y `DualEncoderUNet` en `src/petct/models.py`; registro en `_REGISTRY`.
- **E · anatomía explícita.** A con un tercer canal: el mapa de órganos de TotalSegmentator
  (`data/processed_organos/<base>.npz`, campo `groups`, 17 grupos; hace falta correr
  `scripts/11` sobre los 251). Sin fuga: se calcula solo del CT. Pregunta: si la fusión
  aprendida no usa el contexto anatómico, ¿qué pasa cuando se lo damos hecho?
- **Ensamble de semillas.** Promediar probabilidades (softmax) de las tres semillas por modelo
  antes del argmax; mapa de desacuerdo entre semillas como incertidumbre. Solo inferencia.
- **Detección por lesión y tamaño.** Sensibilidad por lesión (componentes 26-conexas) en
  función del volumen, por modelo y diagnóstico. Solo código sobre las máscaras guardadas.
- **Bootstrap** (1 000 remuestreos sobre los 26 / 49) para intervalos en todas las tablas.
- **A+** (control de capacidad, 24,3 M) solo si sobra tiempo; B ya sugiere que no hace falta.
- Propuesta propia de Sebastián: pendiente de escuchar en el hilo 2.

## Reglas que no cambian en ninguna rama

Partición y manifiesto congelados (commit `28a5ddf`); preprocesamiento fijo; mismo bucle de
entrenamiento (`configs/default.yaml`, 25 000 it, lote 2, parche 96³, lr 3e-4, fp32 en mps);
tres semillas por brazo (423, 2, 3); regla de exclusión de la zona borrada; ablación
obligatoria para cualquier módulo nuevo; test una sola vez, al final, con todos los brazos a
la vez. Corridas exploratorias van en `runs/*_piloto*` (los scripts 10/12/13 las ignoran).

## Cómo se trabaja (recordatorio operativo)

Mac M5 (mps), una corrida por noche (~5 h A, ~6 h B/C). Sebastián corre en la Terminal lo que
lleve torch/nbconvert/TotalSegmentator y pega la salida; la VM de Cowork corre el resto
(scripts 05, 10, 12, 13, 14). Repo local en disco físico, nunca en nube; nada pesado a git.
Documentación viva: `BITACORA.md`, `docs/GLOSARIO.md`, `docs/PROTOCOLO_CONGELADO.md`,
`notas_personales/CUADERNO_DE_DEFENSA.md` (fuera de git, secciones 0–21), Notion (Bitácora,
Notas de estudio, Glosarios), curso visual "Embudo y trompeta" (artifact).
