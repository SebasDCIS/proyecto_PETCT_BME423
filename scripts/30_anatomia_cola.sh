#!/bin/bash
# Rama `extendido`, paso 3: ¿sirve enseñarle anatomía a la red? Ver docs/PASO3_ANATOMIA.md.
#
# Tres corridas de B (825 estudios, 100 000 iteraciones, semilla 423), contra la B ya hecha:
#   B_ext_largo_peso      pérdida pesada por órgano (fondo en órganos fisiológicos cuesta ×3)
#   B_ext_largo_pre       codificador de CT preentrenado en anatomía (scripts/29)
#   B_ext_largo_pre_peso  las dos cosas
#
# Antes hay que completar los mapas de órganos de los 649 estudios nuevos (TotalSegmentator,
# ~10 h) y preentrenar el codificador (~4 h). Reanudable como el 27: cada etapa se salta si
# su resultado ya existe.
#
# Pensado para dejarlo en cola detrás de scripts/27: con --esperar se queda mirando hasta que
# el 27 termine su último paso (las máscaras de A+ semilla 3) y recién entonces empieza.
#   caffeinate -i bash scripts/30_anatomia_cola.sh --esperar 2>&1 | tee -a runs/anatomia_cola.log
set -u
cd "$(dirname "$0")/.."
MAN=data/manifests/subconjunto_extendido.csv
IT=100000
PESO=3
ENC=runs/ct_anatomia/enc_ct.pt

hora() { date "+%Y-%m-%d %H:%M"; }

if [ "${1:-}" = "--esperar" ]; then
  echo "[$(hora)] esperando a que scripts/27 termine (runs/Aplus_ext_largo_s3/mascaras_val)"
  while [ ! -d runs/Aplus_ext_largo_s3/mascaras_val ]; do sleep 600; done
  echo "[$(hora)] el 27 terminó; empieza la cola de anatomía"
fi

entrenar() {  # carpeta flags...
  local d=$1; shift
  if [ -f "runs/$d/resumen.json" ]; then echo "[$(hora)] $d ya entrenado"; return 0; fi
  echo "[$(hora)] ENTRENAR $d (B, semilla 423, $IT iteraciones) $*"
  python scripts/07_entrenar.py --modelo B --semilla 423 --manifest "$MAN" \
    --iteraciones "$IT" --salida "runs/$d" "$@"
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

echo "======== [$(hora)] etapa 0: mapas de órganos de los estudios de entrenamiento que faltan"
python scripts/11_organos_totalsegmentator.py --manifest "$MAN" --particion train ${TS_DEVICE:+--device "$TS_DEVICE"}
n_falta=$(python - <<'PY'
import pandas as pd, os
m = pd.read_csv("data/manifests/subconjunto_extendido.csv"); m = m[m.split != "test"]
have = set(f[:-4] for f in os.listdir("data/processed_organos"))
print(int((~(m.patient_id + "__" + m.study_uid).isin(have)).sum()))
PY
)
if [ "$n_falta" != "0" ]; then echo "[$(hora)] faltan $n_falta mapas de órganos; no sigo"; exit 1; fi

echo "======== [$(hora)] etapa 1: B con pérdida pesada por órgano (x$PESO)"
entrenar B_ext_largo_peso --peso-organos "$PESO" && completo B_ext_largo_peso

echo "======== [$(hora)] etapa 2: preentrenar el codificador de CT en anatomía"
if [ -f "$ENC" ]; then echo "[$(hora)] $ENC ya existe"; else
  python scripts/29_preentrenar_ct_anatomia.py --manifest "$MAN" --salida runs/ct_anatomia
fi
[ -f "$ENC" ] || { echo "[$(hora)] no se generó $ENC; no sigo"; exit 1; }

echo "======== [$(hora)] etapa 3: B con codificador preentrenado"
entrenar B_ext_largo_pre --enc-ct-preentrenado "$ENC" && completo B_ext_largo_pre

echo "======== [$(hora)] etapa 4: B con las dos cosas"
entrenar B_ext_largo_pre_peso --enc-ct-preentrenado "$ENC" --peso-organos "$PESO" && completo B_ext_largo_pre_peso

echo "======== [$(hora)] etapa 5: falsos positivos por órgano, todas las corridas con máscaras"
python scripts/12_analisis_por_organo.py --particion val --manifest "$MAN" --sin-clasica

echo "======== [$(hora)] TODO LISTO"
