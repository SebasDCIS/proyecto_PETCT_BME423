# Resultados finales sobre `test`

*Generado por `scripts/37_analisis_final.py --particion test`. Lo que se mide y cómo se decide está en `docs/TEST_PREREGISTRO.md`, escrito antes de abrir el test.*

## Hipótesis principal (H1)

Ensamble de cinco pliegues + TTA, umbral 0,5, contra B (825 estudios, media de tres semillas). Se confirma si el IC95 de ΔDice⁺ queda entero sobre 0 **y** el de ΔFPV entero bajo 0.

| comparación | ΔDice⁺ | IC95 | gana | p | ΔFPV mL | IC95 | baja en | p |
|---|---|---|---|---|---|---|---|---|
| ensamble+TTA − B | +0.028 | [+0.011, +0.048] | 28/38 | 0.000 | -7.01 | [-12.35, -3.38] | 49/49 | 0.000 |

**Veredicto H1: CONFIRMADA.**

## Hipótesis H2: el sistema final

Ensamble + TTA con el umbral (0.6) y la regla del hígado (no) decididos sobre los 825 estudios fuera de pliegue, contra B. Misma regla de confirmación que H1.

| comparación | ΔDice⁺ | IC95 | gana | p | ΔFPV mL | IC95 | baja en | p |
|---|---|---|---|---|---|---|---|---|
| sistema final − B | +0.029 | [+0.006, +0.054] | 23/38 | 0.026 | -9.38 | [-16.44, -4.47] | 49/49 | 0.000 |

**Veredicto H2: CONFIRMADA.**

## Todos los brazos (métrica corregida)

| brazo | semillas | Dice⁺ | sd | mediana | FPV mL | FPV mediana | FNV mL | FPV en controles |
|---|---|---|---|---|---|---|---|---|
| Clásica (SUV ≥ 2,5) | 1 | 0.182 |  | 0.128 | 832.50 | 741.28 | 2.12 | 987.07 |
| Acto 1 · A (176 est., 25k, mejor.pt) | 3 | 0.616 | 0.001 | 0.664 | 38.44 | 13.21 | 5.75 | 85.71 |
| Acto 1 · B (176 est., 25k, mejor.pt) | 3 | 0.630 | 0.023 | 0.676 | 23.58 | 8.13 | 5.51 | 44.98 |
| Acto 1 · C (176 est., 25k, mejor.pt) | 3 | 0.607 | 0.029 | 0.633 | 24.83 | 10.03 | 6.91 | 48.52 |
| Acto 1 · E (176 est., 25k, mejor.pt) | 3 | 0.596 | 0.051 | 0.644 | 28.55 | 9.47 | 8.80 | 58.36 |
| Extendido · A (825 est., 100k) | 3 | 0.660 | 0.005 | 0.717 | 26.57 | 6.27 | 3.61 | 39.56 |
| Extendido · A+ (825 est., 100k) | 3 | 0.662 | 0.011 | 0.714 | 23.51 | 5.71 | 4.57 | 39.35 |
| Extendido · B (825 est., 100k) | 3 | 0.698 | 0.006 | 0.742 | 18.88 | 4.39 | 2.73 | 29.14 |
| Extendido · C (825 est., 100k) | 3 | 0.695 | 0.005 | 0.734 | 18.94 | 5.30 | 2.61 | 29.26 |
| Extendido · B preentrenada (825 est., 100k) | 3 | 0.709 | 0.004 | 0.758 | 16.27 | 4.41 | 3.10 | 25.65 |
| Extendido · B pérdida pesada (1 sem.) | 1 | 0.700 |  | 0.748 | 17.38 | 4.08 | 2.25 | 27.29 |
| Extendido · B pre + pesada (1 sem.) | 1 | 0.688 |  | 0.750 | 17.94 | 4.10 | 2.01 | 29.63 |
| Miembros del ensamble, solos (media de 5) | 5 | 0.697 | 0.013 | 0.749 | 15.72 | 4.09 | 4.43 | 23.79 |
| Ensamble | 1 | 0.719 |  | 0.785 | 12.17 | 1.78 | 3.06 | 14.74 |
| **Ensamble + TTA (u 0,5, principal)** | 1 | 0.726 |  | 0.798 | 11.87 | 2.51 | 3.46 | 13.83 |
| Ensamble + TTA (u 0,7, secundario) | 1 | 0.724 |  | 0.783 | 7.39 | 0.70 | 8.07 | 6.42 |
| **Sistema final (H2)** | 1 | 0.727 |  | 0.806 | 9.50 | 1.27 | 3.95 | 9.57 |

## Comparaciones secundarias declaradas

| comparación | ΔDice⁺ | IC95 | gana | p | ΔFPV mL | IC95 | baja en | p |
|---|---|---|---|---|---|---|---|---|
| S1 · ensamble+TTA u 0,7 − B | +0.026 | [-0.002, +0.057] | 21/38 | 0.232 | -11.49 | [-20.09, -5.26] | 49/49 | 0.000 |
| S2 · ensamble+TTA − sus 5 miembros | +0.029 | [+0.019, +0.041] | 34/38 | 0.000 | -3.85 | [-6.18, -2.05] | 46/49 | 0.000 |
| S5 · acto 1: B − A | +0.015 | [-0.017, +0.054] | 19/38 | 0.989 | -14.86 | [-29.79, -3.21] | 25/49 | 0.174 |
| S5 · acto 1: C − A | -0.008 | [-0.040, +0.031] | 14/38 | 0.036 | -13.60 | [-27.91, -1.92] | 17/49 | 0.758 |
| S5 · acto 1: E − A | -0.020 | [-0.052, +0.013] | 11/38 | 0.014 | -9.89 | [-23.15, +1.00] | 29/49 | 0.184 |
| S6 · extendido: A+ − A | +0.001 | [-0.007, +0.009] | 23/38 | 0.350 | -3.06 | [-7.46, +0.31] | 27/49 | 0.247 |
| S6 · extendido: B − A | +0.038 | [+0.006, +0.076] | 27/38 | 0.003 | -7.69 | [-16.85, -1.62] | 30/49 | 0.011 |
| S6 · extendido: C − A | +0.034 | [+0.007, +0.069] | 28/38 | 0.003 | -7.63 | [-16.28, -1.84] | 33/49 | 0.002 |
| S7 · extendido: B preentrenada − B | +0.011 | [-0.002, +0.026] | 24/38 | 0.087 | -2.61 | [-5.39, -0.28] | 26/49 | 0.239 |

## S3 · Por lesión (lesiones fuera de la zona borrada; detectada = la toca alguna predicción)

| | detectadas | < 1 mL | 1–3 mL | 3–10 mL | > 10 mL | marcas falsas / estudio |
|---|---|---|---|---|---|---|
| B s423 | 337/435 (0.77) | 0.52 | 0.84 | 0.92 | 1.00 | 12.94 |
| B s2 | 327/435 (0.75) | 0.52 | 0.77 | 0.90 | 0.99 | 12.82 |
| B s3 | 332/435 (0.76) | 0.53 | 0.80 | 0.90 | 0.99 | 13.55 |
| Ensamble + TTA (u 0,5) | 330/435 (0.76) | 0.52 | 0.81 | 0.90 | 0.97 | 7.78 |
| Sistema final (H2) | 322/435 (0.74) | 0.50 | 0.79 | 0.87 | 0.97 | 6.31 |

## S4 · Falso positivo por órgano (mL por estudio, incluida la zona borrada)

| | B (3 sem.) | Ensamble + TTA (u 0,5) | Sistema final (H2) |
|---|---|---|---|
| órganos fisiológicos | 6.54 | 5.17 | 4.19 |
| tejido sin etiqueta + pulmón + bordes | 7.71 | 4.21 | 3.51 |
| total | 19.10 | 11.87 | 9.50 |

## S8 · Métrica cruda del reto autoPET (sin excluir la zona borrada)

| | Dice⁺ | FPV mL | FNV mL |
|---|---|---|---|
| B (3 sem.) | 0.674 | 19.10 | 3.71 |
| Ensamble + TTA (u 0,5) | 0.705 | 11.87 | 4.42 |
| Ensamble + TTA (u 0,7) | 0.701 | 7.39 | 8.91 |
| Sistema final (H2) | 0.705 | 9.50 | 4.90 |

Referencias publicadas del reto 2022 (su test, no el nuestro): ganador Dice 0,623 / FPV 2,84 mL; nnU-Net de base 0,690 / 5,78.
