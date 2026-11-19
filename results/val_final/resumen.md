# Resultados finales sobre `val`

*Generado por `scripts/37_analisis_final.py --particion val`. Lo que se mide y cómo se decide está en `docs/TEST_PREREGISTRO.md`, escrito antes de abrir el test.*

## Hipótesis principal (H1)

Ensamble de cinco pliegues + TTA, umbral 0,5, contra B (825 estudios, media de tres semillas). Se confirma si el IC95 de ΔDice⁺ queda entero sobre 0 **y** el de ΔFPV entero bajo 0.

| comparación | ΔDice⁺ | IC95 | gana | p | ΔFPV mL | IC95 | baja en | p |
|---|---|---|---|---|---|---|---|---|
| ensamble+TTA − B | +0.048 | [+0.023, +0.080] | 16/20 | 0.000 | -4.03 | [-6.65, -2.17] | 24/26 | 0.000 |

**Veredicto H1: CONFIRMADA.**

## Todos los brazos (métrica corregida)

| brazo | semillas | Dice⁺ | sd | mediana | FPV mL | FPV mediana | FNV mL | FPV en controles |
|---|---|---|---|---|---|---|---|---|
| Clásica (SUV ≥ 2,5) | 1 | 0.180 |  | 0.047 | 1191.87 | 798.27 | 5.59 | 1224.37 |
| Acto 1 · A (176 est., 25k, mejor.pt) | 3 | 0.621 | 0.016 | 0.699 | 20.93 | 6.39 | 6.02 | 36.33 |
| Acto 1 · B (176 est., 25k, mejor.pt) | 3 | 0.612 | 0.014 | 0.690 | 22.78 | 10.55 | 5.36 | 38.53 |
| Acto 1 · C (176 est., 25k, mejor.pt) | 3 | 0.612 | 0.008 | 0.689 | 23.18 | 6.78 | 5.93 | 44.70 |
| Acto 1 · E (176 est., 25k, mejor.pt) | 3 | 0.640 | 0.022 | 0.715 | 21.97 | 5.73 | 7.27 | 41.82 |
| Extendido · A (825 est., 100k) | 3 | 0.694 | 0.013 | 0.802 | 15.08 | 5.68 | 4.14 | 36.08 |
| Extendido · A+ (825 est., 100k) | 3 | 0.694 | 0.020 | 0.772 | 15.84 | 6.75 | 4.18 | 35.00 |
| Extendido · B (825 est., 100k) | 3 | 0.705 | 0.011 | 0.780 | 13.25 | 4.29 | 3.78 | 31.63 |
| Extendido · C (825 est., 100k) | 3 | 0.713 | 0.003 | 0.767 | 13.18 | 4.30 | 3.41 | 30.55 |
| Extendido · B preentrenada (825 est., 100k) | 3 | 0.707 | 0.014 | 0.778 | 12.71 | 4.23 | 3.62 | 27.53 |
| Extendido · B pérdida pesada (1 sem.) | 1 | 0.711 |  | 0.804 | 12.47 | 3.75 | 3.42 | 25.80 |
| Extendido · B pre + pesada (1 sem.) | 1 | 0.708 |  | 0.750 | 11.92 | 2.51 | 3.95 | 25.17 |
| Miembros del ensamble, solos (media de 5) | 5 | 0.718 | 0.024 | 0.791 | 11.85 | 3.33 | 4.09 | 26.80 |
| Ensamble | 1 | 0.744 |  | 0.821 | 9.96 | 1.30 | 3.93 | 24.62 |
| **Ensamble + TTA (u 0,5, principal)** | 1 | 0.754 |  | 0.821 | 9.21 | 1.17 | 3.83 | 23.29 |
| Ensamble + TTA (u 0,7, secundario) | 1 | 0.784 |  | 0.832 | 6.51 | 0.39 | 4.75 | 16.83 |

## Comparaciones secundarias declaradas

| comparación | ΔDice⁺ | IC95 | gana | p | ΔFPV mL | IC95 | baja en | p |
|---|---|---|---|---|---|---|---|---|
| S1 · ensamble+TTA u 0,7 − B | +0.079 | [+0.027, +0.140] | 12/20 | 0.058 | -6.73 | [-11.55, -3.59] | 25/26 | 0.000 |
| S2 · ensamble+TTA − sus 5 miembros | +0.036 | [+0.020, +0.054] | 19/20 | 0.000 | -2.64 | [-4.13, -1.44] | 24/26 | 0.000 |
| S5 · acto 1: B − A | -0.009 | [-0.055, +0.024] | 12/20 | 0.522 | +1.85 | [-4.08, +7.73] | 12/26 | 0.617 |
| S5 · acto 1: C − A | -0.009 | [-0.061, +0.030] | 9/20 | 0.869 | +2.25 | [-4.57, +8.72] | 14/26 | 0.822 |
| S5 · acto 1: E − A | +0.018 | [-0.020, +0.062] | 8/20 | 0.927 | +1.03 | [-5.20, +7.63] | 15/26 | 0.940 |
| S6 · extendido: A+ − A | +0.000 | [-0.015, +0.019] | 6/20 | 0.261 | +0.76 | [-1.01, +2.29] | 9/26 | 0.075 |
| S6 · extendido: B − A | +0.012 | [-0.005, +0.031] | 13/20 | 0.216 | -1.83 | [-4.95, +0.77] | 14/26 | 0.565 |
| S6 · extendido: C − A | +0.019 | [-0.006, +0.047] | 12/20 | 0.452 | -1.91 | [-5.19, +0.59] | 13/26 | 0.638 |
| S7 · extendido: B preentrenada − B | +0.002 | [-0.029, +0.036] | 10/20 | 0.784 | -0.54 | [-2.67, +1.77] | 14/26 | 0.380 |

## S3 · Por lesión (lesiones fuera de la zona borrada; detectada = la toca alguna predicción)

| | detectadas | < 1 mL | 1–3 mL | 3–10 mL | > 10 mL | marcas falsas / estudio |
|---|---|---|---|---|---|---|
| B s423 | 163/256 (0.64) | 0.31 | 0.73 | 0.91 | 1.00 | 4.77 |
| B s2 | 160/256 (0.62) | 0.28 | 0.71 | 0.95 | 1.00 | 4.88 |
| B s3 | 158/256 (0.62) | 0.27 | 0.72 | 0.91 | 1.00 | 5.81 |
| Ensamble + TTA (u 0,5) | 160/256 (0.62) | 0.28 | 0.72 | 0.93 | 1.00 | 2.81 |

## S4 · Falso positivo por órgano (mL por estudio, incluida la zona borrada)

| | B (3 sem.) | Ensamble + TTA (u 0,5) |
|---|---|---|
| órganos fisiológicos | 2.55 | 1.41 |
| tejido sin etiqueta + pulmón + bordes | 11.18 | 7.90 |
| total | 14.19 | 9.61 |

## S8 · Métrica cruda del reto autoPET (sin excluir la zona borrada)

| | Dice⁺ | FPV mL | FNV mL |
|---|---|---|---|
| B (3 sem.) | 0.637 | 14.19 | 5.85 |
| Ensamble + TTA (u 0,5) | 0.687 | 9.61 | 5.90 |
| Ensamble + TTA (u 0,7) | 0.718 | 6.61 | 6.77 |

Referencias publicadas del reto 2022 (su test, no el nuestro): ganador Dice 0,623 / FPV 2,84 mL; nnU-Net de base 0,690 / 5,78.
