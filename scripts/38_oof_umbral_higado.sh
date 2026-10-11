#!/bin/bash
# Rama `extendido`, paso 5 (antes del test): decidir el umbral y la regla del hígado con los
# 825 estudios fuera de pliegue, no con los 26 de validación. Ver docs/TEST_PREREGISTRO.md.
#
#   1. Mapas de órganos y referencias ya existen para train y val (scripts/30).
#   2. Cada miembro B_ens_k predice, con TTA, su pliegue no visto, guardando probabilidades.
#   3. scripts/39 barre umbrales con y sin la regla del hígado, aplica la regla de decisión
#      declarada y escribe results/oof_umbral/decision.json (lo lee scripts/35 para el test).
#   4. Comprobación en validación sobre el ensamble real (no decide nada).
#
# Reanudable. Unas 5 horas.   caffeinate -i bash scripts/38_oof_umbral_higado.sh 2>&1 | tee -a runs/oof_umbral.log
set -u
cd "$(dirname "$0")/.."
hora() { date "+%Y-%m-%d %H:%M"; }

echo "======== [$(hora)] probabilidades fuera de pliegue (cinco miembros, TTA)"
for k in 0 1 2 3 4; do
  e=oof_B_ens_$k
  if [ -f "results/${e}_oof.csv" ]; then echo "[$(hora)] $e ya existe"; continue; fi
  echo "[$(hora)] PREDECIR $e (pliegue $k, ~165 estudios)"
  python scripts/33_ensamble.py --modelo B --checkpoints "runs/B_ens_$k/ultimo.pt" --particion oof \
    --manifest "data/manifests/_pliegues/pliegue_$k.csv" --etiqueta "$e" --tta --guardar-probabilidades
done

echo "======== [$(hora)] decisión con los 825 (regla fijada antes)"
[ -f results/oof_umbral/decision.json ] || python scripts/39_decidir_umbral_higado.py --particion oof
cat results/oof_umbral/decision.json

echo "======== [$(hora)] comprobación en validación (ensamble real; no decide)"
[ -f results/val_umbral/barrido.csv ] || python scripts/39_decidir_umbral_higado.py --particion val \
  --probabilidades runs/ensambles/ensamble_B_ens_tta/probabilidades_val
echo "======== [$(hora)] TODO LISTO — revisar con Claude antes de abrir el test"
