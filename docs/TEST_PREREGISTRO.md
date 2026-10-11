# Preregistro del test

*2026-10-11. Escrito y commiteado antes de abrir el conjunto de prueba. `scripts/35_test_final.sh`
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

## Secundarias declaradas (se reportan todas, ninguna rescata a H1)

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

    caffeinate -i bash scripts/35_test_final.sh 2>&1 | tee -a runs/test_final.log

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
