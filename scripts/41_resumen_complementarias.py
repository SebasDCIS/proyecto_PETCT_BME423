#!/usr/bin/env python
"""Resume las salidas de scripts/40 en results/test_final/complementarias.md.

Las comparaciones son pareadas por estudio. En los brazos con tres semillas se usa, por
estudio, el promedio de las semillas (para HD95, solo entre las semillas con predicción no
vacía). Como el HD95 tiene colas largas, se reporta la mediana y, para las comparaciones,
la mediana de las diferencias con IC95 por bootstrap y la prueba de Wilcoxon.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

D = Path("results/test_final")
rng = np.random.default_rng(423)


def boot_mediana(x, n=10000):
    x = np.asarray(x, float)
    idx = rng.integers(0, len(x), (n, len(x)))
    m = np.median(x[idx], axis=1)
    return float(np.median(x)), np.percentile(m, [2.5, 97.5])


def f(x, d=1):
    return "" if pd.isna(x) else f"{x:.{d}f}".replace(".", ",")


def main():
    L = []
    L.append("# Métricas complementarias sobre `test`\n")
    L.append("*Generado por `scripts/41_resumen_complementarias.py` a partir de `scripts/40`. "
             "Análisis secundario, declarado después de abrir la prueba y sin parámetros ajustables. "
             "Métrica corregida (sin la zona anonimizada) salvo en el contraste con el script oficial.*\n")

    # ---------------- HD95 ----------------
    hd = pd.read_csv(D / "hd95_test.csv")
    por_est = (hd.groupby(["brazo", "estudio"])
                 .agg(hd95_mm=("hd95_mm", "mean"), vacias=("pred_vacia", "sum"), n=("pred_vacia", "size"))
                 .reset_index())
    orden = list(dict.fromkeys(hd.brazo))
    L.append("## 1. Hausdorff 95 (mm), estudios positivos\n")
    L.append("| brazo | estudios con HD95 | predicción vacía (corridas) | mediana | p25 | p75 | media |")
    L.append("|---|---|---|---|---|---|---|")
    for b in orden:
        g = por_est[por_est.brazo == b]
        v = g.hd95_mm.dropna()
        L.append(f"| {b} | {len(v)}/{len(g)} | {int(g.vacias.sum())} | {f(v.median())} | "
                 f"{f(v.quantile(.25))} | {f(v.quantile(.75))} | {f(v.mean())} |")
    L.append("")
    comps = [("Sistema final (u 0,6)", "Extendido · B"), ("Ensamble + TTA (u 0,5)", "Extendido · B"),
             ("Extendido · B", "Extendido · A"), ("Extendido · C", "Extendido · A"),
             ("Extendido · A+", "Extendido · A"), ("Acto 1 · B", "Acto 1 · A"),
             ("Acto 1 · C", "Acto 1 · A"), ("Acto 1 · E", "Acto 1 · A"),
             ("Extendido · A", "Acto 1 · A"), ("Acto 1 · A", "Clásica + exclusión de órganos")]
    L.append("Comparaciones pareadas (diferencia por estudio, en mm; negativo = bordes más cerca de la verdad):\n")
    L.append("| comparación | estudios | mediana de la diferencia | IC95 | mejora en | p (Wilcoxon) |")
    L.append("|---|---|---|---|---|---|")
    piv = por_est.pivot(index="estudio", columns="brazo", values="hd95_mm")
    for x, y in comps:
        d = (piv[x] - piv[y]).dropna()
        med, ci = boot_mediana(d)
        p = wilcoxon(d).pvalue if len(d) > 5 and (d != 0).any() else float("nan")
        L.append(f"| {x} − {y} | {len(d)} | {f(med)} | [{f(ci[0])}, {f(ci[1])}] | {(d < 0).sum()}/{len(d)} | {f(p, 3)} |")
    L.append("")

    # ---------------- SUVmax ----------------
    sv = pd.read_csv(D / "suvmax_test.csv")
    sv = sv.groupby(["brazo", "estudio"])[["suvmax_gt", "suvmax_pred"]].mean().reset_index()
    sv["err"] = sv.suvmax_pred - sv.suvmax_gt
    sv["err_rel"] = sv.err / sv.suvmax_gt
    tope = (sv[sv.brazo == orden[0]].suvmax_gt >= 29.9).sum()
    L.append("## 2. Error de SUVmax por paciente, estudios positivos\n")
    L.append(f"SUVmax dentro de la predicción contra SUVmax dentro de la anotación. El SUV del "
             f"preprocesamiento tiene tope en 30: {tope} de {sv[sv.brazo == orden[0]].shape[0]} estudios "
             f"positivos tienen un SUVmax anotado en el tope, y en ellos el error queda subestimado.\n")
    L.append("| brazo | estudios | error mediano (SUV) | error absoluto mediano | dentro de ±10 % | sesgo | límites de concordancia |")
    L.append("|---|---|---|---|---|---|---|")
    for b in orden:
        g = sv[sv.brazo == b].dropna(subset=["err"])
        sd = g.err.std()
        L.append(f"| {b} | {len(g)} | {f(g.err.median(), 2)} | {f(g.err.abs().median(), 2)} | "
                 f"{(g.err_rel.abs() <= 0.10).mean() * 100:.0f} % | {f(g.err.mean(), 2)} | "
                 f"{f(g.err.mean() - 1.96 * sd, 2)} a {f(g.err.mean() + 1.96 * sd, 2)} |")
    L.append("")

    # ---------------- oficial ----------------
    of = pd.read_csv(D / "contraste_oficial_test.csv")
    L.append("## 3. Contraste con el script oficial de autoPET (métrica cruda)\n")
    L.append("El oficial usa componentes con conectividad 18; el nuestro, 26. Mismas máscaras, sin excluir la zona anonimizada.\n")
    L.append("| brazo | Dice⁺ oficial | Dice⁺ nuestro | FPV oficial | FPV nuestro | FNV oficial | FNV nuestro | estudios con alguna diferencia | mayor diferencia en FPV (mL) |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for b, g in of.groupby("brazo", sort=False):
        pos = g[g.positivo]
        dif = ((g.fpv_oficial - g.fpv_nuestro).abs() > 1e-6) | ((g.fnv_oficial - g.fnv_nuestro).abs() > 1e-6) | \
              ((g.dice_oficial - g.dice_nuestro).abs() > 1e-9)
        L.append(f"| {b} | {f(pos.dice_oficial.mean(), 3)} | {f(pos.dice_nuestro.mean(), 3)} | "
                 f"{f(g.fpv_oficial.mean(), 2)} | {f(g.fpv_nuestro.mean(), 2)} | {f(pos.fnv_oficial.mean(), 2)} | "
                 f"{f(pos.fnv_nuestro.mean(), 2)} | {int(dif.sum())}/{len(g)} | "
                 f"{f((g.fpv_oficial - g.fpv_nuestro).abs().max(), 2)} |")
    L.append("")

    # ---------------- clásicas ----------------
    L.append("## 4. Referencia clásica con y sin exclusión de órganos (TotalSegmentator)\n")
    L.append("| partición | variante | Dice⁺ | FPV (mL) | FNV (mL) | FPV en controles (mL) |")
    L.append("|---|---|---|---|---|---|")
    for part in ("val", "test"):
        p = (Path("results/val_final") if part == "val" else D) / f"clasicas_{part}.csv"
        if not p.exists():
            continue
        c = pd.read_csv(p)
        for b, g in c.groupby("brazo", sort=False):
            pos, neg = g[g.mtv_gt_ml > 0], g[g.mtv_gt_ml == 0]
            L.append(f"| {part} | {b} | {f(pos.dice.mean(), 3)} | {f(g.fpv_ml.mean(), 1)} | "
                     f"{f(pos.fnv_ml.mean(), 2)} | {f(neg.fpv_ml.mean(), 1)} |")
    L.append("")
    (D / "complementarias.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
