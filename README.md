# Segmentación de lesiones en FDG-PET/CT: fusión temprana frente a fusión intermedia con atención cruzada

Mini-proyecto del curso **BME423 Procesamiento de imágenes médicas** (Universidad de Valparaíso, segundo semestre 2026).
Autor: **Sebastián Inostroza**, Tecnólogo Médico, Doctorado en Ciencias e Ingeniería para la Salud.

**Informe final:** [`report/final/informe.pdf`](report/final/informe.pdf) (fuente LaTeX y BibTeX en [`report/final/`](report/final/)).
Entrega parcial: [`report/parcial/entrega_parcial.pdf`](report/parcial/entrega_parcial.pdf).
Definición de tema: [`report/definicion_de_tema.pdf`](report/definicion_de_tema.pdf).

## De qué se trata

En un PET/CT con FDG las lesiones tumorales captan glucosa y "brillan", pero también brillan
órganos sanos: encéfalo, corazón, riñones, vejiga, intestino. Un umbral de SUV no los distingue.
Este proyecto compara formas de combinar el PET y el CT dentro de una U-Net 3D para segmentar
las lesiones de estudios de cuerpo entero de la colección pública autoPET, con el mismo
presupuesto de datos y entrenamiento para todas, y frente a una referencia clásica del curso.

| Brazo | Fusión | Idea |
|---|---|---|
| Clásica | sin aprendizaje | umbral SUV ≥ 2,5 + apertura morfológica + componentes conexas ≥ 0,5 mL |
| A | temprana | PET y CT como dos canales de una U-Net (12,9 M parámetros) |
| A+ | temprana | A con 1,375× canales (24,3 M): control de capacidad |
| B | intermedia, concatenación | un codificador por modalidad, unidos en el cuello de botella (24,0 M) |
| C | intermedia, atención cruzada | B + atención cruzada en el cuello: el PET consulta al CT (24,4 M) |
| E | temprana + referencia | A + tercer canal: SUV ÷ SUV hepático del paciente |
| Sistema final | ensamble | cinco B (uno por pliegue) + TTA, umbral 0,6 |

## Resultados principales (prueba, 49 estudios, abierta una sola vez)

| | Dice⁺ | FPV (mL) | FNV (mL) |
|---|---|---|---|
| Umbral clásico | 0,182 | 832,5 | 2,1 |
| A, acto 1 (176 estudios, 25 000 it.) | 0,616 | 38,4 | 5,8 |
| B, etapa extendida (825 estudios, 100 000 it.) | 0,698 | 18,9 | 2,7 |
| **Sistema final** | **0,727** | **9,5** | **3,95** |

- Las dos hipótesis preregistradas (H1 y H2) se confirmaron: el sistema final mejora a B en
  Dice⁺ (+0,029, IC95 +0,006 a +0,054) y en FPV (−9,4 mL, IC95 −16,4 a −4,5).
- Con entrenamiento suficiente, los dos codificadores superan a la fusión temprana, y no por
  tamaño: A+ empata con A.
- La atención cruzada del brazo C quedó inerte (ablación con diferencia cero); el mecanismo
  está medido en el informe.

Tablas completas: [`results/test_final/resumen.md`](results/test_final/resumen.md) y
[`docs/RESULTADOS_TEST.md`](docs/RESULTADOS_TEST.md). Análisis secundarios (HD95, SUVmax,
script oficial, clásica con exclusión de órganos): [`docs/METRICAS_COMPLEMENTARIAS.md`](docs/METRICAS_COMPLEMENTARIAS.md).

## Estructura del repositorio

```
configs/default.yaml       constantes del proyecto (preprocesamiento, clásica, entrenamiento)
src/petct/                 biblioteca
  suv.py convert.py geometry.py   SUV desde DICOM, DICOM → NIfTI, SEG por posición física
  tcia.py                         subconjunto reproducible y descarga desde TCIA
  preprocess.py data.py           3 mm, ventana CT, SUV/30, recorte, parches con sesgo a lesión
  classical.py                    referencia clásica (umbral + morfología + componentes)
  models.py                       brazos A, A+, B, C y E (MONAI)
  losses.py train.py device.py    Dice + entropía cruzada, bucle de entrenamiento, mps/cuda/cpu
  infer.py postproc.py            ventana deslizante con ponderación gaussiana, TTA, posproceso
  metrics.py organs.py            Dice, FPV, FNV, zona anonimizada; errores por órgano
  reference.py                    referencia hepática del brazo E
scripts/                   pasos numerados en el orden del trabajo (01 a 43)
  oficial_autopet/         script oficial de evaluación del reto (MIT), sin cambios
tests/                     pruebas con un fantoma DICOM sintético
data/manifests/            listas de pacientes, particiones y pliegues (sí van al repo)
data/raw|interim|processed datos (NO van al repo; ver abajo)
results/                   tablas por estudio y resúmenes (CSV y Markdown)
docs/                      bitácora técnica por etapa, preregistro, figuras
report/                    definición de tema, parcial e informe final (LaTeX + BibTeX + PDF)
notebooks/                 cuadernos del acto 1, uno por paso
BITACORA.md                bitácora fechada de todo el proyecto
```

## Requisitos e instalación

Python 3.10 a 3.12. Probado en un MacBook Pro M5 (24 GB) con PyTorch 2.14 sobre `mps` y
MONAI 1.6; también corre en CUDA o en CPU (lento).

```bash
git clone https://github.com/SebasDCIS/proyecto_PETCT_BME423.git
cd proyecto_PETCT_BME423
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install torch monai            # aprendizaje profundo
pip install TotalSegmentator       # solo para el análisis por órgano y el brazo E
python -m pytest tests -q          # todas las pruebas deben pasar
```

## Datos

Colección **FDG-PET-CT-Lesions** (autoPET), The Cancer Imaging Archive, licencia CC BY 4.0,
versión con rostro anonimizado. DOI 10.7937/gkr0-xv29.
https://www.cancerimagingarchive.net/collection/fdg-pet-ct-lesions/

Los datos no se suben al repositorio. Desde la página de la colección se descargan el CSV
clínico (guardarlo como `data/manifests/clinical_tcia.csv`) y el manifiesto de la versión
anonimizada (`data/manifests/FDG-PET-CT-Lesions_defaced.tcia`). Las particiones usadas
están en `data/manifests/subconjunto.csv` (acto 1, 251 estudios) y
`data/manifests/subconjunto_extendido.csv` (900 estudios, uno por paciente). La validación
(26) y la prueba (49) son las mismas en los dos.

## Cómo reproducir

Todos los comandos se corren desde la raíz del repositorio. Los entrenamientos largos se
lanzaron con `caffeinate -i` en el Mac para que no se suspendiera.

**1. Datos y referencia clásica (acto 1, 251 estudios)**

```bash
python scripts/01_seleccionar_subconjunto.py data/manifests/clinical_tcia.csv
python scripts/02_descargar_tcia.py --tcia-manifest data/manifests/FDG-PET-CT-Lesions_defaced.tcia --descargar
python scripts/03_convertir_a_nifti.py
python scripts/04_preprocesar.py
python scripts/05_referencia_clasica.py
```

**2. Acto 1: brazos A, B, C y E con tres semillas (25 000 iteraciones)**

```bash
python scripts/07_entrenar.py --modelo A --salida runs/A               # semilla 423
python scripts/07_entrenar.py --modelo A --semilla 2 --salida runs/A_s2
python scripts/09_evaluar.py --modelo A --checkpoint runs/A/mejor.pt --particion val
python scripts/10_resumir_corridas.py
```

Igual para B, C y E. El brazo E necesita antes los mapas de órganos
(`scripts/11_organos_totalsegmentator.py`) y las referencias hepáticas. Los análisis del acto 1
están en los scripts 11 a 20 (por órgano, casos, atlas de normalidad, desfase del diafragma).

**3. Etapa extendida (825 estudios, 100 000 iteraciones)**

```bash
python scripts/24_ampliar_entrenamiento.py      # arma subconjunto_extendido.csv
python scripts/25_traer_por_lotes.py            # descarga, convierte y preprocesa por lotes
caffeinate -i bash scripts/27_semillas_largo.sh # A, A+, B y C con tres semillas
caffeinate -i bash scripts/30_anatomia_cola.sh  # preentrenamiento del CT y pérdida por órgano
python scripts/32_pliegues.py                   # cinco pliegues estratificados
BRAZO=B caffeinate -i bash scripts/34_ensamble_cola.sh   # cinco B + ensamble en validación
caffeinate -i bash scripts/38_oof_umbral_higado.sh      # umbral decidido fuera de pliegue
```

**4. Prueba (una sola vez)**

```bash
caffeinate -i bash scripts/35_test_final.sh     # exige el preregistro commiteado
python scripts/37_analisis_final.py --particion test
python scripts/40_metricas_complementarias.py --particion test
python scripts/41_resumen_complementarias.py
python scripts/42_casos_prueba.py
python scripts/43_fp_organo_todos_test.py
```

`scripts/35_test_final.sh` se niega a correr si `docs/TEST_PREREGISTRO.md` o el script de
análisis tienen cambios sin commitear, y deja el acta de apertura en `results/test/APERTURA.txt`.

**Informe**

```bash
cd report/final && xelatex informe && bibtex informe && xelatex informe && xelatex informe
```

## Tiempos y reproducibilidad

- A tarda 0,65 s por iteración y B o C 0,79 s en el M5: unas 5 a 6,5 horas por corrida de
  25 000 iteraciones y cerca de un día por corrida de 100 000. En total hubo 38 corridas.
- Las particiones, los pliegues y el muestreo usan semilla fija (423), pero en `mps` las
  operaciones de PyTorch no son deterministas: repetir una corrida da un modelo distinto bit
  a bit y resultados equivalentes en promedio, no idénticos.
- Las máscaras predichas, los checkpoints y los datos preprocesados no están en el repositorio
  por su tamaño.

## Documentación

- [`BITACORA.md`](BITACORA.md): qué se hizo cada día y por qué.
- [`docs/PROTOCOLO_CONGELADO.md`](docs/PROTOCOLO_CONGELADO.md) y [`docs/AUDITORIA.md`](docs/AUDITORIA.md): protocolo y auditoría de fugas.
- [`docs/PASO1_RESULTADO.md`](docs/PASO1_RESULTADO.md) a [`docs/PASO4_ENSAMBLE.md`](docs/PASO4_ENSAMBLE.md): las cuatro etapas del extendido.
- [`docs/TEST_PREREGISTRO.md`](docs/TEST_PREREGISTRO.md): hipótesis y reglas escritas antes de abrir la prueba.
- [`docs/GLOSARIO.md`](docs/GLOSARIO.md): términos del proyecto con analogías.

## Cita del dataset

Gatidis S, et al. *A whole-body FDG-PET/CT dataset with manually annotated tumor lesions.*
Sci Data 2022;9:601. doi:10.1038/s41597-022-01718-3.

## Uso de inteligencia artificial

Se usó Claude (Anthropic) como asistente para revisar y depurar código, proponer la estructura
de algunos scripts y corregir la redacción. Las decisiones del trabajo, la ejecución de los
entrenamientos y la lectura de los resultados son del autor.

## Licencia

Código bajo licencia MIT. Los datos conservan la licencia de TCIA (CC BY 4.0). El script oficial
de autoPET en `scripts/oficial_autopet/` conserva su licencia MIT original.
