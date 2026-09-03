# Segmentación de lesiones en FDG-PET/CT: fusión temprana vs intermedia con atención cruzada

Mini-proyecto del curso **BME423 – Procesamiento de imágenes médicas** (Universidad de Valparaíso, 2º semestre 2026).
Autor: **Sebastián Inostroza**, Tecnólogo Médico, Doctorado en Ingeniería y Ciencias de la Salud.

## De qué se trata

En un PET/CT con FDG las lesiones tumorales "brillan", pero también brillan órganos sanos
(encéfalo, corazón, riñones, vejiga, grasa parda). Una red que mira solo el PET, o que mezcla
PET y CT desde la primera capa, marca esos órganos como tumor. Este proyecto compara tres
maneras de combinar PET y CT en una U-Net 3D **con el mismo presupuesto de entrenamiento**:

| Modelo | Fusión | Idea |
|---|---|---|
| A | Temprana | PET y CT como dos canales de entrada (baseline) |
| B | Intermedia, concatenación | Dos codificadores, unidos en el cuello de botella (control) |
| C | Intermedia, atención cruzada | El mapa PET "pregunta" al mapa CT qué hay en cada sitio antes de decidir |

Se mide Dice, HD95, volumen de falsos positivos (FPV) y falsos negativos (FNV) con el script
oficial de autoPET, más FPV **por órgano fisiológico** y error en MTV y SUVmax. Antes de
cualquier red se evalúa una referencia clásica del curso (umbral SUV ≥ 2,5 + morfología +
exclusión anatómica).

Documento de definición de tema: [`report/definicion_de_tema.pdf`](report/definicion_de_tema.pdf).
Bitácora del proyecto: [`BITACORA.md`](BITACORA.md). Glosario con analogías: [`docs/GLOSARIO.md`](docs/GLOSARIO.md).

## Estructura

```
configs/default.yaml      todos los números del proyecto en un solo lugar
src/petct/                paquete Python
  suv.py                  cálculo del SUV desde etiquetas DICOM
  convert.py              DICOM (CT, PT, SEG) → NIfTI (CT, PET, SUV, CTres, SEG)
  tcia.py                 subconjunto reproducible + descarga desde TCIA
scripts/                  pasos numerados, uno por etapa
tests/                    pruebas con un fantoma DICOM sintético (sin datos reales)
data/manifests/           listas de pacientes/series (sí van al repo)
data/raw|interim|processed  datos (NO van al repo; ver data/README.md)
docs/                     glosario, figuras, notas
report/                   informe LaTeX y PDFs entregados
notebooks/                cuadernos comentados, uno por paso (se regeneran con build_notebooks.py)
```

## Requisitos e instalación

Python 3.10–3.12. En el computador (CPU):

```bash
git clone https://github.com/SebasDCIS/proyecto_PETCT_BME423.git
cd proyecto_PETCT_BME423
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests -q          # debe imprimir "8 passed"
```

En el Mac se abre la carpeta en VS Code con la extensión de Jupyter y se eligen el
kernel `.venv`. Los cuadernos de `notebooks/` se ejecutan ahí; los módulos de `src/petct`
son los mismos que usan los scripts y las pruebas.

Dónde corre cada etapa: los pasos 1, 2 y 5 (datos, preprocesamiento, evaluación) corren en
el Mac. Los entrenamientos con presupuesto completo (pasos 3 y 4) corren en Google Colab con
`torch` y `monai`; en el Mac, PyTorch usa el chip gráfico de Apple (`mps`) para pruebas
cortas. `notebooks/00_entorno.ipynb` revisa qué tiene cada máquina.

## Acceso a los datos

Colección **FDG-PET-CT-Lesions** (autoPET), The Cancer Imaging Archive, licencia CC BY 4.0
(versión con rostro anonimizado). DOI 10.7937/gkr0-xv29.
https://www.cancerimagingarchive.net/collection/fdg-pet-ct-lesions/

Los datos no se suben al repositorio. Para reproducir:

1. Descargar el CSV clínico desde la página de TCIA y guardarlo como `data/manifests/clinical_tcia.csv`.
2. `python scripts/01_seleccionar_subconjunto.py data/manifests/clinical_tcia.csv`
   → `data/manifests/subconjunto.csv` (250 estudios, semilla 423, partición por paciente).
3. `python scripts/02_descargar_tcia.py --limit 3` para probar, luego sin `--limit` (≈ 100 GB en DICOM).
4. `python scripts/03_convertir_a_nifti.py` → `data/interim/nifti/<paciente>/<estudio>/{CT,PET,SUV,CTres,SEG}.nii.gz`.

Cita del dataset: Gatidis S, et al. *A whole-body FDG-PET/CT Dataset with manually annotated Tumor
Lesions.* Sci Data 2022;9:601. doi:10.1038/s41597-022-01718-3.

## Ejecución (se completa a medida que avanza el proyecto)

| Paso | Script / notebook | Estado |
|---|---|---|
| 0 | `notebooks/00_entorno.ipynb` revisión del entorno | listo |
| 1 | `notebooks/01_datos_suv_conversion.ipynb` y `scripts/01…03` | listo y probado con fantoma sintético |
| 2 | preprocesamiento y referencia clásica | pendiente |
| 3 | modelo A (fusión temprana), Colab | pendiente |
| 4 | modelos B y C (fusión intermedia) | pendiente |
| 5 | evaluación y análisis por órgano | pendiente |

## Licencia

Código bajo licencia MIT. Los datos conservan la licencia de TCIA (CC BY 4.0).
