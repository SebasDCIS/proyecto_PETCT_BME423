# Reanálisis sin entrenar (fallas de la revisión crítica)

*Generado por `scripts/44_reanalisis_sin_entrenar.py`. Análisis secundario, posterior a la apertura de la prueba; no cambia el preregistro ni los veredictos de H1 y H2.*

## 1. Acto 1 en validación sin la fuga del checkpoint

`mejor.pt` se eligió con los primeros 12 estudios de validación. Media de tres semillas.

| brazo | checkpoint | estudios | positivos | Dice⁺ | FPV mL |
|---|---|---|---|---|---|
| A | `mejor.pt` | 26 (todos) | 20 | 0,621 | 20,9 |
| A | `mejor.pt` | 12 usados para elegir | 9 | 0,631 | 11,8 |
| A | `mejor.pt` | 14 no usados | 11 | 0,614 | 28,8 |
| A | `ultimo.pt` | 26 (todos) | 20 | 0,615 | 21,7 |
| A | `ultimo.pt` | 12 usados para elegir | 9 | 0,618 | 12,6 |
| A | `ultimo.pt` | 14 no usados | 11 | 0,612 | 29,5 |
| B | `mejor.pt` | 26 (todos) | 20 | 0,612 | 22,8 |
| B | `mejor.pt` | 12 usados para elegir | 9 | 0,586 | 18,9 |
| B | `mejor.pt` | 14 no usados | 11 | 0,634 | 26,1 |
| B | `ultimo.pt` | 26 (todos) | 20 | 0,607 | 22,1 |
| B | `ultimo.pt` | 12 usados para elegir | 9 | 0,545 | 19,7 |
| B | `ultimo.pt` | 14 no usados | 11 | 0,658 | 24,1 |
| C | `mejor.pt` | 26 (todos) | 20 | 0,612 | 23,2 |
| C | `mejor.pt` | 12 usados para elegir | 9 | 0,594 | 21,5 |
| C | `mejor.pt` | 14 no usados | 11 | 0,627 | 24,7 |
| C | `ultimo.pt` | 26 (todos) | 20 | 0,610 | 21,5 |
| C | `ultimo.pt` | 12 usados para elegir | 9 | 0,560 | 17,4 |
| C | `ultimo.pt` | 14 no usados | 11 | 0,650 | 25,0 |
| E | `mejor.pt` | 26 (todos) | 20 | 0,640 | 22,0 |
| E | `mejor.pt` | 12 usados para elegir | 9 | 0,692 | 14,4 |
| E | `mejor.pt` | 14 no usados | 11 | 0,597 | 28,4 |
| E | `ultimo.pt` | 26 (todos) | 20 | 0,638 | 23,6 |
| E | `ultimo.pt` | 12 usados para elegir | 9 | 0,648 | 15,4 |
| E | `ultimo.pt` | 14 no usados | 11 | 0,630 | 30,7 |

Comparación pareada contra A en los 14 estudios no usados (`mejor.pt`, Dice⁺):

| comparación | positivos | ΔDice⁺ | IC95 |
|---|---|---|---|
| B − A | 11 | +0,020 | [+0,000, +0,045] |
| C − A | 11 | +0,013 | [-0,018, +0,048] |
| E − A | 11 | -0,017 | [-0,048, +0,012] |

## 2 y 3. Comparaciones de la prueba: IC jerárquico y Holm

IC simple: bootstrap de pacientes sobre el promedio de semillas (el del preregistro). IC jerárquico: remuestrea pacientes y semillas. Holm: sobre las 18 pruebas secundarias (9 comparaciones × 2 métricas).

| comparación | métrica | Δ | IC simple | IC jerárquico | p Wilcoxon | p Holm |
|---|---|---|---|---|---|---|
| H1 · ensamble + TTA − B | Dice⁺ | +0,028 | [+0,011, +0,048] | [+0,009, +0,050] | 0,000 |  |
| H1 · ensamble + TTA − B | FPV | -7,01 | [-12,40, -3,34] | [-13,33, -2,98] | 0,000 |  |
| H2 · sistema final − B | Dice⁺ | +0,029 | [+0,007, +0,053] | [+0,005, +0,055] | 0,026 |  |
| H2 · sistema final − B | FPV | -9,38 | [-16,44, -4,45] | [-17,21, -4,23] | 0,000 |  |
| S1 · ensamble + TTA u 0,7 − B | Dice⁺ | +0,026 | [-0,003, +0,056] | [-0,004, +0,058] | 0,232 | 1,000 |
| S1 · ensamble + TTA u 0,7 − B | FPV | -11,49 | [-20,26, -5,33] | [-20,53, -5,10] | 0,000 | 0,000 |
| S2 · ensamble + TTA − sus 5 miembros | Dice⁺ | +0,029 | [+0,019, +0,041] | [+0,015, +0,049] | 0,000 | 0,000 |
| S2 · ensamble + TTA − sus 5 miembros | FPV | -3,85 | [-6,18, -2,04] | [-9,43, +1,61] | 0,000 | 0,000 |
| S5 · acto 1: B − A | Dice⁺ | +0,015 | [-0,017, +0,054] | [-0,031, +0,061] | 0,989 | 1,000 |
| S5 · acto 1: B − A | FPV | -14,86 | [-30,13, -3,22] | [-31,20, -2,08] | 0,174 | 1,000 |
| S5 · acto 1: C − A | Dice⁺ | -0,008 | [-0,041, +0,031] | [-0,059, +0,038] | 0,036 | 0,357 |
| S5 · acto 1: C − A | FPV | -13,60 | [-28,33, -2,16] | [-30,99, +0,37] | 0,758 | 1,000 |
| S5 · acto 1: E − A | Dice⁺ | -0,020 | [-0,053, +0,013] | [-0,087, +0,032] | 0,014 | 0,156 |
| S5 · acto 1: E − A | FPV | -9,89 | [-23,44, +1,24] | [-26,28, +2,52] | 0,184 | 1,000 |
| S6 · extendido: A+ − A | Dice⁺ | +0,001 | [-0,007, +0,009] | [-0,017, +0,016] | 0,350 | 1,000 |
| S6 · extendido: A+ − A | FPV | -3,06 | [-7,51, +0,28] | [-8,50, +1,95] | 0,247 | 1,000 |
| S6 · extendido: B − A | Dice⁺ | +0,038 | [+0,006, +0,077] | [+0,005, +0,079] | 0,003 | 0,037 |
| S6 · extendido: B − A | FPV | -7,69 | [-16,94, -1,63] | [-17,09, -0,76] | 0,011 | 0,128 |
| S6 · extendido: C − A | Dice⁺ | +0,034 | [+0,006, +0,070] | [+0,004, +0,071] | 0,003 | 0,037 |
| S6 · extendido: C − A | FPV | -7,63 | [-16,37, -1,88] | [-16,75, -1,49] | 0,002 | 0,029 |
| S7 · extendido: B preentrenada − B | Dice⁺ | +0,011 | [-0,002, +0,026] | [-0,007, +0,030] | 0,087 | 0,784 |
| S7 · extendido: B preentrenada − B | FPV | -2,61 | [-5,38, -0,27] | [-6,97, +0,53] | 0,239 | 1,000 |

## 4. Ensamble + TTA contra B + TTA

B + TTA (media de tres semillas): Dice⁺ 0,709; FPV 17,57 mL.

| métrica | Δ (ensamble+TTA − B+TTA) | IC jerárquico | p Wilcoxon |
|---|---|---|---|
| Dice⁺ | +0,018 | [+0,004, +0,035] | 0,001 |
| FPV | -5,70 | [-11,42, -2,20] | 0,000 |
