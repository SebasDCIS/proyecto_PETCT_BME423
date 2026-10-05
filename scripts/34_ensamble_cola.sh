#!/bin/bash
# Rama `extendido`, paso 4: ensamble de cinco pliegues. Ver docs/PASO4_ENSAMBLE.md.
#
# BRAZO decide qué residente entra al ensamble (lo fija el veredicto de scripts/31):
#   BRAZO=pre  → B con codificador de CT preentrenado (si las semillas 2 y 3 cumplieron)
#   BRAZO=B    → B a secas (si no)
# Cinco corridas (una por pliegue, 4/5 del entrenamiento cada una, 100 000 iteraciones,
# semilla 423), después: cada corrida sobre su pliegue no visto (oof), cada corrida sola
# sobre val, y el ensamble sobre val con y sin TTA. Reanudable como los anteriores.
#
#   BRAZO=pre caffeinate -i bash scripts/34_ensamble_cola.sh 2>&1 | tee -a runs/ensamble_cola.log
set -u
# Nota: el bash del Mac es 3.2, donde "${arr[@]}" con un arreglo vacío falla bajo set -u;
# por eso EXTRA se expande como ${EXTRA[@]+"${EXTRA[@]}"} (vacío si no hay nada).
cd "$(dirname "$0")/.."
BRAZO=${BRAZO:?define BRAZO=pre o BRAZO=B}
MAN=data/manifests/subconjunto_extendido.csv
IT=100000
ENC=runs/ct_anatomia/enc_ct.pt
case "$BRAZO" in
  pre) EXTRA=(--enc-ct-preentrenado "$ENC"); PREFIJO=B_ens_pre ;;
  B)   EXTRA=(); PREFIJO=B_ens ;;
  *)   echo "BRAZO debe ser pre o B"; exit 1 ;;
esac

hora() { date "+%Y-%m-%d %H:%M"; }

[ -f data/manifests/_pliegues/pliegue_4.csv ] || python scripts/32_pliegues.py

echo "======== [$(hora)] cinco pliegues ($PREFIJO)"
CKS=()
for k in 0 1 2 3 4; do
  d=${PREFIJO}_$k
  if [ -f "runs/$d/resumen.json" ]; then echo "[$(hora)] $d ya entrenado"; else
    echo "[$(hora)] ENTRENAR $d (pliegue $k fuera)"
    python scripts/07_entrenar.py --modelo B --semilla 423 --manifest "data/manifests/_pliegues/pliegue_$k.csv" \
      --iteraciones "$IT" --salida "runs/$d" ${EXTRA[@]+"${EXTRA[@]}"}
  fi
  CKS+=("runs/$d/ultimo.pt")
  # el quinto no visto: la única estimación sobre estudios de entrenamiento que no vio
  if [ ! -f "results/modelo_${d}_ultimo_oof.csv" ]; then
    echo "[$(hora)] EVALUAR $d sobre su pliegue (oof, ~165 estudios)"
    python scripts/09_evaluar.py --modelo B --checkpoint "runs/$d/ultimo.pt" --particion oof \
      --manifest "data/manifests/_pliegues/pliegue_$k.csv" --etiqueta "modelo_${d}_ultimo"
  fi
  if [ ! -f "results/modelo_${d}_ultimo_val.csv" ]; then
    echo "[$(hora)] EVALUAR $d solo sobre val"
    python scripts/09_evaluar.py --modelo B --checkpoint "runs/$d/ultimo.pt" --particion val \
      --manifest "$MAN" --etiqueta "modelo_${d}_ultimo"
  fi
done

echo "======== [$(hora)] ensamble sobre val"
for variante in "" "--tta"; do
  e=ensamble_${PREFIJO}${variante:+_tta}
  if [ -f "results/${e}_val.csv" ]; then echo "[$(hora)] results/${e}_val.csv ya existe"; continue; fi
  echo "[$(hora)] ENSAMBLE $e"
  python scripts/33_ensamble.py --modelo B --checkpoints "${CKS[@]}" --particion val --manifest "$MAN" \
    --etiqueta "$e" --guardar-mascaras --guardar-probabilidades $variante
  python scripts/33_ensamble.py --modelo B --checkpoints "${CKS[@]}" --particion val --manifest "$MAN" \
    --etiqueta "${e}_crudo" --incluir-zona-borrada $variante
done

echo "======== [$(hora)] veredicto (criterio de docs/PASO4_ENSAMBLE.md)"
python - "$PREFIJO" <<'PY'
import sys, pandas as pd
pref = sys.argv[1]
def res(e):
    d = pd.read_csv(f"results/{e}_val.csv"); p = d[d.mtv_gt_ml > 0]
    return p.dice.mean(), d.fpv_ml.mean(), p.fnv_ml.mean()
solos = [res(f"modelo_{pref}_{k}_ultimo") for k in range(5)]
print("corridas solas (val): Dice", [round(s[0], 3) for s in solos], "FPV", [round(s[1], 1) for s in solos])
for e in (f"ensamble_{pref}", f"ensamble_{pref}_tta"):
    d, f, n = res(e)
    ok = f < 9.0 and d >= 0.705
    print(f"{e}: Dice⁺ {d:.3f}  FPV {f:.2f} mL  FNV {n:.2f} mL → {'CUMPLE' if ok else 'no cumple'} (FPV < 9 y Dice⁺ ≥ 0,705)")
PY
echo "======== [$(hora)] TODO LISTO"
