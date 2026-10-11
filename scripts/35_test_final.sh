#!/bin/bash
# Rama `extendido`, paso 5: ABRIR EL TEST. Una sola vez, con todo decidido de antemano en
# docs/TEST_PREREGISTRO.md. Evalúa los 49 estudios de prueba con todos los brazos del proyecto
# (acto 1 y rama extendido) y deja el análisis declarado en results/test_final/resumen.md.
#
# Se niega a correr si el preregistro y el script de análisis no están commiteados tal cual.
# La primera vez escribe results/test/APERTURA.txt con la fecha y el commit: esa es la marca de
# que el test se abrió. Reanudable como los anteriores (cada paso se salta si su tabla existe).
#
#   caffeinate -i bash scripts/35_test_final.sh 2>&1 | tee -a runs/test_final.log
#
# Compatible con el bash 3.2 del Mac: sin arreglos asociativos ni arreglos vacíos bajo set -u.
set -u
cd "$(dirname "$0")/.."
MAN=data/manifests/subconjunto_extendido.csv
hora() { date "+%Y-%m-%d %H:%M"; }

# ---------------------------------------------------------------- el candado
for f in docs/TEST_PREREGISTRO.md scripts/37_analisis_final.py scripts/35_test_final.sh results/oof_umbral/decision.json; do
  git ls-files --error-unmatch "$f" >/dev/null 2>&1 || { echo "$f no está en git: commitea el preregistro antes de abrir el test"; exit 1; }
  git diff --quiet HEAD -- "$f" || { echo "$f tiene cambios sin commitear: el test se abre solo con lo declarado"; exit 1; }
done
mkdir -p results/test
if [ ! -f results/test/APERTURA.txt ]; then
  { echo "Test abierto: $(date -u '+%Y-%m-%d %H:%M UTC')"; echo "Commit del preregistro: $(git rev-parse HEAD)"; } > results/test/APERTURA.txt
  echo "[$(hora)] TEST ABIERTO. $(cat results/test/APERTURA.txt | tr '\n' ' ')"
else
  echo "[$(hora)] reanudando; $(head -1 results/test/APERTURA.txt)"
fi

evaluar() {  # modelo carpeta checkpoint etiqueta [--guardar-mascaras]
  local m=$1 d=$2 ck=$3 e=$4; shift 4
  if [ -f "results/${e}_test.csv" ]; then echo "[$(hora)] results/${e}_test.csv ya existe"; return 0; fi
  echo "[$(hora)] EVALUAR $e"
  python scripts/09_evaluar.py --modelo "$m" --checkpoint "runs/$d/$ck" --particion test --manifest "$MAN" --etiqueta "$e" "$@"
}
crudo_desde_mascaras() {  # carpeta etiqueta
  if [ -f "results/${2}_test.csv" ]; then return 0; fi
  python scripts/36_reevaluar_guardado.py --mascaras "runs/$1/mascaras_test" --etiqueta "$2" --particion test --incluir-zona-borrada
}

echo "======== [$(hora)] etapa 1: mapas de órganos y referencias internas del test (no usan la anotación)"
python scripts/11_organos_totalsegmentator.py --manifest "$MAN" --particion test
python scripts/19_referencias_internas.py --manifest "$MAN" --particion test

echo "======== [$(hora)] etapa 2: acto 1 (176 estudios, 25 000 iteraciones), mejor.pt (protocolo) y ultimo.pt"
for par in A:A A:A_s2 A:A_s3 B:B B:B_s2 B:B_s3 C:C C:C_s2 C:C_s3 E:E E:E_s2 E:E_s3; do
  m=${par%%:*}; d=${par#*:}
  evaluar "$m" "$d" mejor.pt "modelo_${d}" --guardar-mascaras
  evaluar "$m" "$d" ultimo.pt "modelo_${d}_ultimo"
done

echo "======== [$(hora)] etapa 3: rama extendido (825 estudios, 100 000 iteraciones), ultimo.pt"
for par in A:A_ext_largo A:A_ext_largo_s2 A:A_ext_largo_s3 A+:Aplus_ext_largo A+:Aplus_ext_largo_s2 A+:Aplus_ext_largo_s3 \
           B:B_ext_largo B:B_ext_largo_s2 B:B_ext_largo_s3 C:C_ext_largo C:C_ext_largo_s2 C:C_ext_largo_s3 \
           B:B_ext_largo_pre B:B_ext_largo_pre_s2 B:B_ext_largo_pre_s3 B:B_ext_largo_peso B:B_ext_largo_pre_peso; do
  m=${par%%:*}; d=${par#*:}
  evaluar "$m" "$d" ultimo.pt "modelo_${d}_ultimo" --guardar-mascaras
  crudo_desde_mascaras "$d" "modelo_${d}_ultimo_crudo"
done

echo "======== [$(hora)] etapa 4: los cinco miembros del ensamble, cada uno solo"
for k in 0 1 2 3 4; do evaluar B "B_ens_$k" ultimo.pt "modelo_B_ens_${k}_ultimo"; done

echo "======== [$(hora)] etapa 5: el ensamble (principal: + TTA, umbral 0,5)"
CKS="runs/B_ens_0/ultimo.pt runs/B_ens_1/ultimo.pt runs/B_ens_2/ultimo.pt runs/B_ens_3/ultimo.pt runs/B_ens_4/ultimo.pt"
if [ ! -f results/ensamble_B_ens_test.csv ]; then
  echo "[$(hora)] ENSAMBLE ensamble_B_ens"
  python scripts/33_ensamble.py --modelo B --checkpoints $CKS --particion test --manifest "$MAN" --etiqueta ensamble_B_ens
fi
if [ ! -f results/ensamble_B_ens_tta_test.csv ]; then
  echo "[$(hora)] ENSAMBLE ensamble_B_ens_tta (principal)"
  python scripts/33_ensamble.py --modelo B --checkpoints $CKS --particion test --manifest "$MAN" --etiqueta ensamble_B_ens_tta \
    --tta --guardar-mascaras --guardar-probabilidades
fi
PROB=runs/ensambles/ensamble_B_ens_tta/probabilidades_test
[ -f results/ensamble_B_ens_tta_crudo_test.csv ] || python scripts/36_reevaluar_guardado.py --probabilidades $PROB --umbral 0.5 --etiqueta ensamble_B_ens_tta_crudo --particion test --incluir-zona-borrada
[ -f results/ensamble_B_ens_tta_u07_test.csv ] || python scripts/36_reevaluar_guardado.py --probabilidades $PROB --umbral 0.7 --etiqueta ensamble_B_ens_tta_u07 --particion test
[ -f results/ensamble_B_ens_tta_u07_crudo_test.csv ] || python scripts/36_reevaluar_guardado.py --probabilidades $PROB --umbral 0.7 --etiqueta ensamble_B_ens_tta_u07_crudo --particion test --incluir-zona-borrada

echo "======== [$(hora)] etapa 5b: el sistema final (umbral y regla del hígado decididos en los 825 fuera de pliegue)"
U=$(python -c "import json; print(json.load(open('results/oof_umbral/decision.json'))['umbral'])")
H=$(python -c "import json; d=json.load(open('results/oof_umbral/decision.json')); print(d['k_higado'] if d['regla_higado'] else '')")
echo "[$(hora)] umbral $U; regla del hígado: ${H:-no}"
REGLA=""; [ -n "$H" ] && REGLA="--regla-higado $H"
[ -f results/ensamble_final_test.csv ] || python scripts/36_reevaluar_guardado.py --probabilidades $PROB --umbral "$U" $REGLA \
  --etiqueta ensamble_final --particion test --guardar-mascaras runs/ensambles/ensamble_final/mascaras_test
[ -f results/ensamble_final_crudo_test.csv ] || python scripts/36_reevaluar_guardado.py --probabilidades $PROB --umbral "$U" $REGLA \
  --etiqueta ensamble_final_crudo --particion test --incluir-zona-borrada

echo "======== [$(hora)] etapa 6: el análisis declarado"
python scripts/37_analisis_final.py --particion test
echo "======== [$(hora)] TODO LISTO — resultados en results/test_final/resumen.md"
