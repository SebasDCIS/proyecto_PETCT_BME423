#!/usr/bin/env python
"""Rama `extendido`, paso 5. El análisis del test, escrito y probado ANTES de abrirlo.

Calcula exactamente lo declarado en docs/TEST_PREREGISTRO.md, ni más ni menos, y escribe
results/<particion>_final/resumen.md con las tablas y el veredicto de la hipótesis principal.
Se prueba con `--particion val` (mismos nombres de tabla, sufijo _val) para que el día del test
no haya código nuevo que escribir. No necesita torch.

    python scripts/37_analisis_final.py --particion val     # ensayo general
    python scripts/37_analisis_final.py --particion test    # una vez, tras scripts/35
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage, stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.organs import GROUP_NAMES, ORGANOS_FISIOLOGICOS, fp_by_organ  # noqa: E402
from petct.preprocess import load_study  # noqa: E402

SEM = ["", "_s2", "_s3"]
B_BOOT = 10_000
RNG = np.random.default_rng(423)
S26 = np.ones((3, 3, 3))


def tabla(et, part):
    f = Path("results") / f"{et}_{part}.csv"
    return pd.read_csv(f).sort_values("estudio").reset_index(drop=True) if f.exists() else None


def resumen(d):
    p, n = d[d.mtv_gt_ml > 0], d[d.mtv_gt_ml == 0]
    return dict(n=len(d), n_pos=len(p), dice=p.dice.mean(), dice_med=p.dice.median(), fpv=d.fpv_ml.mean(),
                fpv_med=d.fpv_ml.median(), fnv=p.fnv_ml.mean(), fpv_controles=n.fpv_ml.mean() if len(n) else np.nan)


def media_semillas(tablas):
    """Promedio estudio a estudio entre semillas (la referencia de las comparaciones pareadas)."""
    base = tablas[0][["estudio", "mtv_gt_ml"]].copy()
    for col in ("dice", "fpv_ml", "fnv_ml"):
        base[col] = np.mean([t[col].values for t in tablas], axis=0)
    return base


def pareado(x, ref):
    """x − ref, estudio a estudio: Dice en positivos, FPV en todos. IC95 por bootstrap."""
    assert (x.estudio.values == ref.estudio.values).all()
    pos = (ref.mtv_gt_ml > 0).values
    out = {}
    for nom, col, mask in (("dice", "dice", pos), ("fpv", "fpv_ml", np.ones_like(pos))):
        d = (x[col].values - ref[col].values)[mask]
        bo = np.array([RNG.choice(d, len(d)).mean() for _ in range(B_BOOT)])
        try:
            p = stats.wilcoxon(d).pvalue
        except ValueError:
            p = np.nan
        out[nom] = dict(delta=d.mean(), lo=np.percentile(bo, 2.5), hi=np.percentile(bo, 97.5), p=p,
                        gana=int((d > 0).sum() if nom == "dice" else (d < 0).sum()), n=len(d))
    return out


def fila_par(nom, r):
    a, b = r["dice"], r["fpv"]
    return (f"| {nom} | {a['delta']:+.3f} | [{a['lo']:+.3f}, {a['hi']:+.3f}] | {a['gana']}/{a['n']} | {a['p']:.3f} "
            f"| {b['delta']:+.2f} | [{b['lo']:+.2f}, {b['hi']:+.2f}] | {b['gana']}/{b['n']} | {b['p']:.3f} |")


def por_lesion_y_organo(carpeta, part, manifest, cache):
    sub = pd.read_csv(manifest); sub = sub[sub.split == part]
    L, F, O = [], [], []
    for r in sub.itertuples():
        nombre = f"{r.patient_id}__{r.study_uid}.npz"
        mf = Path(carpeta) / nombre
        if not mf.exists():
            return None
        if nombre not in cache:
            v = load_study(Path("data/processed") / nombre)
            seg = v["seg"].astype(bool); valid = v["suv"] > 0; ml = float(np.prod(v["spacing"])) / 1000
            lab, n = ndimage.label(seg & valid, S26)
            sz = ndimage.sum(np.ones_like(lab), lab, range(1, n + 1)) * ml if n else np.array([])
            go = Path("data/processed_organos") / nombre
            g = np.load(go)["groups"] if go.exists() else None
            cache[nombre] = (seg, valid, lab, n, sz, g, ml)
        seg, valid, lab, n, sz, g, ml = cache[nombre]
        z = np.load(mf); pred = (z["pred"] if "pred" in z.files else z[z.files[0]]).astype(bool)
        pv = pred & valid
        hit = set(np.unique(lab[pv & (lab > 0)]).tolist()) - {0}
        L += [dict(ml=sz[i - 1], det=int(i in hit)) for i in range(1, n + 1)]
        pl, pn = ndimage.label(pv, S26)
        F.append(sum(1 for k in range(1, pn + 1) if not seg[pl == k].any()))
        if g is not None:
            O.append(fp_by_organ(pred, seg, g, ml))
    L = pd.DataFrame(L)
    L["tam"] = pd.cut(L.ml, [0, 1, 3, 10, 1e9], labels=["<1 mL", "1–3 mL", "3–10 mL", ">10 mL"])
    sens = L.groupby("tam", observed=False).det.mean()
    org = pd.DataFrame(O).mean() if O else None
    return dict(det=int(L.det.sum()), tot=len(L), sens=sens, fp_est=float(np.mean(F)), org=org)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--particion", default="test", choices=["val", "test"])
    ap.add_argument("--manifest", default="data/manifests/subconjunto_extendido.csv")
    a = ap.parse_args()
    P = a.particion
    out = Path("results") / f"{P}_final"; out.mkdir(parents=True, exist_ok=True)
    md = [f"# Resultados finales sobre `{P}`\n",
          f"*Generado por `scripts/37_analisis_final.py --particion {P}`. Lo que se mide y cómo se decide está "
          f"en `docs/TEST_PREREGISTRO.md`, escrito antes de abrir el test.*\n"]

    # ---------------------------------------------------------- hipótesis principal
    B = [tabla(f"modelo_B_ext_largo{s}_ultimo", P) for s in SEM]
    ens = tabla("ensamble_B_ens_tta", P)
    if any(t is None for t in B) or ens is None:
        sys.exit("faltan las tablas de la hipótesis principal (B × 3 semillas y ensamble+TTA)")
    refB = media_semillas(B)
    h = pareado(ens, refB)
    acepta = h["dice"]["lo"] > 0 and h["fpv"]["hi"] < 0
    md += ["## Hipótesis principal (H1)\n",
           "Ensamble de cinco pliegues + TTA, umbral 0,5, contra B (825 estudios, media de tres semillas). "
           "Se confirma si el IC95 de ΔDice⁺ queda entero sobre 0 **y** el de ΔFPV entero bajo 0.\n",
           "| comparación | ΔDice⁺ | IC95 | gana | p | ΔFPV mL | IC95 | baja en | p |", "|---|---|---|---|---|---|---|---|---|",
           fila_par("ensamble+TTA − B", h),
           f"\n**Veredicto H1: {'CONFIRMADA' if acepta else 'NO CONFIRMADA'}.**\n"]
    fin = tabla("ensamble_final", P)
    dec_f = Path("results/oof_umbral/decision.json")
    if fin is not None:
        import json
        dec = json.load(open(dec_f)) if dec_f.exists() else {}
        h2 = pareado(fin, refB)
        acepta2 = h2["dice"]["lo"] > 0 and h2["fpv"]["hi"] < 0
        md += ["## Hipótesis H2: el sistema final\n",
               f"Ensamble + TTA con el umbral ({dec.get('umbral', '?')}) y la regla del hígado "
               f"({'sí, k = ' + str(dec.get('k_higado')) if dec.get('regla_higado') else 'no'}) decididos sobre los 825 "
               "estudios fuera de pliegue, contra B. Misma regla de confirmación que H1.\n",
               "| comparación | ΔDice⁺ | IC95 | gana | p | ΔFPV mL | IC95 | baja en | p |", "|---|---|---|---|---|---|---|---|---|",
               fila_par("sistema final − B", h2), f"\n**Veredicto H2: {'CONFIRMADA' if acepta2 else 'NO CONFIRMADA'}.**\n"]
        print(f"H2 ({P}): ΔDice {h2['dice']['delta']:+.3f} [{h2['dice']['lo']:+.3f},{h2['dice']['hi']:+.3f}]  "
              f"ΔFPV {h2['fpv']['delta']:+.2f} [{h2['fpv']['lo']:+.2f},{h2['fpv']['hi']:+.2f}]  → {'CONFIRMADA' if acepta2 else 'NO CONFIRMADA'}")
    print(f"H1 ({P}): ΔDice {h['dice']['delta']:+.3f} [{h['dice']['lo']:+.3f},{h['dice']['hi']:+.3f}]  "
          f"ΔFPV {h['fpv']['delta']:+.2f} [{h['fpv']['lo']:+.2f},{h['fpv']['hi']:+.2f}]  → {'CONFIRMADA' if acepta else 'NO CONFIRMADA'}")

    # ---------------------------------------------------------- tabla general
    filas = {}
    def agrega(nom, ts):
        ts = [t for t in ts if t is not None]
        if not ts:
            return
        r = pd.DataFrame([resumen(t) for t in ts])
        filas[nom] = dict(semillas=len(ts), dice=r.dice.mean(), dice_sd=r.dice.std(ddof=1) if len(ts) > 1 else np.nan,
                          dice_med=r.dice_med.mean(), fpv=r.fpv.mean(), fpv_med=r.fpv_med.mean(), fnv=r.fnv.mean(),
                          fpv_controles=r.fpv_controles.mean())
    clas = Path("results/referencia_clasica.csv")
    if clas.exists():
        c = pd.read_csv(clas); c = c[c.variante == "umbral+morfologia"]
        ids = set(pd.read_csv(a.manifest).query("split == @P").patient_id)
        agrega("Clásica (SUV ≥ 2,5)", [c[c.estudio.isin(ids)].sort_values("estudio").reset_index(drop=True)])
    for arm in ("A", "B", "C", "E"):                           # acto 1, criterio del protocolo (mejor.pt)
        agrega(f"Acto 1 · {arm} (176 est., 25k, mejor.pt)", [tabla(f"modelo_{arm}{s}", P) for s in SEM])
    for arm, run in (("A", "A_ext_largo"), ("A+", "Aplus_ext_largo"), ("B", "B_ext_largo"), ("C", "C_ext_largo"),
                     ("B preentrenada", "B_ext_largo_pre")):
        agrega(f"Extendido · {arm} (825 est., 100k)", [tabla(f"modelo_{run}{s}_ultimo", P) for s in SEM])
    agrega("Extendido · B pérdida pesada (1 sem.)", [tabla("modelo_B_ext_largo_peso_ultimo", P)])
    agrega("Extendido · B pre + pesada (1 sem.)", [tabla("modelo_B_ext_largo_pre_peso_ultimo", P)])
    miembros = [tabla(f"modelo_B_ens_{k}_ultimo", P) for k in range(5)]
    agrega("Miembros del ensamble, solos (media de 5)", miembros)
    agrega("Ensamble", [tabla("ensamble_B_ens", P)])
    agrega("**Ensamble + TTA (u 0,5, principal)**", [ens])
    agrega("Ensamble + TTA (u 0,7, secundario)", [tabla("ensamble_B_ens_tta_u07", P)])
    agrega("**Sistema final (H2)**", [tabla("ensamble_final", P)])
    T = pd.DataFrame(filas).T
    T.to_csv(out / "tabla_general.csv")
    md += ["## Todos los brazos (métrica corregida)\n",
           "| brazo | semillas | Dice⁺ | sd | mediana | FPV mL | FPV mediana | FNV mL | FPV en controles |",
           "|---|---|---|---|---|---|---|---|---|"]
    for k, r in T.iterrows():
        md.append(f"| {k} | {int(r.semillas)} | {r.dice:.3f} | {'' if pd.isna(r.dice_sd) else f'{r.dice_sd:.3f}'} | "
                  f"{r.dice_med:.3f} | {r.fpv:.2f} | {r.fpv_med:.2f} | {r.fnv:.2f} | {r.fpv_controles:.2f} |")

    # ---------------------------------------------------------- secundarias declaradas
    md += ["\n## Comparaciones secundarias declaradas\n",
           "| comparación | ΔDice⁺ | IC95 | gana | p | ΔFPV mL | IC95 | baja en | p |", "|---|---|---|---|---|---|---|---|---|"]
    u07 = tabla("ensamble_B_ens_tta_u07", P)
    if u07 is not None:
        md.append(fila_par("S1 · ensamble+TTA u 0,7 − B", pareado(u07, refB)))
    if all(t is not None for t in miembros):
        md.append(fila_par("S2 · ensamble+TTA − sus 5 miembros", pareado(ens, media_semillas(miembros))))
    acto1 = {arm: [tabla(f"modelo_{arm}{s}", P) for s in SEM] for arm in "ABCE"}
    if all(t is not None for v in acto1.values() for t in v):
        refA = media_semillas(acto1["A"])
        for arm in "BCE":
            md.append(fila_par(f"S5 · acto 1: {arm} − A", pareado(media_semillas(acto1[arm]), refA)))
    ext = {arm: [tabla(f"modelo_{run}{s}_ultimo", P) for s in SEM] for arm, run in
           (("A", "A_ext_largo"), ("A+", "Aplus_ext_largo"), ("B", "B_ext_largo"), ("C", "C_ext_largo"), ("Bpre", "B_ext_largo_pre"))}
    if all(t is not None for v in ext.values() for t in v):
        refA = media_semillas(ext["A"])
        for arm in ("A+", "B", "C"):
            md.append(fila_par(f"S6 · extendido: {arm} − A", pareado(media_semillas(ext[arm]), refA)))
        md.append(fila_par("S7 · extendido: B preentrenada − B", pareado(media_semillas(ext["Bpre"]), refB)))

    # ---------------------------------------------------------- por lesión y por órgano
    cache = {}
    carpetas = [("B s423", "runs/B_ext_largo"), ("B s2", "runs/B_ext_largo_s2"), ("B s3", "runs/B_ext_largo_s3"),
                ("Ensamble + TTA (u 0,5)", "runs/ensambles/ensamble_B_ens_tta"), ("Sistema final (H2)", "runs/ensambles/ensamble_final")]
    md += ["\n## S3 · Por lesión (lesiones fuera de la zona borrada; detectada = la toca alguna predicción)\n",
           "| | detectadas | < 1 mL | 1–3 mL | 3–10 mL | > 10 mL | marcas falsas / estudio |", "|---|---|---|---|---|---|---|"]
    orgs = {}
    for nom, base in carpetas:
        r = por_lesion_y_organo(f"{base}/mascaras_{P}", P, a.manifest, cache)
        if r is None:
            md.append(f"| {nom} | (sin máscaras) | | | | | |"); continue
        s = r["sens"]
        md.append(f"| {nom} | {r['det']}/{r['tot']} ({r['det'] / r['tot']:.2f}) | " + " | ".join(f"{v:.2f}" for v in s.values)
                  + f" | {r['fp_est']:.2f} |")
        if r["org"] is not None:
            orgs[nom] = r["org"]
    if orgs:
        O = pd.DataFrame(orgs).reindex(GROUP_NAMES)
        if all(k in O for k in ("B s423", "B s2", "B s3")):
            O.insert(0, "B (3 sem.)", O[["B s423", "B s2", "B s3"]].mean(1)); O = O.drop(columns=["B s423", "B s2", "B s3"])
        O.to_csv(out / "fp_por_organo.csv")
        md += ["\n## S4 · Falso positivo por órgano (mL por estudio, incluida la zona borrada)\n",
               "| | " + " | ".join(O.columns) + " |", "|---" * (len(O.columns) + 1) + "|"]
        grupos = [("órganos fisiológicos", ORGANOS_FISIOLOGICOS), ("tejido sin etiqueta + pulmón + bordes", ["otro", "pulmon", "fuera"])]
        for nom, gr in grupos + [("total", GROUP_NAMES)]:
            md.append(f"| {nom} | " + " | ".join(f"{O.loc[gr, c].sum():.2f}" for c in O.columns) + " |")

    # ---------------------------------------------------------- métrica cruda del reto
    md += ["\n## S8 · Métrica cruda del reto autoPET (sin excluir la zona borrada)\n", "| | Dice⁺ | FPV mL | FNV mL |", "|---|---|---|---|"]
    for nom, et in (("B (3 sem.)", [f"modelo_B_ext_largo{s}_ultimo_crudo" for s in SEM]), ("Ensamble + TTA (u 0,5)", ["ensamble_B_ens_tta_crudo"]),
                    ("Ensamble + TTA (u 0,7)", ["ensamble_B_ens_tta_u07_crudo"]), ("Sistema final (H2)", ["ensamble_final_crudo"])):
        ts = [tabla(e, P) for e in et]
        if all(t is not None for t in ts):
            r = pd.DataFrame([resumen(t) for t in ts]).mean()
            md.append(f"| {nom} | {r.dice:.3f} | {r.fpv:.2f} | {r.fnv:.2f} |")
    md.append("\nReferencias publicadas del reto 2022 (su test, no el nuestro): ganador Dice 0,623 / FPV 2,84 mL; nnU-Net de base 0,690 / 5,78.")

    (out / "resumen.md").write_text("\n".join(md) + "\n")
    print(f"escrito {out / 'resumen.md'}")


if __name__ == "__main__":
    main()
