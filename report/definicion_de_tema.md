---
title: "Segmentación automática de lesiones hipermetabólicas en FDG-PET/CT de cuerpo entero: fusión temprana frente a fusión intermedia con atención cruzada"
---

BME423, Procesamiento de imágenes médicas. Definición de tema del mini-proyecto. Segundo semestre 2026.

**Integrante:** Sebastián Inostroza, Tecnólogo Médico, estudiante del Doctorado en Ingeniería y Ciencias de la Salud, Universidad de Valparaíso. Modalidad individual.

## 1. Descripción del problema

El PET/CT con ^18^F-FDG se usa en la estadificación y el control de la mayoría de los tumores sólidos y hematológicos, y también fuera de la oncología: fiebre de origen desconocido, endocarditis, sarcoidosis, vasculitis de grandes vasos. Conviene ser preciso sobre qué mide, porque de ahí sale el problema técnico de este trabajo: el trazador no marca tumor, marca consumo de glucosa. El proyecto se acota a las tres indicaciones que cubre el único conjunto público de cuerpo entero con anotación manual de lesiones, linfoma, melanoma y cáncer de pulmón, y las conclusiones no se extienden más allá.

El PET aporta el metabolismo y el CT la anatomía. Para calcular los biomarcadores que se usan en seguimiento, el volumen tumoral metabólico (MTV) y el SUVmax, primero hay que delinear cada lesión, a mano o con umbrales. Un estudio de cuerpo entero toma entre 30 y 90 minutos de trabajo de un especialista, de modo que el MTV rara vez se calcula fuera de protocolos de investigación.

El obstáculo técnico es que muchas cosas que no son tumor consumen glucosa. El encéfalo, el miocardio, los riñones, la vía urinaria, el intestino y la grasa parda lo hacen de forma fisiológica; el tejido inflamatorio o infeccioso, de forma patológica pero no tumoral. Todos superan con holgura el umbral clásico de SUV ≥ 2,5. Un método que mire solo el PET, o que mezcle PET y CT desde la primera capa sin consulta anatómica explícita, marca esos tejidos como tumor, y cada mililitro de falso positivo infla el MTV y degrada el seguimiento.

El desafío autoPET fija el estado del arte sobre datos públicos. En la edición 2022 todas las soluciones ganadoras fueron U-Net 3D del tipo nnU-Net: la primera obtuvo Dice 0,623, volumen de falso negativo (FNV) 0,54 mL y volumen de falso positivo (FPV) 2,84 mL, promediados sobre estudios positivos y negativos [2]. Un nnU-Net sin modificar alcanza Dice 0,69 con FPV 5,78 mL y FNV 6,27 mL en un conjunto interno [4]; al cambiar de centro, el mejor Dice cae a 0,36 [2]. Las ediciones posteriores del desafío se abrieron a varios trazadores y varios centros [8].

En cohortes distintas de autoPET, la fusión intermedia con atención ha rendido más que la concatenación simple: atención espacial PET a CT en pulmón [5], atención cruzada multiescala en linfoma con Dice 0,751 [6] y un transformer de atención cruzada en nasofaringe [7]. Lo que no está publicado es la comparación de las tres formas de fusionar sobre autoPET con presupuesto de entrenamiento idéntico, ni el análisis de en qué órganos fisiológicos se concentra el falso positivo de cada una. Ese es el vacío que aborda este proyecto.

## 2. Objetivo del trabajo

**Objetivo general.** Implementar y comparar tres estrategias de fusión PET/CT en una U-Net 3D para segmentar lesiones hipermetabólicas en FDG-PET/CT de cuerpo entero, con el mismo presupuesto de datos e iteraciones, y cuantificar su efecto sobre el falso positivo en órganos de captación fisiológica y sobre el MTV y el SUVmax.

**Hipótesis.** Condicionar las activaciones funcionales del PET a la evidencia anatómica del CT mediante atención cruzada reduce el FPV respecto de la fusión temprana, sin aumentar el FNV.

Objetivos específicos:

1. Pipeline y referencia clásica. Conversión DICOM a NIfTI con cálculo de SUV normalizado por peso, remuestreo isotrópico a 3 mm, ventaneo de tejido blando (−200 a 300 HU), recorte del cuerpo y parches de 96³ vóxeles con muestreo sesgado a lesiones. Como punto de comparación se evalúa con las mismas métricas un método clásico del curso: umbral SUV ≥ 2,5, apertura morfológica y exclusión anatómica de órganos fisiológicos.
2. Modelo A, fusión temprana. U-Net 3D con SUV y CT como dos canales de entrada, en MONAI, con pérdida Dice más entropía cruzada.
3. Modelos B y C, fusión intermedia. Dos codificadores independientes y un decodificador común. En B las representaciones se concatenan en el cuello de botella, lo que sirve de control de capacidad. En C se combinan por atención cruzada, con el mapa PET como consulta y el CT como clave y valor, de modo que la anatomía module la sospecha metabólica. Comparar B contra C atribuye cualquier diferencia al mecanismo de atención y no a la duplicación del codificador.
4. Evaluación comparativa. Dice, Hausdorff al percentil 95, FPV y FNV por estudio con el script oficial de autoPET; FPV desglosado por órgano (miocardio, riñones y vía urinaria, hígado, bazo, intestino, hueso, músculo) mediante máscaras anatómicas derivadas del CT; error absoluto en MTV y SUVmax por paciente; intervalos de confianza por bootstrap sobre el conjunto de prueba y análisis cualitativo de casos.

## 3. Punto de partida

El proyecto se apoya en código abierto y añade una implementación propia acotada. De MONAI se toman las transformaciones 3D, las arquitecturas UNet y DynUNet, la inferencia por ventana deslizante y las métricas [9]; del repositorio oficial del desafío, la conversión DICOM a NIfTI con cálculo de SUV y el script de evaluación. Como referencia arquitectónica se usan nnU-Net [3] y los diseños de fusión de Fu et al. [5] y Huang et al. [6].

Lo propio del curso es el codificador dual, el bloque de atención cruzada sobre los tokens del cuello de botella, el muestreo de parches, la referencia clásica y el análisis de falsos positivos por órgano. Con parches de 96³ y cuatro reducciones el cuello de botella tiene 6³ = 216 posiciones, así que la atención es barata.

El proyecto no continúa un trabajo anterior de otra asignatura ni de la tesis doctoral. A la fecha de esta entrega el pipeline completo está implementado y verificado con pruebas unitarias, y las corridas de entrenamiento están en curso.

Los recursos condicionan el alcance y conviene declararlo. El entrenamiento corre en un computador personal con procesador Apple Silicon, sobre el acelerador gráfico integrado y en precisión simple: 25 000 iteraciones con lote de 2 parches, del orden de nueve horas por corrida. Son tres modelos por tres semillas, nueve corridas, porque con una sola semilla no hay forma de separar una diferencia real entre arquitecturas del azar de la inicialización y del orden de los parches. La resolución de trabajo es de 3 mm en lugar de los 2 mm habituales, compatible con lesiones FDG clínicamente relevantes, por encima de 1 cm.

## 4. Datasets

**FDG-PET-CT-Lesions (autoPET), The Cancer Imaging Archive.** Contiene 1 014 estudios PET/CT de cuerpo entero de 900 pacientes del Hospital Universitario de Tübingen: 501 positivos (168 cáncer de pulmón, 145 linfoma, 188 melanoma) y 513 controles negativos. El PET tiene vóxel de 2,04 × 2,04 × 3 mm y las máscaras 3D de todas las lesiones FDG ávidas malignas se delinearon manualmente y se revisaron por consenso [1]. Se usa la versión anonimizada, licencia CC BY 4.0, DOI 10.7937/gkr0-xv29 (<https://cancerimagingarchive.net/collection/fdg-pet-ct-lesions/>). El desafío distribuye los mismos estudios ya convertidos a NIfTI, con el CT remuestreado a la grilla del PET (<https://autopet-ii.grand-challenge.org/dataset/>).

**Limitación por anonimización.** La versión pública se anonimiza borrando la región facial y craneal, porque de un CT de cabeza se puede reconstruir el rostro del paciente. Ahí el PET vale cero, pero la anotación se hizo sobre la imagen original y conserva lesiones en esa zona, que ningún método puede encontrar porque no queda señal. Evaluarlas mediría el anonimizado y no el modelo, así que se excluyen de la predicción y de la verdad los vóxeles con SUV = 0, con la misma regla para los tres modelos y para la referencia clásica, y se reporta por estudio cuánta lesión queda excluida. La consecuencia hay que declararla: este trabajo no dice nada sobre lesiones de cabeza y cuello ni sobre la captación fisiológica del encéfalo, la más intensa del organismo y el falso positivo más clásico del umbral por SUV. El análisis por órgano queda limitado a tórax, abdomen y pelvis.

**Subconjunto de trabajo.** 251 estudios seleccionados con semilla fija y descargados por paciente: 201 positivos estratificados por diagnóstico (67 por cada uno) y 50 controles negativos. La partición es por paciente en proporción 70/10/20, o sea 176 de entrenamiento, 26 de validación y 49 de prueba, sin que ningún paciente aparezca en dos de ellas. La colección hermana PSMA-PET-CT-Lesions (597 estudios, CC BY 4.0) queda como trabajo futuro para evaluar generalización entre trazadores.

## 5. Artículos relacionados

::: {custom-style="Referencias"}
[1] Gatidis S, et al. A whole-body FDG-PET/CT dataset with manually annotated tumor lesions. Sci Data. 2022;9:601.

[2] Gatidis S, et al. Results from the autoPET challenge on fully automated lesion segmentation in oncologic PET/CT imaging. Nat Mach Intell. 2024;6:1396-1405.

[3] Isensee F, Maier-Hein KH. Look Ma, no code: fine tuning nnU-Net for the autoPET II challenge by only adjusting its JSON plans. arXiv:2309.13747; 2023.

[4] Alloula A, McGowan DR, Papież BW. autoPET challenge 2023: nnU-Net-based whole-body 3D PET-CT tumour segmentation. arXiv:2309.13675; 2023.

[5] Fu X, Bi L, Kumar A, Fulham M, Kim J. Multimodal spatial attention module for targeting multimodal PET-CT lung tumor segmentation. IEEE J Biomed Health Inform. 2021;25(9):3507-3516.

[6] Huang H, Qiu L, Yang S, et al. 3D lymphoma segmentation on PET/CT images via multi-scale information fusion with cross-attention. Med Phys. 2025.

[7] Zhao W, Huang Z, Tang S, et al. MMCA-Net: a multimodal cross attention transformer network for nasopharyngeal carcinoma tumor segmentation on total-body PET/CT. IEEE J Biomed Health Inform. 2024.

[8] Gatidis S, et al. The autoPET3 challenge: automated lesion segmentation in multitracer multicenter PET/CT. arXiv:2605.05775; 2026.

[9] Cardoso MJ, et al. MONAI: an open-source framework for deep learning in healthcare. arXiv:2211.02701; 2022.
:::
