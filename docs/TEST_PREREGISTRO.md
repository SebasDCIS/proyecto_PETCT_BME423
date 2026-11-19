# Preregistro del test

*2026-10-11, ampliado el mismo día con la sección "Umbral y regla del hígado". Escrito y commiteado antes de abrir el conjunto de prueba. `scripts/35_test_final.sh`
se niega a correr si este archivo o el script de análisis tienen cambios sin commitear, y deja en
`results/test/APERTURA.txt` la fecha de apertura y el commit de este documento.*

## Qué es el test y en qué estado está

49 estudios de 49 pacientes (13 pulmón, 13 linfoma, 13 melanoma, 10 controles), sorteados el
4 de septiembre con semilla 423 y estratificados por diagnóstico. Son los mismos en `main` y en
`extendido` (verificado: los dos manifiestos coinciden). **Ningún modelo se ha evaluado nunca
sobre ellos**: no existe ninguna tabla `*_test.csv` ni carpeta `mascaras_test`.

Una sola excepción, declarada: la referencia clásica (umbral SUV ≥ 2,5 + apertura + tamaño
mínimo) se midió el 5 de septiembre sobre los 251 estudios del sorteo, test incluido, y esas 49
filas están en `results/referencia_clasica.csv` desde entonces. Es una regla con constantes fijas
de la literatura, sin nada ajustado a los datos, y ninguna decisión del proyecto usó esas filas.
Se reporta tal cual.

Los mapas de órganos (TotalSegmentator) y la referencia interna del modelo E se calculan para el
test en la primera etapa: los dos salen solo del CT y del PET, sin mirar la anotación.

## Qué se evalúa (todo con los checkpoints que ya existen; no se entrena nada)

| grupo | corridas | checkpoint |
|---|---|---|
| Acto 1 (`main`) | A, B, C, E × 3 semillas (176 estudios, 25 000 iteraciones) | `mejor.pt` (el del protocolo congelado) y, aparte, `ultimo.pt` |
| Rama extendido | A, A+, B, C, B preentrenada × 3 semillas; B pérdida pesada y B pre + pesada × 1 (825 estudios, 100 000 iteraciones) | `ultimo.pt` |
| Ensamble | los 5 miembros solos, y el ensamble sin y con TTA | `ultimo.pt` de `B_ens_0`…`B_ens_4` |
| Referencia | clásica | — |

Métrica corregida (sin la zona borrada) como principal; la cruda del reto como secundaria.
Mismas funciones de métrica que en validación (`petct.metrics.evaluate_study`).

## Hipótesis principal (una sola)

**H1. El ensamble de cinco pliegues con TTA, a umbral 0,5, mejora a B en el test.** Referencia:
B con 825 estudios, media estudio a estudio de sus tres semillas. Comparación pareada por estudio,
IC95 por bootstrap (10 000 remuestreos, semilla 423). **Se confirma solo si las dos cosas se
cumplen:** el IC95 de ΔDice⁺ (en los positivos) queda entero sobre 0, **y** el IC95 de ΔFPV (en
los 49) queda entero bajo 0. Si falla cualquiera de las dos, H1 no se confirma y se dice así.

En validación esta comparación dio ΔDice⁺ +0,048 [+0,023, +0,080] y ΔFPV −4,0 mL [−6,6, −2,2].
El test tiene 39 positivos (casi el doble que validación), así que si el efecto es real debería
verse; si no se ve, el de validación fue optimista.

## Umbral y regla del hígado: se deciden con los 825 fuera de pliegue (agregado antes de abrir)

Dos mejoras baratas con respaldo previo se deciden **antes** del test y **sin** la validación de
26, con una regla fijada aquí antes de ver ningún número (`scripts/38` y `39`):

- **Fuente.** Cada estudio de entrenamiento predicho con TTA por el único miembro del ensamble
  que no lo vio (825 estudios, ~420 positivos). Es un sustituto del ensamble: en entrenamiento no
  hay cinco miembros ciegos para promediar. Declarado como limitación.
- **Umbral.** Grilla 0,3 · 0,4 · 0,5 · 0,6 · 0,7 · 0,8. Se elige el de mayor Dice⁺ entre los que
  detectan como máximo 2 puntos porcentuales menos de lesiones que 0,5 (empate → el más alto).
- **Regla del hígado** (`petct.postproc`, la misma de `experimentos/23`): borrar cada isla cuyo
  SUV máximo no llegue a 2 × la mediana del hígado del propio paciente (calculada sin la
  anotación). Se adopta, sobre el umbral elegido, solo si baja las marcas falsas por estudio al
  menos un 25 %, pierde como máximo el 3 % de las lesiones detectadas y no baja el Dice⁺ más de
  0,005. Si no, el sistema final no la usa.
- El resultado queda en `results/oof_umbral/decision.json`, que se commitea antes de abrir el
  test: `scripts/35` se niega a correr sin él. La validación de 26 se mira después solo como
  comprobación, sin poder cambiar la decisión.

**H2. El sistema final** (ensamble + TTA con ese umbral y, si se adopta, esa regla) **mejora a B
en el test**, con la misma regla de confirmación que H1. H1 se mantiene tal como se declaró. Si
la decisión resulta ser umbral 0,5 sin regla, H2 es idéntica a H1 y se reporta una vez.

### La decisión, tomada el 2026-10-11 (antes de abrir el test)

`scripts/38` corrió los cinco miembros sobre sus pliegues con TTA (5 h 30) y `scripts/39` aplicó la
regla. Sobre los 825 estudios (6 618 lesiones):

| umbral | regla del hígado | Dice⁺ | FPV mL | lesiones detectadas | marcas falsas / estudio |
|---|---|---|---|---|---|
| 0,5 | no | 0,698 | 13,46 | 63,1 % | 5,41 |
| **0,6** | **no** | **0,699** | **11,91** | **61,9 %** | **4,83** |
| 0,7 | no | 0,698 | 10,81 | 60,7 % (fuera: pierde 2,4 pp) | 4,35 |
| 0,6 | sí | 0,694 | 11,56 | 58,0 % | 3,76 |

- **Umbral elegido: 0,6.** Es el de mayor Dice⁺ entre los que no pierden más de 2 puntos de
  detección respecto de 0,5 (0,7 pierde 2,4). En Dice la diferencia con 0,5 es nula (+0,0005);
  lo que cambia es el falso positivo (−1,5 mL, −11 % de marcas falsas) a cambio de 1,2 puntos
  de lesiones detectadas.
- **Regla del hígado: no se adopta.** Baja las marcas falsas solo 22 % (pedía ≥ 25 %) y pierde el
  6,4 % de las lesiones detectadas (permitía ≤ 3 %). Lo que en el acto 1 parecía −40 % de marcas
  con −2,3 % de lesiones no se repite con un modelo mejor y 32 veces más estudios.
- **Por qué valió la pena hacerlo con los 825:** en los 26 de validación el Dice sube de 0,754 a
  0,784 entre 0,5 y 0,7; en los 825 queda plano (0,698 → 0,698). La mejora de Dice que mostraba
  el umbral alto en validación era en buena parte ruido de 26 estudios. La comprobación en
  validación (`results/val_umbral/barrido.csv`), aplicando la misma regla, habría elegido lo mismo:
  umbral 0,6 y sin regla del hígado.

Por lo tanto **H2 = ensamble + TTA a umbral 0,6, sin regla del hígado**, contra B.

## Secundarias declaradas (se reportan todas, ninguna rescata a H1 ni a H2)

- **S1.** El mismo ensamble a umbral 0,7, contra B. El umbral 0,7 se miró en validación (Dice⁺
  0,784, FPV 6,5 mL); el test dice si esa mejora era real o un ajuste a 26 estudios.
- **S2.** Ensamble + TTA contra la media de sus cinco miembros solos: atribuye la mejora al voto.
- **S3.** Por lesión: lesiones detectadas por tamaño y marcas falsas por estudio (B × 3 y ensamble).
- **S4.** Falso positivo por órgano (B × 3 y ensamble).
- **S5.** Acto 1: B − A, C − A, E − A. La conclusión de `main` ("las fusiones empatan") se
  sostiene en el test si los tres intervalos cruzan el cero.
- **S6.** Extendido: A+ − A, B − A, C − A. Descriptivo: en validación ninguno fue significativo.
- **S7.** Extendido: B preentrenada − B (negativo en validación).
- **S8.** Métrica cruda del reto para B, ensamble u 0,5 y u 0,7, con las referencias publicadas
  del reto 2022 al lado (que son de su test, no del nuestro).

Lo que **no** se hará después de ver el test: elegir otro umbral, otro checkpoint, otro
subconjunto de estudios o excluir casos. Si un caso resulta anómalo (como el control de 2,4 L
del pliegue 0), se describe, pero queda en todos los promedios.

## Cómo se corre y cuánto tarda

    caffeinate -i bash scripts/38_oof_umbral_higado.sh 2>&1 | tee -a runs/oof_umbral.log   # antes: la decisión (~5 h)
    caffeinate -i bash scripts/35_test_final.sh 2>&1 | tee -a runs/test_final.log    # después: el test (~5 h)

Etapas: mapas de órganos del test (~20 min) · acto 1, 24 evaluaciones (~1,5 h) · extendido, 17
evaluaciones (~1,2 h) · cinco miembros (~20 min) · ensamble sin y con TTA (~1,5 h) · análisis
(~5 min). Total ≈ 5 horas. Reanudable. El análisis (`scripts/37_analisis_final.py`) se probó el
2026-10-11 sobre validación y reproduce exactamente las tablas ya publicadas de los pasos 2 a 4.

## Después del test

El resultado decide qué se cuenta, no si se cuenta. Si H1 se confirma, el ensamble pasa a ser el
resultado principal de la rama y cumple la regla de fusión con `main` (supera el ruido entre
semillas, partición intacta, test abierto una vez). Si no, el informe dice que la mejora de
validación no se replicó, y el resultado principal sigue siendo B. En los dos casos el test queda
abierto y ya no sirve para decidir nada más; lo que venga después (2 mm, autoPET 2027) necesitará
otra forma de validarse.
