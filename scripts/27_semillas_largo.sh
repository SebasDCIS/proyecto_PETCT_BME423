#!/bin/bash
# Rama `extendido`. Todo lo que falta para afirmar la inversión de arquitecturas con el
# rigor de la Parte 1: tres semillas por brazo en el régimen de 100 000 iteraciones, más
# el control de capacidad A+ (fusión temprana con los parámetros de B), que separa
# "codificador dual" de "simplemente más red".
#
# Reanudable. 07_entrenar.py retoma solo desde runs/<x>/ultimo.pt; cada evaluación se
# salta si su tabla ya existe. Se puede cortar con Ctrl-C y relanzar cuando sea.
#
# Orden pensado para que cualquier corte parcial deje comparaciones completas:
#   etapa 0  evaluaciones que faltan de las tres corridas largas ya hechas
#   etapa 1  A_s2, B_s2, C_s2      (segunda semilla de los tres brazos)
#   etapa 2  A+ s423               (control de capacidad)
#   etapa 3  A_s3, B_s3, C_s3      (tercera semilla)
#   etapa 4  A+ s2, A+ s3          (el control con el mismo rigor que los brazos)
#
# Costo: ~10 días de Mac. Lanzar con:
#   caffeinate -i bash scripts/27_semillas_largo.sh 2>&1 | tee -a runs/semillas_largo.log
set -u
cd "$(dirname "$0")/.."
MAN=data/manifests/subconjunto_extendido.csv
IT=100000

hora() { date "+%Y-%m-%d %H:%M"; }

entrenar() {  # modelo semilla carpeta
  if [ -f "runs/$3/resumen.json" ]; then echo "[$(hora)] $3 ya entrenado"; return 0; fi
  echo "[$(hora)] ENTRENAR $3 (modelo $1, semilla $2, $IT iteraciones)"
  python scripts/07_entrenar.py --modelo "$1" --semilla "$2" --manifest "$MAN" \
    --iteraciones "$IT" --salida "runs/$3"
}

evaluar() {  # modelo carpeta etiqueta [flags...]
  local m=$1 d=$2 e=$3; shift 3
  if [ -f "results/${e}_val.csv" ]; then echo "[$(hora)] results/${e}_val.csv ya existe"; return 0; fi
  echo "[$(hora)] EVALUAR $e"
  python scripts/09_evaluar.py --modelo "$m" --checkpoint "runs/$d/ultimo.pt" \
    --particion val --manifest "$MAN" --etiqueta "$e" "$@"
}

mascaras() {  # modelo carpeta  (las máscaras alimentan el análisis por órgano y el FROC)
  if [ -d "runs/$2/mascaras_val" ]; then echo "[$(hora)] runs/$2/mascaras_val ya existe"; return 0; fi
  echo "[$(hora)] MASCARAS $2"
  python scripts/09_evaluar.py --modelo "$1" --checkpoint "runs/$2/ultimo.pt" \
    --particion val --manifest "$MAN" --etiqueta "modelo_${2}_ultimo_masc" --guardar-mascaras \
    --salida "runs/$2/_eval_mascaras.csv"
}

completo() {  # modelo carpeta etiqueta_base
  evaluar "$1" "$2" "${3}_ultimo"
  evaluar "$1" "$2" "${3}_ultimo_crudo" --incluir-zona-borrada     # la métrica del reto, sin corrección
  mascaras "$1" "$2"
  if [ "$1" = "C" ]; then evaluar "$1" "$2" "${3}_sin_atencion" --sin-atencion; fi
  return 0
}

echo "======== [$(hora)] etapa 0: completar las tres corridas largas existentes"
completo A A_ext_largo modelo_A_ext_largo
completo B B_ext_largo modelo_B_ext_largo
completo C C_ext_largo modelo_C_ext_largo

echo "======== [$(hora)] etapa 1: segunda semilla"
entrenar A 2 A_ext_largo_s2 && completo A A_ext_largo_s2 modelo_A_ext_largo_s2
entrenar B 2 B_ext_largo_s2 && completo B B_ext_largo_s2 modelo_B_ext_largo_s2
entrenar C 2 C_ext_largo_s2 && completo C C_ext_largo_s2 modelo_C_ext_largo_s2

echo "======== [$(hora)] etapa 2: control de capacidad A+ (24,3 M, los parámetros de B)"
entrenar A+ 423 Aplus_ext_largo && completo A+ Aplus_ext_largo modelo_Aplus_ext_largo

echo "======== [$(hora)] etapa 3: tercera semilla"
entrenar A 3 A_ext_largo_s3 && completo A A_ext_largo_s3 modelo_A_ext_largo_s3
entrenar B 3 B_ext_largo_s3 && completo B B_ext_largo_s3 modelo_B_ext_largo_s3
entrenar C 3 C_ext_largo_s3 && completo C C_ext_largo_s3 modelo_C_ext_largo_s3

echo "======== [$(hora)] etapa 4: segunda y tercera semilla del control A+"
entrenar A+ 2 Aplus_ext_largo_s2 && completo A+ Aplus_ext_largo_s2 modelo_Aplus_ext_largo_s2
entrenar A+ 3 Aplus_ext_largo_s3 && completo A+ Aplus_ext_largo_s3 modelo_Aplus_ext_largo_s3

echo "======== [$(hora)] TODO LISTO"
