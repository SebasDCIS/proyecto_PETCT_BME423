#!/bin/bash
# Rama `extendido`, paso 3, hipótesis declarada el 2026-10-01 (docs/PASO3_ANATOMIA.md):
# ¿el Dice 0,724 de B con codificador preentrenado se repite? Semillas 2 y 3 de B_pre, con el
# mismo enc_ct.pt y la misma receta que B_ext_largo_s2/_s3. Se acepta solo si AMBAS dan
# Dice⁺ ≥ 0,716 y FPV ≤ 14,5 mL. Reanudable como el 27 y el 30.
#
# Con --esperar se queda en cola detrás de scripts/30 (espera las máscaras de B_pre_peso):
#   caffeinate -i bash scripts/31_anatomia_semillas.sh --esperar 2>&1 | tee -a runs/anatomia_semillas.log
set -u
cd "$(dirname "$0")/.."
MAN=data/manifests/subconjunto_extendido.csv
IT=100000
ENC=runs/ct_anatomia/enc_ct.pt

hora() { date "+%Y-%m-%d %H:%M"; }

if [ "${1:-}" = "--esperar" ]; then
  echo "[$(hora)] esperando a que scripts/30 termine (runs/B_ext_largo_pre_peso/mascaras_val)"
  while [ ! -d runs/B_ext_largo_pre_peso/mascaras_val ]; do sleep 600; done
  sleep 300    # deja que el 30 termine su análisis por órgano antes de tomar la GPU
  echo "[$(hora)] el 30 terminó; empiezan las semillas de B_pre"
fi
[ -f "$ENC" ] || { echo "[$(hora)] falta $ENC"; exit 1; }

entrenar() {  # semilla carpeta
  if [ -f "runs/$2/resumen.json" ]; then echo "[$(hora)] $2 ya entrenado"; return 0; fi
  echo "[$(hora)] ENTRENAR $2 (B, semilla $1, $IT iteraciones, enc_ct preentrenado)"
  python scripts/07_entrenar.py --modelo B --semilla "$1" --manifest "$MAN" \
    --iteraciones "$IT" --salida "runs/$2" --enc-ct-preentrenado "$ENC"
}

evaluar() {  # carpeta etiqueta [flags...]
  local d=$1 e=$2; shift 2
  if [ -f "results/${e}_val.csv" ]; then echo "[$(hora)] results/${e}_val.csv ya existe"; return 0; fi
  echo "[$(hora)] EVALUAR $e"
  python scripts/09_evaluar.py --modelo B --checkpoint "runs/$d/ultimo.pt" \
    --particion val --manifest "$MAN" --etiqueta "$e" "$@"
}

mascaras() {  # carpeta
  if [ -d "runs/$1/mascaras_val" ]; then echo "[$(hora)] runs/$1/mascaras_val ya existe"; return 0; fi
  echo "[$(hora)] MASCARAS $1"
  python scripts/09_evaluar.py --modelo B --checkpoint "runs/$1/ultimo.pt" \
    --particion val --manifest "$MAN" --etiqueta "modelo_${1}_ultimo_masc" --guardar-mascaras \
    --salida "runs/$1/_eval_mascaras.csv"
}

completo() {  # carpeta
  evaluar "$1" "modelo_${1}_ultimo"
  evaluar "$1" "modelo_${1}_ultimo_crudo" --incluir-zona-borrada
  mascaras "$1"
  return 0
}

echo "======== [$(hora)] semilla 2 de B_pre"
entrenar 2 B_ext_largo_pre_s2 && completo B_ext_largo_pre_s2
echo "======== [$(hora)] semilla 3 de B_pre"
entrenar 3 B_ext_largo_pre_s3 && completo B_ext_largo_pre_s3

echo "======== [$(hora)] veredicto"
python - <<'PY'
import pandas as pd
ok = True
for s in ("s2", "s3"):
    d = pd.read_csv(f"results/modelo_B_ext_largo_pre_{s}_ultimo_val.csv"); p = d[d.mtv_gt_ml > 0]
    dice, fpv = p.dice.mean(), d.fpv_ml.mean()
    cumple = dice >= 0.716 and fpv <= 14.5
    ok &= cumple
    print(f"B_pre {s}: Dice⁺ {dice:.3f}  FPV {fpv:.2f} mL  → {'cumple' if cumple else 'NO cumple'}")
print("HIPÓTESIS", "ACEPTADA: el codificador preentrenado sube el Dice de forma repetible" if ok
      else "RECHAZADA: el 0,724 fue una semilla; la anatomía se cierra como negativo")
PY
echo "======== [$(hora)] TODO LISTO"
