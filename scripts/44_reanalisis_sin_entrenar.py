#!/usr/bin/env python
"""Arreglos de análisis a fallas encontradas en la revisión crítica, sin entrenar nada.

Usa solo las tablas por estudio que ya están en results/. Todo es análisis secundario,
declarado después de abrir la prueba; no cambia el preregistro ni los veredictos de H1 y H2.

  1. Fuga en la validación del acto 1. `mejor.pt` se eligió con la validación rápida sobre los
     primeros 12 estudios de validación (orden alfabético, `val_files[:12]` en train.py), y la
     tabla del acto 1 reportaba los 26. Aquí se recalcula en los 14 que no participaron en la
     elección, junto a los 12 usados y a `ultimo.pt`.
  2. Bootstrap jerárquico. Los IC del preregistro remuestrean pacientes sobre el promedio de
     semillas. Aquí cada remuestreo sortea también las semillas de cada brazo (3 de 3 con
     reposición), de modo que el intervalo incluye la variación entre entrenamientos.
  3. Corrección por multiplicidad. Holm sobre las comparaciones secundarias (S1, S2, S5, S6,
     S7; Dice⁺ y FPV), con los p de Wilcoxon de la prueba de rangos con signo.
  4. (Opcional, si existen las tablas) Ensamble + TTA contra B + TTA, para separar la ganancia
     del ensamble de la ganancia de leer cada imagen cuatro veces. Las tablas se generan en el
     Mac con scripts/33 (un solo checkpoint con --tta); ver el README de este análisis.

Uso (desde la raíz del repositorio):
    python scripts/44_reanalisis_sin_entrenar.py
Escribe results/reanalisis/reanalisis.md y los CSV de cada parte.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

R = Path("results")
OUT = R / "reanalisis"
B_BOOT = 10_000
RNG = np.random.default_rng(423)


def tabla(nombre):
    f = R / f"{nombre}.csv"
    if not f.exists():
        return None
    return pd.read_csv(f).sort_values("estudio").reset_index(drop=True)


def resumen(d):
    p = d[d.mtv_gt_ml > 0]
    return dict(n=len(d), n_pos=len(p), dice=p.dice.mean(), fpv=d.fpv_ml.mean(), fnv=p.fnv_ml.mean())


def media(tablas, col):
    return np.mean([t[col].values for t in tablas], axis=0)


def f3(x):
    return f"{x:+.3f}".replace(".", ",")


def f2(x):
    return f"{x:+.2f}".replace(".", ",")


# ------------------------------------------------------------------ 1. fuga del acto 1
def parte1():
    filas = []
    for arm in ("A", "B", "C", "E"):
        for ck, suf in (("mejor.pt", ""), ("ultimo.pt", "_ultimo")):
            ts = [tabla(f"modelo_{arm}{s}{suf}_val") for s in ("", "_s2", "_s3")]
            if any(t is None for t in ts):
                continue
            est = list(ts[0].estudio)
            usados = set(est[:12])
            for grupo, sel in (("26 (todos)", est), ("12 usados para elegir", est[:12]), ("14 no usados", est[12:])):
                m = ts[0].estudio.isin(sel).values
                rs = [resumen(t[m]) for t in ts]
                filas.append(dict(brazo=arm, checkpoint=ck, grupo=grupo, n=rs[0]["n"], n_pos=rs[0]["n_pos"],
                                  dice=np.mean([r["dice"] for r in rs]), fpv=np.mean([r["fpv"] for r in rs])))
    df = pd.DataFrame(filas)
    df.to_csv(OUT / "p1_validacion_acto1.csv", index=False)
    # comparación pareada contra A en los 14 no usados, con mejor.pt
    comp = []
    ref = [tabla(f"modelo_A{s}_val") for s in ("", "_s2", "_s3")]
    est = list(ref[0].estudio); m14 = ref[0].estudio.isin(est[12:]).values
    pos = (ref[0].mtv_gt_ml > 0).values & m14
    for arm in ("B", "C", "E"):
        ts = [tabla(f"modelo_{arm}{s}_val") for s in ("", "_s2", "_s3")]
        d = (media(ts, "dice") - media(ref, "dice"))[pos]
        bo = np.array([RNG.choice(d, len(d)).mean() for _ in range(B_BOOT)])
        comp.append(dict(comparacion=f"{arm} − A", n_pos=len(d), delta=d.mean(),
                         lo=np.percentile(bo, 2.5), hi=np.percentile(bo, 97.5)))
    return df, pd.DataFrame(comp)


# ------------------------------------------------------------------ 2 y 3. comparaciones de la prueba
def brazo(nombres):
    ts = [tabla(n) for n in nombres]
    return None if any(t is None for t in ts) else ts


def comparaciones():
    ext = lambda b: [f"modelo_{b}_ultimo_test", f"modelo_{b}_s2_ultimo_test", f"modelo_{b}_s3_ultimo_test"]
    a1 = lambda b: [f"modelo_{b}_test", f"modelo_{b}_s2_test", f"modelo_{b}_s3_test"]
    B = ext("B_ext_largo")
    return [
        ("H1 · ensamble + TTA − B", ["ensamble_B_ens_tta_test"], B, "principal"),
        ("H2 · sistema final − B", ["ensamble_final_test"], B, "principal"),
        ("S1 · ensamble + TTA u 0,7 − B", ["ensamble_B_ens_tta_u07_test"], B, "secundaria"),
        ("S2 · ensamble + TTA − sus 5 miembros", ["ensamble_B_ens_tta_test"],
         [f"modelo_B_ens_{k}_ultimo_test" for k in range(5)], "secundaria"),
        ("S5 · acto 1: B − A", a1("B"), a1("A"), "secundaria"),
        ("S5 · acto 1: C − A", a1("C"), a1("A"), "secundaria"),
        ("S5 · acto 1: E − A", a1("E"), a1("A"), "secundaria"),
        ("S6 · extendido: A+ − A", ext("Aplus_ext_largo"), ext("A_ext_largo"), "secundaria"),
        ("S6 · extendido: B − A", B, ext("A_ext_largo"), "secundaria"),
        ("S6 · extendido: C − A", ext("C_ext_largo"), ext("A_ext_largo"), "secundaria"),
        ("S7 · extendido: B preentrenada − B", ext("B_ext_largo_pre"), B, "secundaria"),
    ]


def jerarquico(X, Y, col, mask):
    """Remuestrea pacientes y, dentro de cada brazo con varias semillas, las semillas."""
    xs = np.array([t[col].values for t in X])[:, mask]
    ys = np.array([t[col].values for t in Y])[:, mask]
    n = xs.shape[1]
    out = np.empty(B_BOOT)
    for b in range(B_BOOT):
        i = RNG.integers(0, n, n)
        sx = RNG.integers(0, len(xs), len(xs)) if len(xs) > 1 else [0]
        sy = RNG.integers(0, len(ys), len(ys)) if len(ys) > 1 else [0]
        out[b] = (xs[sx][:, i].mean(0) - ys[sy][:, i].mean(0)).mean()
    return out


def parte23():
    filas = []
    for nom, xn, yn, tipo in comparaciones():
        X, Y = brazo(xn), brazo(yn)
        if X is None or Y is None:
            continue
        assert all((t.estudio.values == X[0].estudio.values).all() for t in X + Y)
        pos = (Y[0].mtv_gt_ml > 0).values
        for met, col, mask in (("Dice⁺", "dice", pos), ("FPV", "fpv_ml", np.ones_like(pos))):
            d = (media(X, col) - media(Y, col))[mask]
            bo_simple = np.array([RNG.choice(d, len(d)).mean() for _ in range(B_BOOT)])
            bo_jer = jerarquico(X, Y, col, mask)
            try:
                p = stats.wilcoxon(d).pvalue
            except ValueError:
                p = np.nan
            filas.append(dict(comparacion=nom, tipo=tipo, metrica=met, delta=d.mean(),
                              lo_simple=np.percentile(bo_simple, 2.5), hi_simple=np.percentile(bo_simple, 97.5),
                              lo_jer=np.percentile(bo_jer, 2.5), hi_jer=np.percentile(bo_jer, 97.5), p_wilcoxon=p))
    df = pd.DataFrame(filas)
    # Holm sobre la familia de secundarias (todas las métricas)
    sec = df[df.tipo == "secundaria"].copy()
    orden = sec.p_wilcoxon.sort_values().index
    m = len(orden)
    ajust, acum = {}, 0.0
    for k, idx in enumerate(orden):
        acum = max(acum, min(1.0, (m - k) * sec.loc[idx, "p_wilcoxon"]))
        ajust[idx] = acum
    df["p_holm"] = df.index.map(lambda i: ajust.get(i, np.nan))
    df.to_csv(OUT / "p23_comparaciones_prueba.csv", index=False)
    return df


# ------------------------------------------------------------------ 4. ensamble + TTA contra B + TTA (opcional)
def parte4():
    btta = brazo([f"B_ext_tta_{s}_test" for s in ("s423", "s2", "s3")])
    ens = brazo(["ensamble_B_ens_tta_test"])
    if btta is None or ens is None:
        return None
    pos = (btta[0].mtv_gt_ml > 0).values
    filas = []
    for met, col, mask in (("Dice⁺", "dice", pos), ("FPV", "fpv_ml", np.ones_like(pos))):
        d = (media(ens, col) - media(btta, col))[mask]
        bo = jerarquico(ens, btta, col, mask)
        filas.append(dict(metrica=met, delta=d.mean(), lo=np.percentile(bo, 2.5), hi=np.percentile(bo, 97.5),
                          p_wilcoxon=stats.wilcoxon(d).pvalue))
    rb = [resumen(t) for t in btta]
    return pd.DataFrame(filas), dict(dice=np.mean([r["dice"] for r in rb]), fpv=np.mean([r["fpv"] for r in rb]))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    md = ["# Reanálisis sin entrenar (fallas de la revisión crítica)\n",
          "*Generado por `scripts/44_reanalisis_sin_entrenar.py`. Análisis secundario, posterior a la apertura de la prueba; "
          "no cambia el preregistro ni los veredictos de H1 y H2.*\n"]

    p1, c1 = parte1()
    md += ["## 1. Acto 1 en validación sin la fuga del checkpoint\n",
           "`mejor.pt` se eligió con los primeros 12 estudios de validación. Media de tres semillas.\n",
           "| brazo | checkpoint | estudios | positivos | Dice⁺ | FPV mL |", "|---|---|---|---|---|---|"]
    for r in p1.itertuples():
        md.append(f"| {r.brazo} | `{r.checkpoint}` | {r.grupo} | {r.n_pos} | " + f"{r.dice:.3f} | {r.fpv:.1f} |".replace(".", ","))
    md += ["\nComparación pareada contra A en los 14 estudios no usados (`mejor.pt`, Dice⁺):\n",
           "| comparación | positivos | ΔDice⁺ | IC95 |", "|---|---|---|---|"]
    for r in c1.itertuples():
        md.append(f"| {r.comparacion} | {r.n_pos} | {f3(r.delta)} | [{f3(r.lo)}, {f3(r.hi)}] |")

    p23 = parte23()
    md += ["\n## 2 y 3. Comparaciones de la prueba: IC jerárquico y Holm\n",
           "IC simple: bootstrap de pacientes sobre el promedio de semillas (el del preregistro). "
           "IC jerárquico: remuestrea pacientes y semillas. Holm: sobre las 18 pruebas secundarias (9 comparaciones × 2 métricas).\n",
           "| comparación | métrica | Δ | IC simple | IC jerárquico | p Wilcoxon | p Holm |", "|---|---|---|---|---|---|---|"]
    for r in p23.itertuples():
        fm = f3 if r.metrica == "Dice⁺" else f2
        ph = "" if np.isnan(r.p_holm) else f"{r.p_holm:.3f}".replace(".", ",")
        md.append(f"| {r.comparacion} | {r.metrica} | {fm(r.delta)} | [{fm(r.lo_simple)}, {fm(r.hi_simple)}] | "
                  f"[{fm(r.lo_jer)}, {fm(r.hi_jer)}] | {r.p_wilcoxon:.3f} | {ph} |".replace("0.", "0,").replace("1.000", "1,000"))

    p4 = parte4()
    md += ["\n## 4. Ensamble + TTA contra B + TTA\n"]
    if p4 is None:
        md.append("Pendiente: faltan `results/B_ext_tta_{s423,s2,s3}_test.csv` (ver README del análisis).")
    else:
        t4, rb = p4
        t4.to_csv(OUT / "p4_ensamble_vs_btta.csv", index=False)
        md.append(f"B + TTA (media de tres semillas): Dice⁺ {rb['dice']:.3f}, FPV {rb['fpv']:.2f} mL.\n".replace(".", ","))
        md += ["| métrica | Δ (ensamble+TTA − B+TTA) | IC jerárquico | p Wilcoxon |", "|---|---|---|---|"]
        for r in t4.itertuples():
            fm = f3 if r.metrica == "Dice⁺" else f2
            md.append(f"| {r.metrica} | {fm(r.delta)} | [{fm(r.lo)}, {fm(r.hi)}] | {r.p_wilcoxon:.3f} |".replace("0.", "0,"))
    (OUT / "reanalisis.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
