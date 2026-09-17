#!/usr/bin/env python
"""Rama `extendido`. ¿Por qué la atención cruzada de C no contribuye? Diagnóstico sin entrenar.

Carga un C ya entrenado, le pasa parches reales de validación y mide, en el cuello de botella:

  entropia_norm   entropía de los pesos de atención, normalizada por su máximo (1 = uniforme,
                  cada posición del PET mira todas las del CT por igual → salida constante).
  std_esp(out)    desviación estándar ESPACIAL de la salida de la atención, relativa a la de
                  la consulta. Si es ~0, la salida es una constante espacial y la siguiente
                  normalización de instancia la elimina exactamente.
  std_esp(bottom) lo mismo para el cuello de botella después de `fuse`, con y sin atención:
                  si son iguales, la atención no dejó rastro.

Con eso se sabe si el arreglo es "que el softmax deje de estar plano" o si el problema es otro.

Uso:
    python scripts/28_diagnostico_atencion.py --checkpoint runs/C_ext_largo/ultimo.pt
"""
import argparse, sys
from pathlib import Path
import numpy as np, torch, yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from petct.data import split_files                       # noqa: E402
from petct.device import pick_device                     # noqa: E402
from petct.models import build_model                     # noqa: E402
from petct.preprocess import load_study, sample_patch    # noqa: E402
from petct.reference import stack_input                  # noqa: E402
from petct.train import load_weights                     # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--checkpoint", default="runs/C_ext_largo/ultimo.pt")
ap.add_argument("--manifest", default="data/manifests/subconjunto_extendido.csv")
ap.add_argument("--parches", type=int, default=24)
a = ap.parse_args()

device = pick_device(None)
model = build_model("C").to(device).eval()
load_weights(model, Path(a.checkpoint), device)
print(f"gamma = {float(model.cross.gamma):.4f}")

files = split_files(a.manifest, "data/processed", "val")
rng = np.random.default_rng(0)
ent, std_out, std_q, std_b_con, std_b_sin = [], [], [], [], []
with torch.no_grad():
    for i in range(a.parches):
        vol = load_study(files[i % len(files)])
        p = sample_patch(vol, (96, 96, 96), 0.7, rng)
        x = torch.from_numpy(stack_input(p["suv"], p["ct"], vol["suv_top"]))[None].to(device)
        pet, ct = x[:, 0:1], x[:, 1:2]
        bp, bc = model.enc_pet(pet)[-1], model.enc_ct(ct)[-1]          # (1, 320, 6, 6, 6)

        # 1. entropía de los pesos de atención
        w = model.cross.attention_maps(bp, bc)[0]                       # (216, 216)
        h = -(w * (w + 1e-12).log()).sum(1).mean()
        ent.append(float(h / np.log(w.shape[1])))

        # 2. ¿la salida de la atención varía en el espacio?
        n, c, d, hh, ww = bp.shape
        pe = __import__("petct.models", fromlist=["sincos_pos_3d"]).sincos_pos_3d((d, hh, ww), c, bp.device, bp.dtype)
        q = bp.flatten(2).transpose(1, 2); kv = bc.flatten(2).transpose(1, 2)
        out, _ = model.cross.attn(model.cross.norm_q(q) + pe, model.cross.norm_kv(kv) + pe,
                                  model.cross.norm_kv(kv) + pe, need_weights=False)
        std_out.append(float(out[0].std(0).mean()))     # std entre posiciones, media sobre canales
        std_q.append(float(q[0].std(0).mean()))

        # 3. ¿queda rastro después de fuse?
        fused_con = model.fuse(torch.cat([model.cross(bp, bc), bc], 1))
        fused_sin = model.fuse(torch.cat([bp, bc], 1))
        std_b_con.append(float(fused_con.flatten(2).std(2).mean()))
        std_b_sin.append(float(fused_sin.flatten(2).std(2).mean()))
        dif = float((fused_con - fused_sin).abs().max())
        if i == 0:
            print(f"diferencia máxima en el cuello de botella con/sin atención (parche 0): {dif:.2e}")

print(f"\n{a.parches} parches de validación, cuello de botella 6×6×6 = 216 posiciones")
print(f"entropía normalizada de la atención : {np.mean(ent):.4f}  (1,000 = perfectamente uniforme)")
print(f"std espacial de la salida de atención: {np.mean(std_out):.4f}")
print(f"std espacial de la consulta (PET)    : {np.mean(std_q):.4f}   → razón out/q = {np.mean(std_out)/np.mean(std_q):.4f}")
print(f"std espacial del cuello tras fuse    : con atención {np.mean(std_b_con):.4f}  sin {np.mean(std_b_sin):.4f}")
print()
if np.mean(ent) > 0.97:
    print("DIAGNÓSTICO: el softmax está plano. Cada posición promedia todo el CT, la salida es una")
    print("constante espacial y la normalización de instancia de `fuse` la elimina. El arreglo es")
    print("que el softmax discrimine: quitar el LayerNorm previo o escalar consultas y claves.")
elif np.mean(std_out) / np.mean(std_q) < 0.05:
    print("DIAGNÓSTICO: el softmax no es uniforme pero la salida igual es casi constante en el")
    print("espacio. Revisar los valores (V): si el CT del cuello es homogéneo, todas las respuestas")
    print("se parecen. El arreglo va por el lado del codificador de CT, no del softmax.")
else:
    print("DIAGNÓSTICO: la atención SÍ produce señal espacialmente variable. Entonces el rastro")
    print("se pierde más adelante; hay que mirar `fuse` y el decodificador.")
