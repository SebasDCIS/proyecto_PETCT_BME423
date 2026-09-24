#!/usr/bin/env python
"""Rama `extendido`, paso 3. Preentrenar el codificador de CT en anatomía.

La idea, con la analogía del residente: antes de enseñarle a marcar tumores, se le hace
un curso de anatomía. Se toma el mismo codificador de CT que usa el modelo B
(`petct.models.Encoder`, un canal de entrada, el mismo plan de canales) y se lo entrena,
con un decodificador provisional, a responder "¿qué órgano hay en cada vóxel?" a partir
del CT solo. La respuesta correcta la da TotalSegmentator (los 17 grupos de
`petct.organs.GROUP_NAMES`), que para esto es el experto. No se usa ni el PET ni la
máscara de lesión: la anatomía se aprende de los 825 estudios de entrenamiento sin
mirar nunca el tumor.

Al terminar se guarda solo el codificador (`enc_ct.pt`); el decodificador provisional se
descarta. Después, `scripts/07_entrenar.py --modelo B --enc-ct-preentrenado
runs/ct_anatomia/enc_ct.pt` arranca B con ese codificador ya sabiendo dónde está el
hígado, la vejiga o el corazón, y entrena todo lo demás desde cero como siempre.

Qué se mide durante el preentrenamiento: Dice medio por órgano sobre parches fijos de
los estudios de validación (los mismos 26 de siempre; no se toca el test). Es una
métrica interna: sirve para saber que el curso de anatomía funcionó, no para comparar
brazos.

Uso (una noche en el Mac):
    python scripts/29_preentrenar_ct_anatomia.py --manifest data/manifests/subconjunto_extendido.csv
    # humo:
    python scripts/29_preentrenar_ct_anatomia.py --small --parche 64 --iteraciones 30 --validar-cada 15 \
        --salida runs/humo_anatomia --dispositivo cpu

Reanudable: si en `--salida` hay `ultimo.pt`, continúa.
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import yaml
from monai.losses import DiceCELoss
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.data import PatchDataset, organ_files_missing, split_files  # noqa: E402
from petct.device import describe_device, pick_device  # noqa: E402
from petct.models import CHANNELS_FULL, CHANNELS_SMALL, Decoder, Encoder, count_parameters  # noqa: E402
from petct.organs import GROUP_NAMES  # noqa: E402
from petct.train import poly_lr, seed_everything  # noqa: E402

N_CLASES = len(GROUP_NAMES)     # 17


class AnatomiaUNet(nn.Module):
    """Codificador de B (`enc`) + decodificador provisional de 17 clases. Solo `enc` sobrevive."""

    def __init__(self, channels):
        super().__init__()
        self.enc = Encoder(1, channels)
        self.dec = Decoder(channels, skip_mult=1, out_channels=N_CLASES)

    def forward(self, ct):
        feats = self.enc(ct)
        return self.dec(feats[-1], feats[:-1])


@torch.no_grad()
def dice_por_clase(model, parches, device):
    """Dice medio (sobre clases presentes en cada parche, sin 'fuera') en parches fijos de validación."""
    model.eval()
    dices = []
    for x, g in parches:
        x, g = x.to(device), g.to(device)
        pred = model(x[:, 1:2]).argmax(1)                     # (N, D, H, W)
        gt = g[:, 0]
        for c in range(1, N_CLASES):
            m_gt, m_pr = gt == c, pred == c
            n_gt = int(m_gt.sum())
            if n_gt == 0:
                continue
            dices.append(2 * float((m_gt & m_pr).sum()) / (n_gt + int(m_pr.sum())))
    model.train()
    return float(np.mean(dices)) if dices else float("nan")


def parches_fijos(files, parche, n, organs_dir, seed=7):
    """`n` parches de validación, siempre los mismos (semilla fija), centrados en el cuerpo."""
    ds = PatchDataset(files, parche, p_lesion=0.0, length=n, cache_size=8, augment=False,
                      seed=seed, organs_dir=organs_dir)
    out = []
    for i in range(n):
        x, _, g = ds[i]
        out.append((x[None], g[None]))
    return out


def guardar_encoder(path: Path, model, channels, it, dice):
    tmp = path.with_suffix(".tmp")
    torch.save({"enc_ct": model.enc.state_dict(), "channels": tuple(channels), "iter": it,
                "dice_val": dice, "clases": GROUP_NAMES}, tmp)
    tmp.replace(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--manifest", default="data/manifests/subconjunto_extendido.csv")
    ap.add_argument("--procesado", default="data/processed")
    ap.add_argument("--organos", default="data/processed_organos")
    ap.add_argument("--salida", default="runs/ct_anatomia")
    ap.add_argument("--dispositivo", default=None)
    ap.add_argument("--iteraciones", type=int, default=20_000)
    ap.add_argument("--lote", type=int, default=2)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--parche", type=int, default=96)
    ap.add_argument("--validar-cada", type=int, default=1000)
    ap.add_argument("--checkpoint-cada", type=int, default=500)
    ap.add_argument("--parches-val", type=int, default=40)
    ap.add_argument("--cache-estudios", type=int, default=256)
    ap.add_argument("--semilla", type=int, default=423)
    ap.add_argument("--small", action="store_true")
    ap.add_argument("--sin-reanudar", action="store_true")
    a = ap.parse_args()

    seed_everything(a.semilla)
    device = pick_device(a.dispositivo)
    print("dispositivo:", describe_device() if a.dispositivo is None else device, flush=True)
    channels = CHANNELS_SMALL if a.small else CHANNELS_FULL
    parche = (a.parche,) * 3
    out = Path(a.salida)
    out.mkdir(parents=True, exist_ok=True)

    splits = split_files(a.manifest, a.procesado)
    train_files, val_files = splits["train"], splits.get("val", [])
    faltan = organ_files_missing(train_files + val_files, a.organos)
    if faltan:
        sys.exit(f"faltan {len(faltan)} mapas de órganos en {a.organos}; primero: "
                 f"python scripts/11_organos_totalsegmentator.py --manifest {a.manifest} --particion train")

    model = AnatomiaUNet(channels).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-5)
    # Dice + CE sobre 17 clases, sin 'fuera' (el aire ya es trivial); misma familia de pérdida
    # que el entrenamiento de lesiones, para no introducir otra receta
    loss_fn = DiceCELoss(softmax=True, to_onehot_y=True, include_background=False)

    start_it, mejor = 0, -1.0
    ck_path = out / "ultimo.pt"
    if ck_path.exists() and not a.sin_reanudar:
        ck = torch.load(ck_path, map_location=device, weights_only=False)
        model.load_state_dict(ck["model"]); opt.load_state_dict(ck["optimizer"])
        start_it, mejor = int(ck["iter"]), float(ck.get("mejor", -1.0))
        print(f"[reanudar] desde la iteración {start_it}", flush=True)

    # p_lesion = 0: el centro cae en cualquier vóxel del cuerpo, sin sesgo a lesiones (acá no importan)
    ds = PatchDataset(train_files, parche, p_lesion=0.0, length=max(a.iteraciones * a.lote, 1000),
                      cache_size=a.cache_estudios, augment=True, seed=a.semilla + start_it, organs_dir=a.organos)
    loader = DataLoader(ds, batch_size=a.lote, shuffle=False, num_workers=0, drop_last=True)
    val_parches = parches_fijos(val_files, parche, a.parches_val, a.organos) if val_files else []

    print(f"anatomía: codificador {count_parameters(model.enc) / 1e6:.1f} M + decodificador provisional "
          f"{count_parameters(model.dec) / 1e6:.1f} M | {len(train_files)} estudios | {N_CLASES} clases | "
          f"{a.iteraciones} iteraciones | parche {parche} | lote {a.lote}", flush=True)

    log = out / "log_entrenamiento.csv"
    val_log = out / "validacion.csv"
    t0, it, losses = time.time(), start_it, []
    t_it = time.time()
    model.train()
    data_iter = iter(loader)
    while it < a.iteraciones:
        try:
            x, _, g = next(data_iter)
        except StopIteration:
            data_iter = iter(loader); x, _, g = next(data_iter)
        ct, g = x[:, 1:2].to(device), g.to(device)
        lr = poly_lr(a.lr, it, a.iteraciones)
        for grp in opt.param_groups:
            grp["lr"] = lr
        opt.zero_grad(set_to_none=True)
        loss = loss_fn(model(ct), g)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 12.0)
        opt.step()
        it += 1
        losses.append(float(loss.detach()))

        if it % 20 == 0 or it == a.iteraciones:
            dt = (time.time() - t_it) / 20; t_it = time.time()
            row = {"iter": it, "loss": float(np.mean(losses[-20:])), "lr": lr, "seg_por_iter": dt,
                   "minutos": (time.time() - t0) / 60}
            nuevo = not log.exists()
            with open(log, "a", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(row)); (w.writeheader() if nuevo else None); w.writerow(row)
            print(f"it {it:6d}  loss {row['loss']:.4f}  lr {lr:.2e}  {dt:.2f} s/it", flush=True)

        if val_parches and (it % a.validar_cada == 0 or it == a.iteraciones):
            d = dice_por_clase(model, val_parches, device)
            mejora = d > mejor
            if mejora:
                mejor = d
                guardar_encoder(out / "enc_ct_mejor.pt", model, channels, it, d)
            nuevo = not val_log.exists()
            with open(val_log, "a", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=["iter", "dice_organos", "mejor"])
                (w.writeheader() if nuevo else None); w.writerow({"iter": it, "dice_organos": d, "mejor": int(mejora)})
            print(f"  [val it {it}] Dice anatómico medio {d:.3f}" + ("  ← mejor" if mejora else ""), flush=True)

        if it % a.checkpoint_cada == 0 or it == a.iteraciones:
            tmp = ck_path.with_suffix(".tmp")
            torch.save({"model": model.state_dict(), "optimizer": opt.state_dict(), "iter": it, "mejor": mejor}, tmp)
            tmp.replace(ck_path)

    d_final = dice_por_clase(model, val_parches, device) if val_parches else float("nan")
    guardar_encoder(out / "enc_ct.pt", model, channels, it, d_final)      # el que usa B: el FINAL, no el "mejor"
    resumen = {"iteraciones": it, "dice_anatomico_final": d_final, "dice_anatomico_mejor": mejor,
               "minutos": (time.time() - t0) / 60, "parametros_enc": count_parameters(model.enc),
               "canales": list(channels), "clases": GROUP_NAMES, "args": vars(a)}
    json.dump(resumen, open(out / "resumen.json", "w"), indent=2, default=str)
    print("\nresumen:", {k: v for k, v in resumen.items() if k not in ("args", "clases")})


if __name__ == "__main__":
    main()
