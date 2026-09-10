#!/usr/bin/env python
"""Paso 6b. ¿Sirve de algo referir la captación al órgano? Prueba sin entrenar nada.

Uso (no necesita PyTorch):
    python scripts/18_poder_separacion.py --atlas controles
    python scripts/18_poder_separacion.py --atlas train

La pregunta: antes de gastar tres noches de entrenamiento en un modelo con un canal de
"SUV relativo al órgano", conviene comprobar que ese número **separa** de verdad las marcas
buenas de las malas. Y eso se puede medir hoy, porque ya tenemos guardadas las predicciones
de las nueve corridas sobre los 26 estudios de validación, y sabemos cuáles de esas marcas
tocan una lesión anotada y cuáles no.

Cómo funciona:
  1. Cada predicción se parte en componentes conexas (26-conexas), igual que en la métrica
     FPV. Cada componente es "un hallazgo".
  2. Un hallazgo que toca la lesión anotada es verdadero (VP); uno que no la toca es falso
     (FP). Es exactamente la definición de autoPET, no una nueva.
  3. A cada hallazgo se le calculan cinco puntuaciones, de la más ingenua a la más clínica:
        SUVmáx crudo                    lo que se usa hoy
        SUVmáx / p95 del órgano         cuántas veces se pasa del techo normal de ESE órgano
        z robusto del órgano            (SUVmáx − mediana) / (RIC / 1,349)
        veces el hígado propio          SUVmáx dividido por el hígado DEL MISMO paciente. Es
                                        la escala de Deauville: cancela dosis inyectada,
                                        tiempo de captación, glicemia y peso, que son la causa
                                        real de que el "hígado normal" varíe entre personas.
        veces el hígado / p95 del órgano  las dos cosas juntas: referencia interna del paciente
                                        Y techo específico del órgano.
  4. Se mide con qué eficacia cada puntuación ordena los verdaderos por encima de los falsos.
     La medida es el AUC: la probabilidad de que un hallazgo verdadero tomado al azar tenga
     puntuación más alta que un falso tomado al azar. 0,5 es azar puro; 1,0 es separación
     perfecta.

Cómo se decide con el resultado:
  - Si el AUC del SUV relativo supera claramente al del SUV crudo, el canal aporta información
    que la red no tiene y vale la pena entrenar el brazo E2.
  - Si son iguales, la referencia por órgano no agrega nada sobre el valor absoluto y conviene
    ir por el canal anatómico simple (E1), o no gastar las noches.

Salidas:
  results/separacion_hallazgos_val.csv   una fila por hallazgo (para el análisis por órgano)
  results/separacion_resumen_val.csv     AUC por puntuación y por corrida
  docs/figuras/separacion_val.png        distribuciones y curvas ROC
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.organs import GROUP_NAMES, internal_reference  # noqa: E402

CONN = np.ones((3, 3, 3), dtype=bool)
MARGEN_LESION = 2      # igual que en el atlas: no contaminar la referencia con el halo del tumor

# Cuatro formas de puntuar un hallazgo, de la más ingenua a la más clínica:
PUNTUACIONES = ["suvmax", "suv_rel_p95", "z_robusto", "veces_higado", "rel_organo"]
ETIQUETAS = {
    "suvmax": "SUVmáx crudo",
    "suv_rel_p95": "SUVmáx / p95 poblacional del órgano",
    "z_robusto": "z robusto poblacional del órgano",
    "veces_higado": "veces el hígado del propio paciente",       # Deauville puro
    "rel_organo": "veces el hígado propio / p95 del órgano",     # Deauville + órgano
}


def auc(pos: np.ndarray, neg: np.ndarray) -> float:
    """AUC por rangos (Mann-Whitney), con corrección de empates. Sin dependencias extra."""
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    pos, neg = pos[np.isfinite(pos)], neg[np.isfinite(neg)]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    todos = np.concatenate([pos, neg])
    orden = todos.argsort()
    rangos = np.empty(len(todos), float)
    rangos[orden] = np.arange(1, len(todos) + 1)
    # promediar rangos de los empates
    v = todos[orden]
    i = 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[j + 1] == v[i]:
            j += 1
        if j > i:
            rangos[orden[i:j + 1]] = rangos[orden[i:j + 1]].mean()
        i = j + 1
    r_pos = rangos[:len(pos)].sum()
    return float((r_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def curva_roc(pos: np.ndarray, neg: np.ndarray, n=200):
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    pos, neg = pos[np.isfinite(pos)], neg[np.isfinite(neg)]
    if len(pos) == 0 or len(neg) == 0:
        return np.array([0, 1.0]), np.array([0, 1.0])
    umbrales = np.unique(np.quantile(np.concatenate([pos, neg]), np.linspace(0, 1, n)))
    tpr = np.array([(pos >= u).mean() for u in umbrales])
    fpr = np.array([(neg >= u).mean() for u in umbrales])
    return np.concatenate([[1.0], fpr, [0.0]]), np.concatenate([[1.0], tpr, [0.0]])


def corridas_disponibles(raiz: Path, particion: str):
    fuera = lambda d: d.name.startswith("humo") or "piloto" in d.name
    return sorted(d.name for d in raiz.iterdir()
                  if d.is_dir() and not fuera(d) and (d / f"mascaras_{particion}").is_dir())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", default="controles", choices=["controles", "train"])
    ap.add_argument("--particion", default="val")
    ap.add_argument("--manifest", default="data/manifests/subconjunto.csv")
    ap.add_argument("--procesado", default="data/processed")
    ap.add_argument("--organos", default="data/processed_organos")
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--resultados", default="results")
    ap.add_argument("--figura", default="docs/figuras/separacion_val.png")
    ap.add_argument("--min-ml", type=float, default=0.0,
                    help="ignora hallazgos por debajo de este volumen (por defecto, ninguno)")
    a = ap.parse_args()

    res = Path(a.resultados)
    f_atlas = res / f"atlas_normalidad_{a.atlas}.csv"
    if not f_atlas.exists():
        sys.exit(f"No existe {f_atlas}. Corre antes scripts/17_atlas_normalidad.py --subconjunto {a.atlas}")
    atlas = pd.read_csv(f_atlas).set_index("organo")
    col = lambda o, c: float(atlas.loc[o, c]) if c in atlas.columns else float("nan")
    ref = {o: {"p50": col(o, "p50"), "p25": col(o, "p25"), "p75": col(o, "p75"),
               "p95": col(o, "p95"), "rel_p95": col(o, "rel_p95")}
           for o in atlas.index}
    if "rel_p95" not in atlas.columns:
        print("[aviso] el atlas no trae la escala relativa (rel_p95). Vuelve a correr "
              "scripts/17_atlas_normalidad.py para tenerla.", flush=True)

    sub = pd.read_csv(a.manifest)
    estudios = sub[sub.split == a.particion]
    corridas = corridas_disponibles(Path(a.runs), a.particion)
    if not corridas:
        sys.exit(f"No hay carpetas runs/*/mascaras_{a.particion}/")
    print(f"atlas '{a.atlas}' · {len(estudios)} estudios de {a.particion} · corridas: {', '.join(corridas)}\n",
          flush=True)

    filas = []
    for r in estudios.itertuples():
        base = f"{r.patient_id}__{r.study_uid}"
        f_org = Path(a.organos) / f"{base}.npz"
        if not f_org.exists():
            continue
        d = np.load(Path(a.procesado) / f"{base}.npz")
        suv = d["suv"].astype(np.float32) * float(d["suv_top"])
        gt = d["seg"].astype(bool)
        ml = float(np.prod(d["spacing"].astype(float)) / 1000.0)
        body = d["body"].astype(bool)
        groups = np.load(f_org)["groups"].astype(np.uint8)
        # Misma regla de exclusión que la evaluación oficial: la zona borrada no cuenta.
        visible = suv > 0.0
        gt_v = gt & visible

        # Referencia interna del propio paciente, calculada igual que en el atlas: sobre
        # tejido válido y con la lesión anotada (y su halo) fuera.
        valido = body & visible
        if gt.any():
            valido &= ~ndimage.binary_dilation(gt, iterations=MARGEN_LESION)
        ref_pac, origen_ref = internal_reference(suv, groups, valido)

        antes = len(filas)
        for corrida in corridas:
            f_pred = Path(a.runs) / corrida / f"mascaras_{a.particion}" / f"{base}.npz"
            if not f_pred.exists():
                continue
            pred = np.load(f_pred)["pred"].astype(bool) & visible
            etiquetas, n = ndimage.label(pred, structure=CONN)
            if n == 0:
                continue
            objetos = ndimage.find_objects(etiquetas)
            for c in range(1, n + 1):
                sl = objetos[c - 1]
                m = etiquetas[sl] == c
                vox = int(m.sum())
                vol = vox * ml
                if vol < a.min_ml:
                    continue
                suv_c = suv[sl][m]
                g_c = groups[sl][m]
                cuenta = np.bincount(g_c, minlength=len(GROUP_NAMES))
                organo = GROUP_NAMES[int(cuenta.argmax())]
                verdadero = bool(gt_v[sl][m].any())
                smax = float(suv_c.max())
                p = ref.get(organo)
                rel = z = rel_org = float("nan")
                if p and np.isfinite(p["p95"]) and p["p95"] > 0:
                    rel = smax / p["p95"]
                    ric = max(p["p75"] - p["p25"], 1e-3)
                    z = (smax - p["p50"]) / (ric / 1.349)
                # Deauville: el foco medido en unidades del hígado del propio paciente
                veces = smax / ref_pac if np.isfinite(ref_pac) and ref_pac > 0 else float("nan")
                if p and np.isfinite(veces) and np.isfinite(p["rel_p95"]) and p["rel_p95"] > 0:
                    rel_org = veces / p["rel_p95"]
                filas.append({
                    "corrida": corrida, "modelo": corrida.split("_")[0], "patient_id": r.patient_id,
                    "diagnosis": r.diagnosis, "organo": organo, "vol_ml": round(vol, 3),
                    "suvmax": round(smax, 3), "suvmedia": round(float(suv_c.mean()), 3),
                    "ref_interna": round(ref_pac, 3) if np.isfinite(ref_pac) else np.nan,
                    "origen_ref": origen_ref,
                    "suv_rel_p95": round(rel, 3) if np.isfinite(rel) else np.nan,
                    "z_robusto": round(z, 3) if np.isfinite(z) else np.nan,
                    "veces_higado": round(veces, 3) if np.isfinite(veces) else np.nan,
                    "rel_organo": round(rel_org, 3) if np.isfinite(rel_org) else np.nan,
                    "verdadero": verdadero,
                })
        print(f"  {r.patient_id}: {len(filas) - antes} hallazgos", flush=True)

    if not filas:
        sys.exit("No se encontró ningún hallazgo. ¿Existen runs/*/mascaras_val/ y data/processed_organos/?")
    df = pd.DataFrame(filas)
    f1 = res / f"separacion_hallazgos_{a.particion}.csv"
    df.to_csv(f1, index=False)

    # --- AUC por corrida y agrupado
    resumen = []
    for grupo, sel in [("TODAS", df)] + [(c, df[df.corrida == c]) for c in corridas]:
        fila = {"conjunto": grupo, "n_verdaderos": int(sel.verdadero.sum()),
                "n_falsos": int((~sel.verdadero).sum())}
        for p in PUNTUACIONES:
            fila[f"auc_{p}"] = round(auc(sel.loc[sel.verdadero, p].values,
                                         sel.loc[~sel.verdadero, p].values), 4)
        resumen.append(fila)
    dres = pd.DataFrame(resumen)
    f2 = res / f"separacion_resumen_{a.particion}.csv"
    dres.to_csv(f2, index=False)

    # --- ¿Cuántos falsos se podrían quitar conservando el 95 % de los verdaderos?
    print("\nSi se filtra por cada puntuación conservando el 95 % de los hallazgos verdaderos:")
    tabla_op = []
    for p in PUNTUACIONES:
        v = df.loc[df.verdadero, p].dropna().values
        f_ = df.loc[~df.verdadero, p].dropna().values
        if len(v) == 0 or len(f_) == 0:
            continue
        u = float(np.quantile(v, 0.05))
        quitados = float((f_ < u).mean())
        tabla_op.append({"puntuacion": ETIQUETAS[p], "umbral": round(u, 3),
                         "falsos_eliminados_%": round(100 * quitados, 1),
                         "verdaderos_conservados_%": 95.0})
    dop = pd.DataFrame(tabla_op)
    print(dop.to_string(index=False))

    print("\nAUC (probabilidad de ordenar un hallazgo verdadero por encima de uno falso):\n")
    print(dres.to_string(index=False))

    mejor = max(PUNTUACIONES, key=lambda p: dres.loc[0, f"auc_{p}"] if np.isfinite(dres.loc[0, f"auc_{p}"]) else -1)
    delta = dres.loc[0, f"auc_{mejor}"] - dres.loc[0, "auc_suvmax"]
    print(f"\nMejor puntuación: {ETIQUETAS[mejor]} (AUC {dres.loc[0, f'auc_{mejor}']:.3f}), "
          f"{delta:+.3f} frente al SUV crudo.")
    if mejor != "suvmax" and delta >= 0.03:
        print("→ La referencia por órgano aporta información que el SUV absoluto no tiene. "
              "Vale la pena entrenar el brazo con canal de SUV relativo (E2).")
    else:
        print("→ La referencia por órgano no mejora al SUV absoluto en estos datos. "
              "Conviene ir por el canal anatómico simple (E1) o no gastar las noches.")

    # --- AUC por órgano: dónde ayuda y dónde no
    porg = []
    for o, sel in df.groupby("organo"):
        if sel.verdadero.sum() < 5 or (~sel.verdadero).sum() < 5:
            continue
        porg.append({"organo": o, "n_verdaderos": int(sel.verdadero.sum()),
                     "n_falsos": int((~sel.verdadero).sum()),
                     **{f"auc_{p}": round(auc(sel.loc[sel.verdadero, p].values,
                                              sel.loc[~sel.verdadero, p].values), 3)
                        for p in PUNTUACIONES}})
    if porg:
        dorg = pd.DataFrame(porg).sort_values("n_falsos", ascending=False)
        dorg.to_csv(res / f"separacion_por_organo_{a.particion}.csv", index=False)
        print("\nPor órgano (solo los que tienen al menos 5 de cada clase):\n")
        print(dorg.to_string(index=False))

    figura(df, dres, Path(a.figura))
    print(f"\n{f1}\n{f2}\n{a.figura}")


def figura(df: pd.DataFrame, dres: pd.DataFrame, destino: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    destino.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(2, len(PUNTUACIONES), figsize=(3.7 * len(PUNTUACIONES), 8))
    for j, p in enumerate(PUNTUACIONES):
        v = df.loc[df.verdadero, p].dropna().values
        f_ = df.loc[~df.verdadero, p].dropna().values
        if len(v) == 0 or len(f_) == 0:
            continue
        top = float(np.quantile(np.concatenate([v, f_]), 0.99))
        bins = np.linspace(0, max(top, 1e-3), 45)
        ax[0, j].hist(f_, bins=bins, alpha=0.6, label=f"falsos (n={len(f_)})", color="#c0392b")
        ax[0, j].hist(v, bins=bins, alpha=0.6, label=f"verdaderos (n={len(v)})", color="#27ae60")
        ax[0, j].set_title(ETIQUETAS[p]); ax[0, j].set_xlabel(ETIQUETAS[p])
        ax[0, j].set_ylabel("hallazgos"); ax[0, j].legend(fontsize=8)

        fpr, tpr = curva_roc(v, f_)
        ax[1, j].plot(fpr, tpr, color="#2c3e50", lw=2)
        ax[1, j].plot([0, 1], [0, 1], "--", color="#95a5a6", lw=1)
        ax[1, j].set_xlabel("fracción de falsos que pasan el filtro")
        ax[1, j].set_ylabel("fracción de verdaderos conservados")
        ax[1, j].set_title(f"AUC = {dres.loc[0, f'auc_{p}']:.3f}")
        ax[1, j].set_xlim(0, 1); ax[1, j].set_ylim(0, 1.02)
    fig.suptitle("¿Separa mejor la captación referida al órgano que el SUV absoluto?  "
                 "(hallazgos de las 9 corridas sobre los 26 estudios de validación)", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(destino, dpi=140)
    plt.close(fig)


if __name__ == "__main__":
    main()
