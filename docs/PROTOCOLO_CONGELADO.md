# Protocolo congelado y auditoría de fugas (2026-09-06)

Este documento fija, en un solo lugar, qué datos y qué configuración usan las nueve corridas
del proyecto (A, B, C × semillas 423, 2, 3), y deja constancia de la revisión que hice para
descartar fugas de información (data leakage) entre entrenamiento, validación y prueba.
Lo verifiqué contra los archivos reales del Mac, no contra lo que recordaba: el manifiesto
`data/manifests/subconjunto.csv`, `configs/default.yaml`, el `resumen.json` de cada corrida
y el código de `src/petct` y `scripts/`.

## 1. Datos

| | Total | LUNG_CANCER | LYMPHOMA | MELANOMA | NEGATIVE | Lesión anotada (mL/estudio) |
|---|---|---|---|---|---|---|
| train | 176 | 47 | 47 | 47 | 35 | 173 |
| val | 26 | 7 | 7 | 7 | 5 | 161 |
| test | 49 | 13 | 13 | 13 | 10 | 200 |
| **total** | **251** | 67 | 67 | 67 | 50 | 176 |

- Colección: TCIA `FDG-PET-CT-Lesions` (autoPET), versión *defaced* pública (CC BY 4.0).
- Un estudio por paciente: 251 filas, 251 `patient_id` distintos, 251 `study_uid` distintos.
  Ningún paciente aparece en dos particiones (verificado con `groupby(patient_id).split.nunique()`).
- Sorteo estratificado por diagnóstico con semilla 423 (`datos.particion: [0.7, 0.1, 0.2]`).
  El manifiesto no cambió desde que se creó (commit `28a5ddf`, 2026-09-03;
  md5 `03d1d5c6d07bdb31095ff44d8546a874`): las nueve corridas y todas las evaluaciones usan
  exactamente la misma partición.
- Preprocesamiento idéntico para todos: 3 mm isotrópicos, CT con ventana −200/300 HU → [0, 1],
  SUV/30 con tope → [0, 1], máscara corporal y recorte a la caja del cuerpo. Todas las constantes
  son fijas (no se estima nada sobre el conjunto de datos), así que el preprocesamiento no puede
  filtrar información de validación o prueba hacia el entrenamiento.
- Zona borrada por el defacing: en evaluación se excluyen los vóxeles con SUV = 0 de la
  predicción y de la verdad (`metrics.blank_region_mask`). Es una regla de evaluación, igual
  para los tres modelos y la referencia clásica; no toca el entrenamiento.

## 2. Configuración de entrenamiento (idéntica en las nueve corridas)

Verificada en `runs/*/resumen.json` de A, A_s2, A_s3, B, B_s2, B_s3: todos los campos coinciden salvo `modelo` y `semilla`.

| Parámetro | Valor | Dónde vive |
|---|---|---|
| Iteraciones | 25 000 | `entrenamiento.iteraciones` |
| Lote | 2 parches | `entrenamiento.lote` |
| Parche | 96 × 96 × 96 vóxeles (288 mm de lado) | `preprocesamiento.parche` |
| Muestreo | 70 % de parches centrados en lesión (≈ 56 % real, porque los negativos no tienen lesión) | `preprocesamiento.prob_parche_con_lesion` |
| Aumento | solo volteos izquierda-derecha y anterior-posterior; nunca en z | `PatchDataset(augment=True)` |
| Optimizador | AdamW, lr 3·10⁻⁴, weight decay 10⁻⁵ | `entrenamiento.lr`, `entrenamiento.weight_decay` |
| Programa de lr | polinomial, potencia 0,9, hasta 0 en la iteración 25 000 | `train.poly_lr` |
| Pérdida | Dice + entropía cruzada (softmax, sin fondo en el Dice) | `DiceCELoss` |
| Recorte de gradiente | norma 12 | `train.train` |
| Precisión | fp32 (el indicador `precision_mixta` solo actúa en CUDA; en mps queda apagado) | `entrenamiento.precision_mixta` |
| Checkpoint | cada 500 iteraciones (`ultimo.pt`, escritura atómica) | `entrenamiento.checkpoint_cada` |
| Validación rápida | cada 1 000 iteraciones, ventana deslizante sobre 12 estudios fijos de val (los 12 primeros en orden alfabético de archivo), métrica cruda | `entrenamiento.validar_cada`, `max_estudios_val` |
| Elección del checkpoint | `mejor.pt` = mayor Dice en positivos de la validación rápida | `train.train` |
| Caché | los 176 estudios de entrenamiento en RAM (`cache_estudios: 256`), `workers: 0` | `TrainConfig` |
| Semilla | 423, 2, 3 (inicialización, orden de parches y volteos) | `--semilla` |
| Inferencia | ventana deslizante 96³, solape 0,5, ponderación gaussiana | `infer.predict_volume` |

Modelos: A (fusión temprana, U-Net MONAI 32-64-128-256-320, 12,9 M parámetros, 37 GFLOP por
parche); B (dos codificadores + concatenación, 24,0 M, 59 GFLOP); C (B + atención cruzada en el
cuello, 24,4 M). Las tres se entrenan con este mismo bucle sin ningún cambio.

## 3. Auditoría de fugas: qué revisé y qué encontré

**Lo que usa cada fase**

| Fase | Estudios que ve | Para qué |
|---|---|---|
| Entrenamiento (gradiente) | train, 176 | parches con aumento |
| Validación rápida (cada 1 000 it) | val, 12 fijos (3 pulmón, 3 linfoma, 4 melanoma, 2 negativos) | elegir `mejor.pt` |
| Evaluación reportada en la bitácora | val, 26 | comparar A, B y C, elegir el relato |
| Prueba | test, 49 | **una sola vez, al final, con los 9 `mejor.pt`** |

Puntos verificados, con el archivo donde está cada uno:

1. `scripts/07_entrenar.py` pasa `splits["train"]` al `PatchDataset` y `splits["val"]` solo a
   la validación rápida; `test` nunca se carga durante el entrenamiento.
2. En `train.train`, `val_subset = list(val_files)[:max_estudios_val]`: la validación rápida
   solo mide (sin gradiente, `torch.no_grad`) y solo decide qué checkpoint guardar.
3. `PatchDataset(augment=True)` solo existe para train; la validación y la evaluación usan
   `evaluate_files` sobre el volumen completo, sin aumento.
4. Ninguna estadística global: las normalizaciones son constantes (ventana HU, SUV/30), la
   máscara corporal y el recorte se calculan por estudio.
5. Referencia clásica: umbral SUV 2,5, apertura de radio 1 y mínimo 0,5 mL fijados desde el
   diseño (`referencia_clasica` en el YAML); no se ajustaron mirando val ni test.
6. Mapas de órganos (TotalSegmentator): se calculan a partir del CT y se usan solo para
   repartir errores en la evaluación (`scripts/12`, `scripts/13`); no entran a la red.
7. Regla de exclusión de la zona borrada: solo en `evaluate_study`; el entrenamiento y la
   validación rápida ven la anotación cruda, igual en las nueve corridas.
8. Prueba intacta: no existe ningún `results/*_test.csv` ni `runs/*/mascaras_test/`.
9. Cada corrida es independiente: carpeta propia, semilla propia, mismo manifiesto; ninguna
   parte de pesos de otra (la reanudación solo lee el `ultimo.pt` de su propia carpeta).

**Veredicto:** no hay fuga de pacientes entre particiones ni uso de val/test en el
entrenamiento. El conjunto de prueba sigue cerrado.

## 4. Dos limitaciones que dejo declaradas (no son fugas, pero hay que decirlas)

**a) La validación rápida elige el checkpoint con 12 estudios, y es un criterio ruidoso.**
`split_files` ordena los archivos alfabéticamente, así que los 12 son siempre los mismos en las
nueve corridas: 3 de pulmón, 3 de linfoma, 4 de melanoma y 2 negativos (10 positivos). Está
mezclado, pero pesa mucho el melanoma (lesiones de 3 a 9 mL, donde el Dice es más inestable)
e incluye a `1a90052cb2`, cuya única lesión está en la zona borrada: con la métrica cruda ese
estudio vale Dice 0 en todos los checkpoints (baja el promedio de la validación rápida, de ahí
el 0,50–0,59 frente al 0,60–0,63 de los 26 con exclusión, pero no cambia qué checkpoint
gana). El criterio es idéntico en las nueve corridas, así que la comparación A/B/C es justa;
no lo cambio ahora porque haría incomparables las cinco corridas terminadas (no guardo
checkpoints intermedios para reelegir). Mejora futura declarada: validar con los 26 o con
una submuestra estratificada más grande.

**b) Los números de val son de "conjunto de selección".** Los 12 estudios que eligen el
checkpoint están dentro de los 26 que reporto en validación, así que la validación es
levemente optimista. Por eso la comparación definitiva es en test (49 estudios), que ningún
modelo ha visto, y por eso se abre una sola vez.

## 5. Estado de las corridas (2026-09-06)

| Corrida | Estado | mejor.pt (it) | Dice val (26, con exclusión) |
|---|---|---|---|
| A | terminada | 23 000 | 0,603 |
| A_s2 | terminada | 24 000 | 0,632 |
| A_s3 | terminada | 22 000 | 0,630 |
| B | terminada | 13 000 | 0,603 |
| B_s2 | terminada | 19 000 | 0,606 |
| B_s3 | terminada | 22 000 | 0,628 |
| C | en curso (semilla 423) | | |
| C_s2, C_s3 | en cola | | |
