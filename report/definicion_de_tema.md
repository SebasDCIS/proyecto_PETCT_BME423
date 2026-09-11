---
title: "Segmentación automática de lesiones hipermetabólicas en FDG-PET/CT de cuerpo entero: fusión temprana frente a fusión intermedia con atención cruzada"
---

BME423, Procesamiento de imágenes médicas. Definición de tema del mini-proyecto. Segundo semestre 2026.

**Integrante:** Sebastián Inostroza, Tecnólogo Médico, estudiante del Doctorado en Ingeniería y Ciencias de la Salud, Universidad de Valparaíso. Modalidad individual.

## 1. Descripción del problema

El PET/CT con <sup>18</sup>F-FDG es el examen de referencia para estadificar y controlar linfoma, melanoma y cáncer de pulmón. El PET mide el consumo de glucosa, aumentado en el tejido tumoral, y el CT aporta la anatomía. Para calcular los biomarcadores cuantitativos que se usan en seguimiento, el volumen tumoral metabólico (MTV) y el SUVmax, primero hay que delinear cada lesión. Eso hoy se hace a mano o con umbrales, y un estudio de cuerpo entero toma entre 30 y 90 minutos de trabajo de un especialista. En la práctica el MTV rara vez se calcula fuera de protocolos de investigación.

El obstáculo técnico es la captación fisiológica. El encéfalo, el miocardio, los riñones, la vía urinaria, la grasa parda y los focos inflamatorios superan con holgura el umbral clásico de SUV ≥ 2,5. Un método que mire solo el PET, o que mezcle PET y CT desde la primera capa sin ningún mecanismo explícito de consulta anatómica, marca esos órganos como tumor. Cada mililitro de falso positivo infla el MTV y degrada el seguimiento.

El desafío autoPET fija el estado del arte sobre datos públicos. En la edición 2022 todas las soluciones ganadoras fueron U-Net 3D del tipo nnU-Net: la primera obtuvo Dice 0,623, volumen de falso negativo (FNV) 0,54 mL y volumen de falso positivo (FPV) 2,84 mL, promediados sobre estudios positivos y negativos [2]. Un nnU-Net sin modificar alcanza Dice 0,69 con FPV 5,78 mL y FNV 6,27 mL en un conjunto interno [4]; al cambiar de centro, el mejor Dice cae a 0,36 [2]. Las ediciones posteriores del desafío se abrieron a varios trazadores y varios centros [8].

En cohortes distintas de autoPET, la fusión intermedia con atención ha mostrado ganancias sobre la concatenación simple: un módulo de atención espacial PET a CT en pulmón [5], atención cruzada multiescala en linfoma (Dice 0,751) [6] y un transformer de atención cruzada en nasofaringe [7]. Lo que no está publicado es la comparación entre fusión temprana, fusión intermedia por concatenación y fusión intermedia con atención cruzada sobre autoPET y con presupuesto de entrenamiento idéntico, ni el análisis de en qué órganos fisiológicos se concentran los falsos positivos de cada una. Ese es el vacío que aborda este proyecto.

## 2. Objetivo del trabajo

**Objetivo general.** Implementar y comparar tres estrategias de fusión PET/CT en una U-Net 3D para segmentar lesiones hipermetabólicas en FDG-PET/CT de cuerpo entero, con el mismo presupuesto de datos e iteraciones, y cuantificar su efecto sobre los falsos positivos en órganos de captación fisiológica y sobre los biomarcadores MTV y SUVmax.

**Hipótesis.** Condicionar las activaciones funcionales del PET a la evidencia anatómica del CT mediante atención cruzada reduce el FPV respecto de la fusión temprana, sin aumentar el FNV.

Objetivos específicos:

1. Pipeline de preprocesamiento y referencia clásica. Conversión DICOM a NIfTI con cálculo de SUV normalizado por peso, remuestreo isotrópico a 3 mm, ventaneo de tejido blando (−200 a 300 HU), recorte del cuerpo y extracción de parches de 96³ vóxeles con muestreo sesgado a lesiones. Como punto de comparación se evalúa con las mismas métricas un método clásico del curso: umbral SUV ≥ 2,5, apertura morfológica y exclusión anatómica de órganos fisiológicos.
2. Modelo A, fusión temprana. U-Net 3D con SUV y CT como dos canales de entrada, en MONAI, con pérdida Dice más entropía cruzada.
3. Modelos B y C, fusión intermedia. Dos codificadores independientes y un decodificador común. En B las representaciones se concatenan en el cuello de botella, lo que funciona como control de capacidad. En C se combinan mediante atención cruzada, donde el mapa PET actúa como consulta y el mapa CT como clave y valor, de modo que la sospecha metabólica se module por la anatomía. La comparación B contra C permite atribuir cualquier diferencia al mecanismo de atención y no a la duplicación del codificador.
4. Evaluación comparativa. Dice, distancia de Hausdorff al percentil 95, FPV y FNV por estudio con el script oficial de autoPET; FPV desglosado por órgano (encéfalo, miocardio, riñones y vejiga, hígado, intestino) mediante máscaras anatómicas derivadas del CT; error absoluto en MTV y SUVmax por paciente; intervalos de confianza por bootstrap sobre el conjunto de prueba y análisis cualitativo de casos.

## 3. Punto de partida

El proyecto se apoya en código abierto y añade una implementación propia acotada. La base es MONAI, de donde se toman las transformaciones 3D, las arquitecturas UNet y DynUNet, la inferencia por ventana deslizante y las métricas [9]. Del repositorio oficial del desafío se toman la conversión DICOM a NIfTI con cálculo de SUV y el script de evaluación con Dice, FPV y FNV. Como referencia arquitectónica se usan la documentación de nnU-Net [3] y los diseños de fusión de Fu et al. [5] y Huang et al. [6].

Lo propio del curso es el codificador dual, el bloque de atención cruzada sobre los tokens del cuello de botella, el muestreo de parches, la implementación de la referencia clásica y el análisis de falsos positivos por órgano. Con parches de 96³ y cuatro reducciones, el cuello de botella tiene 6³ = 216 posiciones, de modo que la atención es computacionalmente barata.

El proyecto no continúa un trabajo anterior de otra asignatura ni de la tesis doctoral. A la fecha de esta entrega el pipeline completo está implementado y verificado con pruebas unitarias, y las corridas de entrenamiento están en curso.

Sobre los recursos, conviene declarar una restricción que condiciona el alcance. El entrenamiento corre en un computador personal con procesador Apple Silicon, usando el acelerador gráfico integrado en precisión simple. Cada corrida son 25 000 iteraciones con lote de 2 parches, del orden de nueve horas. El diseño contempla tres modelos por tres semillas de inicialización, es decir nueve corridas, porque con una sola semilla no hay forma de distinguir una diferencia real entre arquitecturas de la variación propia del azar en la inicialización y en el orden de los parches. La resolución de trabajo es de 3 mm en lugar de los 2 mm habituales, limitación que se declara y que resulta compatible con lesiones FDG clínicamente relevantes, por encima de 1 cm.

## 4. Datasets

**FDG-PET-CT-Lesions (autoPET), The Cancer Imaging Archive.** Contiene 1 014 estudios PET/CT de cuerpo entero de 900 pacientes del Hospital Universitario de Tübingen: 501 estudios positivos (168 cáncer de pulmón, 145 linfoma, 188 melanoma) y 513 controles negativos. El PET tiene vóxel de 2,04 × 2,04 × 3 mm y las máscaras 3D de todas las lesiones FDG ávidas malignas fueron delineadas manualmente por un lector experto y revisadas por consenso [1]. Se usa la versión con rostro anonimizado, licencia CC BY 4.0, DOI 10.7937/gkr0-xv29, disponible en <https://cancerimagingarchive.net/collection/fdg-pet-ct-lesions/>. El desafío distribuye además los mismos estudios ya convertidos a NIfTI, con el CT remuestreado a la grilla del PET, en <https://autopet-ii.grand-challenge.org/dataset/>.

**Subconjunto de trabajo.** 251 estudios seleccionados de forma reproducible con semilla fija y descargados por paciente: 201 positivos estratificados por diagnóstico (67 de cáncer de pulmón, 67 de linfoma y 67 de melanoma) y 50 controles negativos. La partición es por paciente en proporción 70/10/20, lo que da 176 estudios de entrenamiento, 26 de validación y 49 de prueba. Ningún paciente aparece en dos particiones. La colección hermana PSMA-PET-CT-Lesions (597 estudios, CC BY 4.0) se reserva como trabajo futuro para evaluar generalización entre trazadores.

## 5. Artículos relacionados

[1] Gatidis S, Hepp T, Früh M, et al. A whole-body FDG-PET/CT Dataset with manually annotated Tumor Lesions. Sci Data. 2022;9:601. doi:10.1038/s41597-022-01718-3

[2] Gatidis S, Früh M, Fabritius MP, et al. Results from the autoPET challenge on fully automated lesion segmentation in oncologic PET/CT imaging. Nat Mach Intell. 2024;6:1396-1405. doi:10.1038/s42256-024-00912-9

[3] Isensee F, Maier-Hein KH. Look Ma, no code: fine tuning nnU-Net for the AutoPET II challenge by only adjusting its JSON plans. arXiv:2309.13747; 2023.

[4] Alloula A, McGowan DR, Papież BW. Autopet Challenge 2023: nnUNet-based whole-body 3D PET-CT tumour segmentation. arXiv:2309.13675; 2023.

[5] Fu X, Bi L, Kumar A, Fulham M, Kim J. Multimodal Spatial Attention Module for Targeting Multimodal PET-CT Lung Tumor Segmentation. IEEE J Biomed Health Inform. 2021;25(9):3507-3516. doi:10.1109/JBHI.2021.3059453

[6] Huang H, Qiu L, Yang S, et al. 3D lymphoma segmentation on PET/CT images via multi-scale information fusion with cross-attention. Med Phys. 2025. doi:10.1002/mp.17763

[7] Zhao W, Huang Z, Tang S, et al. MMCA-NET: A Multimodal Cross Attention Transformer Network for Nasopharyngeal Carcinoma Tumor Segmentation Based on a Total-Body PET/CT System. IEEE J Biomed Health Inform. 2024. doi:10.1109/JBHI.2024.3405993

[8] Gatidis S, et al. The autoPET3 Challenge: Automated Lesion Segmentation in Multitracer Multicenter PET/CT. arXiv:2605.05775.

[9] Cardoso MJ, et al. MONAI: An open-source framework for deep learning in healthcare. arXiv:2211.02701; 2022.

[10] Isensee F, Jaeger PF, Kohl SAA, Petersen J, Maier-Hein KH. nnU-Net: a self-configuring method for deep learning-based biomedical image segmentation. Nat Methods. 2021;18:203-211. doi:10.1038/s41592-020-01008-z
