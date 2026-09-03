"""Genera los notebooks del proyecto a partir de código Python (así quedan versionados
como texto legible y se pueden regenerar). Uso: python notebooks/build_notebooks.py
"""
import nbformat as nbf
from pathlib import Path

HERE = Path(__file__).resolve().parent


def nb(cells, path):
    n = nbf.v4.new_notebook()
    n.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    n.metadata["language_info"] = {"name": "python"}
    n.cells = [nbf.v4.new_markdown_cell(c[1]) if c[0] == "md" else nbf.v4.new_code_cell(c[1]) for c in cells]
    nbf.write(n, path)
    print("escrito", path)


# ============================================================ 00 · entorno
nb00 = [
("md", """# 00 · Revisión del entorno

Este cuaderno se corre una vez en cada máquina donde vaya a trabajar el proyecto
(el Mac con VS Code, y más adelante Colab). No procesa datos. Solo responde tres
preguntas: qué versiones hay instaladas, si PyTorch ve una GPU, y cuánta memoria y
disco quedan. Copia la salida de la última celda en la bitácora.

Por qué importa: el plan del proyecto reparte el trabajo en dos lugares. Todo lo que
sea leer DICOM, calcular SUV, remuestrear y evaluar corre en el Mac. El entrenamiento
con el presupuesto completo (25 000 iteraciones por modelo) corre en Colab, salvo que
el Mac tenga memoria de sobra y las pruebas cortas muestren que rinde. Esta celda es
la que decide."""),
("code", """import sys, platform, importlib, shutil, os

print("Python", sys.version.split()[0], "en", platform.platform())
print("Procesador:", platform.machine())

paquetes = ["numpy", "scipy", "pandas", "pydicom", "SimpleITK", "nibabel",
            "skimage", "matplotlib", "yaml", "pytest", "torch", "monai", "tcia_utils"]
for nombre in paquetes:
    try:
        mod = importlib.import_module(nombre)
        print(f"  {nombre:12s} {getattr(mod, '__version__', 'ok')}")
    except ImportError:
        print(f"  {nombre:12s} NO instalado")"""),
("md", """## ¿Hay GPU?

En Colab la respuesta esperada es `cuda`. En un Mac con chip M la respuesta es `mps`,
que es el nombre que PyTorch le da al chip gráfico de Apple. Si dice `cpu`, el
entrenamiento igual funciona, solo que mucho más lento."""),
("code", """import sys
sys.path.insert(0, "../src")
from petct.device import describe_device
print("Dispositivo que usaría PyTorch:", describe_device())"""),
("md", """## Memoria y disco

Regla práctica para este proyecto: los 250 estudios en NIfTI a resolución nativa
ocupan unos 25 GB; a 3 mm, menos de 8 GB. Un parche 3D de 96³ con dos canales y lote
de 2 pesa poco, pero la U-Net guarda activaciones intermedias, y ahí se van varios
GB. Con 16 GB de memoria unificada en el Mac alcanza para probar; para el presupuesto
completo conviene Colab o un Mac con 32 GB o más."""),
("code", """import shutil, os
total, usado, libre = shutil.disk_usage(os.getcwd())
print(f"Disco libre en esta carpeta: {libre / 2**30:.1f} GB de {total / 2**30:.1f} GB")
try:
    import psutil
    print(f"Memoria RAM total: {psutil.virtual_memory().total / 2**30:.1f} GB")
except ImportError:
    print("psutil no instalado; en el Mac: sysctl hw.memsize en la Terminal (bytes)")"""),
("md", """## Qué anotar en la bitácora

Fecha, máquina, versión de Python, dispositivo (`cuda`, `mps` o `cpu`), RAM y disco
libre. Con eso, cualquiera que lea el informe sabe en qué condiciones se corrió cada
etapa, y tú sabes si el Paso 3 se hace aquí o en Colab."""),
]

# ============================================================ 01 · datos y conversión
nb01 = [
("md", """# 01 · Datos: del DICOM al NIfTI con SUV

Este cuaderno recorre el Paso 1 completo. Primero con un fantoma sintético, que
funciona en cualquier computador sin descargar nada, y después con estudios reales
de autoPET si ya están en `data/raw`.

La idea del paso, en una frase: el scanner entrega cientos de archivos DICOM por
estudio, con los píxeles y una ficha de metadatos cada uno; nosotros necesitamos
cinco volúmenes limpios por estudio (CT, PET, SUV, CTres, SEG) en un formato que las
librerías de aprendizaje profundo entiendan (NIfTI). Las funciones que hacen el
trabajo viven en `src/petct/`; aquí se llaman y se explican."""),
("code", """import sys, tempfile
from pathlib import Path
import numpy as np
import SimpleITK as sitk
import matplotlib.pyplot as plt

RAIZ = Path.cwd().resolve().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "tests"))
from petct.suv import SUVParams, parse_dicom_time, suv_params_from_dataset
from petct.convert import convert_study, read_dicom_series
import synthetic
print("raíz del proyecto:", RAIZ)"""),
("md", """## 1. El SUV a mano

Antes de tocar archivos conviene entender el número que vamos a calcular miles de
veces. El scanner mide actividad en becquerel por mililitro. El SUV divide esa
actividad por la que habría si la dosis inyectada se hubiera repartido de manera
uniforme en todo el cuerpo (dosis dividida por peso). La analogía que uso: un frasco
de tinta en una piscina; el SUV dice cuántas veces más concentrada está la tinta en
un rincón respecto del promedio de la piscina.

Hay un detalle que se olvida fácil: entre la inyección y el scan pasa casi una hora,
y el flúor 18 pierde la mitad de su actividad cada 109,8 minutos. La dosis que se usa
en el denominador es la que queda en el cuerpo al momento del scan, no la que se
inyectó. Veamos los números con un caso típico."""),
("code", """p = SUVParams(weight_kg=70.0, injected_dose_bq=300e6, half_life_s=6586.2,
              injection_time=parse_dicom_time("100000"), scan_time=parse_dicom_time("110000"))
print(f"tiempo entre inyección y scan: {p.decay_time_s/60:.0f} min")
print(f"fracción de dosis que queda:   {p.decayed_dose_bq / p.injected_dose_bq:.3f}")
print(f"dosis corregida:               {p.decayed_dose_bq/1e6:.1f} MBq")
print(f"factor SUV (multiplica Bq/mL): {p.scale_factor:.6f}")
print(f"un vóxel con 3000 Bq/mL tiene SUV = {3000 * p.scale_factor:.2f}")"""),
("md", """Ese último número es el que importa clínicamente: 3000 Bq/mL en este paciente
equivale a SUV cerca de 1, es decir, captación promedio. Una lesión con SUV 8 tiene
ocho veces esa concentración.

## 2. Un fantoma para probar sin datos reales

`tests/synthetic.py` fabrica un estudio DICOM completo: un cuerpo elíptico de agua,
una esfera caliente de SUV 8 sobre fondo de SUV 1, un CT a 2 mm y un PET a 4 mm (a
propósito con distinta resolución, como en la realidad), y un DICOM SEG con los
cortes guardados en orden inverso para comprobar que la conversión usa la posición
física de cada corte y no su orden en el archivo. Es el mismo papel que cumple el
fantoma de control de calidad del PET: un objeto con respuesta conocida."""),
("code", """raiz_fantoma = Path(tempfile.mkdtemp(prefix="fantoma_"))
verdad = synthetic.make_phantom(raiz_fantoma)
for carpeta in ("CT", "PT", "SEG"):
    n = len(list((raiz_fantoma / carpeta).glob("*.dcm")))
    print(f"{carpeta}: {n} archivos DICOM")"""),
("md", """## 3. Leer los metadatos del PET y calcular el factor

`suv_params_from_dataset` abre la ficha DICOM de una lámina PET y saca de ahí el
peso, la dosis, la semivida y las dos horas. Si alguna etiqueta falta, o las
unidades no son Bq/mL, la función se detiene con un error en vez de seguir con un
SUV inventado. Ese comportamiento es deliberado: un estudio sin SUV confiable no
sirve para el proyecto y se registra en `errores_conversion.csv`."""),
("code", """import pydicom
primera = sorted((raiz_fantoma / "PT").glob("*.dcm"))[0]
ds = pydicom.dcmread(primera, stop_before_pixels=True)
print("Units:", ds.Units, "| DecayCorrection:", ds.DecayCorrection, "| peso:", ds.PatientWeight, "kg")
params = suv_params_from_dataset(ds)
print(f"factor leído del DICOM: {params.scale_factor:.6f}")
print(f"factor esperado:        {verdad['suv_factor']:.6f}")"""),
("md", """## 4. Convertir el estudio completo

`convert_study` hace todo el trabajo: lee las tres series, escribe CT y PET, aplica el
factor para obtener SUV, remuestrea el CT sobre la grilla del PET (CTres) y convierte
el SEG a máscara. CTres merece una explicación. El CT tiene vóxeles de 2 mm y el PET
de 4 mm en este fantoma (en autoPET, cerca de 1 mm contra 2 mm). La red necesita dos
tensores del mismo tamaño y alineados vóxel a vóxel, así que el CT se "vuelve a
fotografiar" con la cámara del PET: para cada vóxel del PET se calcula el valor de CT
en esa misma posición física por interpolación lineal. Se pierde detalle del CT, pero
se gana lo único que la red puede usar: correspondencia exacta."""),
("code", """salidas = convert_study(raiz_fantoma, raiz_fantoma / "nifti")
for nombre, ruta in salidas.items():
    img = sitk.ReadImage(str(ruta))
    print(f"{nombre:6s} tamaño (x,y,z) = {img.GetSize()}  espaciado = {tuple(round(s,2) for s in img.GetSpacing())} mm")"""),
("md", """CT quedó en 64 × 64 y CTres en 32 × 32, la grilla del PET. Ahora la verificación
visual y numérica, que es lo que uno haría con un estudio real en 3D Slicer."""),
("code", """ct = sitk.GetArrayFromImage(sitk.ReadImage(str(salidas["CT"])))
ctres = sitk.GetArrayFromImage(sitk.ReadImage(str(salidas["CTres"])))
suv = sitk.GetArrayFromImage(sitk.ReadImage(str(salidas["SUV"])))
seg = sitk.GetArrayFromImage(sitk.ReadImage(str(salidas["SEG"])))
z = 10
fig, ax = plt.subplots(1, 4, figsize=(13, 3.4))
ax[0].imshow(ct[z], cmap="gray", vmin=-200, vmax=300); ax[0].set_title("CT nativo (2 mm)")
ax[1].imshow(ctres[z], cmap="gray", vmin=-200, vmax=300); ax[1].set_title("CTres (grilla PET, 4 mm)")
im = ax[2].imshow(suv[z], cmap="inferno", vmin=0, vmax=8); ax[2].set_title("SUV"); plt.colorbar(im, ax=ax[2], fraction=0.046)
ax[3].imshow(suv[z], cmap="gray", vmin=0, vmax=8); ax[3].contour(seg[z], levels=[0.5], colors="cyan"); ax[3].set_title("SEG sobre SUV")
for a in ax: a.axis("off")
plt.tight_layout(); plt.show()

lesion = verdad["lesion_pet"]; fondo = verdad["body_pet"] & ~lesion
print(f"SUV mediana en lesión: {np.median(suv[lesion]):.2f}   en fondo: {np.median(suv[fondo]):.2f}")
inter = (seg.astype(bool) & lesion).sum()
print(f"Dice entre SEG convertido y verdad: {2*inter/(seg.sum()+lesion.sum()):.4f}")"""),
("md", """Los tres números que hay que mirar: lesión cerca de 8, fondo cerca de 1, Dice cerca
de 1. Si alguno falla con un estudio real, el problema está en las etiquetas del
DICOM (unidades, horas) o en la geometría del SEG, y ahí hay que detenerse.

## 5. Con estudios reales de autoPET

Esta sección solo corre si ya ejecutaste `scripts/02_descargar_tcia.py` en tu
computador (la API de TCIA no es alcanzable desde todos los entornos). Convierte los
estudios que encuentre en `data/raw` usando la tabla `data/manifests/series_tcia.csv`
y muestra el primero. Con datos reales los valores esperables son: fondo hepático SUV
2 a 3, encéfalo SUV 6 a 10, vejiga a veces sobre 30, y las lesiones anotadas dentro
de zonas calientes del PET."""),
("code", """import pandas as pd, os
series_csv = RAIZ / "data/manifests/series_tcia.csv"
raw = RAIZ / "data/raw"
if series_csv.exists() and any(raw.iterdir()):
    series = pd.read_csv(series_csv)
    print(series.groupby("Modality").size())
    # convertir con el script (agrupa por estudio y maneja errores)
    !python {RAIZ}/scripts/03_convertir_a_nifti.py --raw {raw} --series-csv {series_csv} --out {RAIZ}/data/interim/nifti
else:
    print("Todavía no hay datos reales en data/raw. Corre scripts/01 y 02 en tu computador y vuelve aquí.")"""),
("code", """nifti = RAIZ / "data/interim/nifti"
estudios = sorted(nifti.glob("*/*/SUV.nii.gz"))
if estudios:
    carpeta = estudios[0].parent
    suv = sitk.GetArrayFromImage(sitk.ReadImage(str(carpeta / "SUV.nii.gz")))
    seg = sitk.GetArrayFromImage(sitk.ReadImage(str(carpeta / "SEG.nii.gz")))
    ctres = sitk.GetArrayFromImage(sitk.ReadImage(str(carpeta / "CTres.nii.gz")))
    print("estudio:", carpeta.relative_to(nifti), "| forma (z,y,x):", suv.shape)
    print(f"SUV máximo: {suv.max():.1f}  | vóxeles de lesión: {int(seg.sum())}  | volumen ≈ {seg.sum()*np.prod(sitk.ReadImage(str(carpeta/'SUV.nii.gz')).GetSpacing())/1000:.1f} mL")
    # proyección de intensidad máxima (MIP) coronal: la "foto" clásica del PET
    mip = suv.max(axis=1)
    fig, ax = plt.subplots(1, 2, figsize=(8, 8))
    ax[0].imshow(np.flipud(mip), cmap="gray_r", vmin=0, vmax=8, aspect="auto"); ax[0].set_title("MIP coronal SUV")
    ax[1].imshow(np.flipud(mip), cmap="gray_r", vmin=0, vmax=8, aspect="auto")
    ax[1].contour(np.flipud(seg.max(axis=1)), levels=[0.5], colors="red"); ax[1].set_title("lesiones anotadas")
    for a in ax: a.axis("off")
    plt.tight_layout(); plt.show()
else:
    print("Sin estudios convertidos aún.")"""),
("md", """## Qué registrar en la bitácora al terminar

Cuántos estudios se convirtieron y cuántos fallaron (y por qué), el rango de SUV
máximo que viste, si las lesiones anotadas coinciden con las zonas calientes en el
MIP, y cualquier decisión que hayas tomado (por ejemplo, excluir un estudio con
etiquetas incompletas). Con eso el Paso 1 queda cerrado y se abre el Paso 2."""),
]


# ============================================================ 02 · preprocesamiento y referencia clásica
nb02 = [
("md", """# 02 · Preprocesamiento y referencia clásica

Este cuaderno cubre el Paso 2. Toma los NIfTI del Paso 1 y los deja en la forma en que
la red los va a mirar, y después construye la referencia clásica: una segmentación sin
ninguna red, con las herramientas del curso (umbral, morfología, componentes conexas),
medida con las métricas oficiales de autoPET. Ese número es el piso. Si un modelo no lo
supera, algo está mal en el modelo, no en la idea.

Como en el cuaderno anterior, todo corre primero sobre fantomas que se fabrican aquí
mismo; la última sección se activa sola cuando hay estudios reales."""),
("code", """import sys, tempfile
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

RAIZ = Path.cwd().resolve().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(RAIZ / "src")); sys.path.insert(0, str(RAIZ / "tests"))
from petct.convert import convert_study
from petct.preprocess import preprocess_study, load_study, sample_patch, window_ct, scale_suv, body_mask
from petct.classical import classical_segmentation, heuristic_organ_masks, threshold_suv, clean_mask
from petct.metrics import evaluate_study
import synthetic
ML = 0.027   # mL por vóxel a 3 mm: 0.3 cm x 0.3 cm x 0.3 cm
print("raíz:", RAIZ)"""),
("md", """## 1. Ventaneo del CT y tope del SUV

Las dos operaciones puntuales del paso. El ventaneo es lo mismo que hace la consola
cuando eliges "ventana de tejido blando": todo lo que está bajo −200 HU se vuelve 0,
todo lo que pasa de 300 HU se vuelve 1, y el medio queda lineal. La red no necesita
distinguir hueso cortical de hueso esponjoso, pero sí grasa de músculo de agua.

El SUV se divide por 30 y se recorta a 1. Sin ese tope, la vejiga (que llega a SUV 50
o más) obligaría a comprimir todo el resto del cuerpo en el primer 5 % de la escala."""),
("code", """hu = np.linspace(-1000, 1500, 500)
suv = np.linspace(0, 60, 500)
fig, ax = plt.subplots(1, 2, figsize=(9, 3))
ax[0].plot(hu, window_ct(hu)); ax[0].set_xlabel("HU"); ax[0].set_ylabel("valor de entrada"); ax[0].set_title("ventana de tejido blando")
ax[0].axvspan(-200, 300, alpha=.1)
ax[1].plot(suv, scale_suv(suv)); ax[1].set_xlabel("SUV"); ax[1].set_title("SUV / 30 con tope")
ax[1].axvline(2.5, ls="--", c="gray"); ax[1].text(3, .5, "umbral 2,5", color="gray")
plt.tight_layout(); plt.show()"""),
("md", """## 2. El fantoma del Paso 1 pasa por el preprocesamiento

`preprocess_study` remuestrea a 3 mm isotrópicos (el PET del fantoma tenía vóxeles de
4 × 4 × 2 mm), calcula la máscara del cuerpo desde el CT, recorta a la caja que contiene
al paciente y guarda un `.npz` con `suv`, `ct`, `seg` y `body` alineados. Ese archivo es
lo que leerán los parches y los modelos: un estudio de 250 se abre en milisegundos."""),
("code", """root = Path(tempfile.mkdtemp(prefix="p2_"))
synthetic.make_phantom(root)
convert_study(root, root / "nifti")
info = preprocess_study(root / "nifti", root / "proc" / "fantoma.npz")
vol = load_study(root / "proc" / "fantoma.npz")
print("forma tras remuestrear y recortar (z, y, x):", vol["suv"].shape)
print(f"vóxeles de lesión: {info['lesion_voxels']}  ≈ {info['lesion_voxels']*ML:.2f} mL (esfera de 9 mm: 3.05 mL)")
print(f"fracción del volumen que es cuerpo: {vol['body'].mean():.2f}")"""),
("md", """## 3. Parches sesgados a lesiones

La red no ve el cuerpo entero: ve cubos de 96³ vóxeles (29 cm de lado a 3 mm). Si los
cubos se eligieran al azar, la mayoría no tendría ni un vóxel de lesión (las lesiones son
menos del 1 % del cuerpo) y la red aprendería que la respuesta correcta es siempre
"nada". Por eso el 70 % de los parches se centra en un vóxel de lesión y el 30 % en un
vóxel cualquiera del cuerpo. En el fantoma usamos cubos chicos para poder dibujarlos."""),
("code", """rng = np.random.default_rng(423)
con = sum(sample_patch(vol, (16, 16, 16), p_lesion=0.7, rng=rng)["with_lesion"] for _ in range(200))
print(f"de 200 parches con p_lesion = 0.7, {con} contienen lesión")
p = sample_patch(vol, (16, 16, 16), p_lesion=1.0, rng=rng)
z = p["seg"].sum(axis=(1, 2)).argmax()
fig, ax = plt.subplots(1, 3, figsize=(9, 3))
ax[0].imshow(p["ct"][z], cmap="gray", vmin=0, vmax=1); ax[0].set_title("canal CT [0,1]")
ax[1].imshow(p["suv"][z], cmap="inferno", vmin=0, vmax=0.3); ax[1].set_title("canal SUV [0,1]")
ax[2].imshow(p["seg"][z], cmap="gray"); ax[2].set_title("máscara")
for a in ax: a.axis("off")
plt.tight_layout(); plt.show()"""),
("md", """## 4. La referencia clásica, con un fantoma más parecido a un paciente

Para ver lo que el umbral hace mal hace falta un cuerpo con órganos calientes. Este
fantoma se arma directo en NumPy, ya a 3 mm: un cilindro de 60 cm de alto con fondo SUV
1, un "encéfalo" de SUV 7 arriba, una "vejiga" de SUV 25 abajo, un "hígado" de SUV 2,2
(justo bajo el umbral) y dos lesiones, una de SUV 6 y otra de SUV 4.

La receta clásica tiene cuatro pasos y conviene mirar cada uno por separado: umbral,
apertura morfológica, tamaño mínimo y exclusión anatómica. Los tres primeros son lo que
un físico médico habría hecho hace veinte años. El cuarto es el que decide el resultado y
depende de tener máscaras de órganos; mientras no las tengamos, dos reglas provisionales
buscan el encéfalo (la componente caliente grande más alta) y la vejiga (la componente
muy intensa más baja). Un detalle que importa: en este fantoma la cabeza está en el
índice 0 del arreglo; en los NIfTI de autoPET está al final, porque en DICOM la
coordenada z crece hacia la cabeza. Por eso las funciones reciben `head_at_end`."""),
("code", """def paciente_sintetico():
    Z, Y, X = 200, 100, 100                     # 60 x 30 x 30 cm a 3 mm
    zz, yy, xx = np.mgrid[:Z, :Y, :X]
    body = ((yy - 50) / 45) ** 2 + ((xx - 50) / 45) ** 2 <= 1
    suv = np.where(body, 1.0, 0.0)
    def esfera(c, r): return (zz - c[0]) ** 2 + (yy - c[1]) ** 2 + (xx - c[2]) ** 2 <= r ** 2
    suv[esfera((15, 50, 50), 20)] = 7.0          # encéfalo: ~900 mL
    suv[esfera((170, 50, 50), 10)] = 25.0        # vejiga: ~110 mL
    higado = esfera((90, 45, 35), 18); suv[higado] = 2.2
    seg = np.zeros_like(body)
    for c, r, s in (((70, 50, 65), 5, 6.0), ((120, 40, 50), 3, 4.0)):
        m = esfera(c, r); suv[m] = s; seg |= m
    return suv, body, seg

suv_p, body_p, seg_p = paciente_sintetico()
print(f"lesiones anotadas: {seg_p.sum()*ML:.1f} mL")

etapas = {}
etapas["1 umbral 2,5"] = threshold_suv(suv_p) & body_p
etapas["2+3 apertura y tamaño"] = clean_mask(etapas["1 umbral 2,5"], 1, 0.5, ML)
etapas["4 exclusión anatómica"] = classical_segmentation(suv_p, body_p, ML, head_at_end=False)
for nombre, m in etapas.items():
    r = evaluate_study(m, seg_p, suv_p, ML)
    print(f"{nombre:26s} Dice={r['dice']:.3f}  FPV={r['fpv_ml']:7.1f} mL  FNV={r['fnv_ml']:.1f} mL  MTV pred={r['mtv_pred_ml']:.1f} mL")"""),
("md", """Léelo como un radiólogo: el umbral solo marca el encéfalo y la vejiga como tumor y el
MTV se dispara a más de mil mililitros. La apertura y el tamaño mínimo no cambian nada,
porque esos órganos son grandes y compactos. Solo la exclusión anatómica baja el FPV a
cero. Esa es la hipótesis del proyecto entero, dicha con reglas fijas: la anatomía es lo
que separa captación fisiológica de patológica. Los modelos B y C intentan que la red
aprenda esa regla sola a partir del CT."""),
("code", """organos = heuristic_organ_masks(suv_p, body_p, ML, head_at_end=False)
mip = suv_p.max(axis=1)
fig, ax = plt.subplots(1, 3, figsize=(10, 6))
ax[0].imshow(mip, cmap="gray_r", vmin=0, vmax=8, aspect="auto"); ax[0].set_title("MIP SUV")
ax[1].imshow(mip, cmap="gray_r", vmin=0, vmax=8, aspect="auto"); ax[1].contour(etapas["1 umbral 2,5"].max(axis=1), levels=[.5], colors="red"); ax[1].set_title("umbral 2,5 (rojo)")
ax[2].imshow(mip, cmap="gray_r", vmin=0, vmax=8, aspect="auto")
for nombre, m in organos.items():
    ax[2].contour(m.max(axis=1), levels=[.5], colors="orange")
ax[2].contour(etapas["4 exclusión anatómica"].max(axis=1), levels=[.5], colors="cyan"); ax[2].set_title("órganos (naranja) y resultado (cian)")
for a in ax: a.axis("off")
plt.tight_layout(); plt.show()"""),
("md", """## 5. Con estudios reales

Se activa cuando `data/processed` tiene archivos `.npz` (salida de `scripts/04`). Corre
la referencia clásica en todos y muestra la tabla. Con pacientes de verdad hay que
esperar Dice bajo y FPV alto, incluso con la exclusión heurística: el corazón, los
riñones y el intestino no están cubiertos por las dos reglas, y las lesiones de SUV 3
quedan pegadas al hígado. Ese es el punto: documentar cuánto falla la receta clásica y en
qué órganos, para tener contra qué comparar los modelos."""),
("code", """import pandas as pd
proc = sorted((RAIZ / "data/processed").glob("*.npz"))
if proc:
    filas = []
    for f in proc:
        v = load_study(f); suv_r = v["suv"] * v["suv_top"]
        pred = classical_segmentation(suv_r, v["body"], ML, head_at_end=v["head_at_end"])
        r = evaluate_study(pred, v["seg"], suv_r, ML); r["estudio"] = f.stem[:20]; filas.append(r)
    df = pd.DataFrame(filas).set_index("estudio")
    display(df.round(2))
    print("promedio Dice / FPV / FNV:", df[["dice", "fpv_ml", "fnv_ml"]].mean().round(2).to_dict())
else:
    print("Todavía no hay estudios procesados. Corre scripts/04_preprocesar.py después del Paso 1.")"""),
("md", """## Qué registrar en la bitácora

La forma típica de los volúmenes a 3 mm (para dimensionar memoria), cuántos estudios
fallaron en el preprocesamiento, y la tabla de la referencia clásica con su promedio de
Dice, FPV y FNV. Ese promedio es el primer número del informe."""),
]

nb(nb02, HERE / "02_preprocesamiento_referencia_clasica.ipynb")


# ============================================================ 01b · geometría DICOM
nb01b = [
("md", """# 01b · Geometría DICOM: posiciones de corte, espaciado y medidas

Este cuaderno desarrolla el punto del Laboratorio 1 ("ordene por `ImagePositionPatient`,
mida el espaciado efectivo, compárelo con `SliceThickness`, corrija la relación de
aspecto y cuantifique el error") sobre los datos del proyecto, para PET y CT. El texto
completo está en `docs/GEOMETRIA_DICOM.md`; aquí se ejecuta.

Corre con lo que haya en `data/raw`. Con tres pacientes ya muestra todo; con los 251 la
tabla final se convierte en la estadística de la colección. Si no hay datos reales, usa
el fantoma sintético para que ninguna celda falle."""),
("code", """import sys, glob, tempfile
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
import pydicom, SimpleITK as sitk

RAIZ = Path.cwd().resolve().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(RAIZ / "src")); sys.path.insert(0, str(RAIZ / "tests"))
from petct.geometry import series_geometry, index_to_mm, measurement_error_if_aspect_ignored
import synthetic

series_csv = RAIZ / "data/manifests/series_tcia.csv"
raw = RAIZ / "data/raw"
reales = series_csv.exists() and raw.exists() and any(p.is_dir() for p in raw.iterdir())
if reales:
    ser = pd.read_csv(series_csv)
    ser = ser[ser.Modality.isin(["CT", "PT"]) & ser.SeriesInstanceUID.map(lambda u: (raw / str(u)).exists())]
    carpetas = {(r.PatientID, r.Modality): raw / str(r.SeriesInstanceUID) for _, r in ser.iterrows()}
    print(f"{len(carpetas)} series reales de {ser.PatientID.nunique()} pacientes")
else:
    tmp = Path(tempfile.mkdtemp(prefix="geo_")); synthetic.make_phantom(tmp)
    carpetas = {("FANTOMA", "CT"): tmp / "CT", ("FANTOMA", "PT"): tmp / "PT"}
    print("sin datos reales: usando el fantoma sintético")"""),
("md", """## 1. Leer la cabecera de un corte

Cada archivo DICOM lleva, además de los píxeles, la ficha con su geometría. Cuatro
atributos bastan para ubicar cualquier píxel en el espacio del paciente: la posición del
primer píxel (`ImagePositionPatient`), la orientación de filas y columnas
(`ImageOrientationPatient`), el tamaño del píxel (`PixelSpacing`) y el grosor del corte
(`SliceThickness`). Miremos el primer archivo de una serie PET y una CT."""),
("code", """def ficha(folder):
    f = sorted(p for p in Path(folder).iterdir() if p.suffix == ".dcm")[0]
    ds = pydicom.dcmread(str(f), stop_before_pixels=True)
    campos = ["Modality", "PatientPosition", "Rows", "Columns", "PixelSpacing", "SliceThickness",
              "SpacingBetweenSlices", "ImagePositionPatient", "ImageOrientationPatient",
              "InstanceNumber", "SliceLocation", "FrameOfReferenceUID"]
    return {c: ds.get(c, "(ausente)") for c in campos}

for (pid, mod), folder in list(carpetas.items())[:2]:
    print(f"== {pid} {mod}")
    for k, v in ficha(folder).items():
        print(f"   {k:24s} {str(v)[:70]}")"""),
("md", """`SpacingBetweenSlices` aparece como ausente: la distancia entre cortes no está
declarada y hay que medirla. `PatientPosition = HFS` (cabeza primero, decúbito supino)
dice cómo entró el paciente al equipo. Y `FrameOfReferenceUID` es el mismo para PET y CT
del mismo estudio: comparten origen y ejes, por eso se superponen por milímetros.

## 2. El orden de los cortes

La advertencia del laboratorio es que el orden alfabético no garantiza el orden
anatómico. Para comprobarlo se lee la posición z de cada archivo en el orden en que
vienen nombrados. `series_geometry` hace además el ordenamiento correcto: proyecta cada
posición sobre la normal al plano (producto cruz de los dos vectores de orientación) y
ordena por ese número."""),
("code", """def z_por_nombre(folder):
    zs = []
    for f in sorted(p for p in Path(folder).iterdir() if p.is_file() and not p.name.startswith(".")):
        try:
            zs.append(float(pydicom.dcmread(str(f), stop_before_pixels=True).ImagePositionPatient[2]))
        except Exception:      # cada carpeta de TCIA trae un archivo LICENSE
            pass
    return np.array(zs)

pid0 = list(carpetas)[0][0]
fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
for mod in ("PT", "CT"):
    z = z_por_nombre(carpetas[(pid0, mod)])
    ax[0].plot(z, ".", ms=3, label=f"{mod}: {len(z)} archivos")
    ax[1].plot(np.diff(np.sort(z)), ".", ms=3, label=f"{mod}: {np.diff(np.sort(z)).mean():.2f} mm")
ax[0].set_xlabel("índice del archivo (orden alfabético)"); ax[0].set_ylabel("z de ImagePositionPatient (mm)"); ax[0].legend(); ax[0].set_title(f"{pid0}: posición real de cada archivo")
ax[1].set_xlabel("par de cortes consecutivos (ordenados)"); ax[1].set_ylabel("distancia (mm)"); ax[1].legend(); ax[1].set_title("espaciado efectivo"); ax[1].set_ylim(0, None)
plt.tight_layout(); plt.show()"""),
("md", """En autoPET el PET viene de los pies a la cabeza y el CT de la cabeza a los pies. El
nombre y el `InstanceNumber` coinciden entre sí en ambos, así que ninguno sirve como
criterio general. La única regla robusta es la posición física, y es la que usa SimpleITK
al leer una serie y la que usa `convert.py`.

## 3. Grosor frente a espaciado

Son dos cosas distintas: el grosor es cuánto tejido promedia cada corte reconstruido; el
espaciado es cada cuántos milímetros hay un corte. La tabla los pone lado a lado para
todas las series disponibles, junto con el campo de visión y la relación de aspecto."""),
("code", """filas = []
for (pid, mod), folder in carpetas.items():
    g = series_geometry(folder); g.pop("positions_sorted_mm"); g["patient_id"] = pid; filas.append(g)
geo = pd.DataFrame(filas)
cols = ["patient_id", "modality", "n_slices", "rows", "row_spacing_mm", "fov_rows_mm", "slice_thickness_mm",
        "gap_mean_mm", "gap_min_mm", "gap_max_mm", "uniform", "extent_mm", "order_by_name_ok", "aspect_coronal"]
geo["solape_mm"] = (geo.slice_thickness_mm - geo.gap_mean_mm).round(2)
display(geo[cols + ["solape_mm"]].round(3))"""),
("md", """Lectura: en el PET grosor y espaciado coinciden (3 mm cada 3 mm, contiguos). En el CT
el grosor es mayor que el espaciado: reconstrucción con solape, habitual en CT
helicoidal. No es un error de los datos; el error sería usar el grosor para armar el
volumen. Cuando la colección completa esté descargada, esta tabla dice cuántos CT vienen
con cada combinación de grosor y espaciado, que es un dato para la sección de materiales
del informe.

## 4. De índices a milímetros

La ecuación del módulo Image Plane: la posición de la fila i, columna j del corte k es
el origen del corte más j veces el espaciado de columnas en la dirección de las columnas,
más i veces el espaciado de filas en la dirección de las filas. Es una transformación
afín, la misma que guardan SimpleITK (origen, espaciado, dirección) y NIfTI. Un ejemplo
con la serie PET: el vóxel del centro del primer corte."""),
("code", """g = series_geometry(carpetas[(pid0, "PT")])
col_dir, row_dir = np.array(g["iop"][:3]), np.array(g["iop"][3:])
p = index_to_mm(g["rows"] // 2, g["cols"] // 2, 0, g["origin_first_slice"], g["row_spacing_mm"], g["col_spacing_mm"],
                col_dir, row_dir, g["normal"], g["gap_mean_mm"])
print("origen del primer corte (mm):", g["origin_first_slice"])
print("centro del primer corte (mm): ", p.round(1))
print("normal al corte:", g["normal"], "→ cada corte siguiente está", g["gap_mean_mm"], "mm más arriba (z crece hacia la cabeza)")"""),
("md", """## 5. Relación de aspecto y el error que se comete al ignorarla

En una vista coronal o sagital el eje vertical es z. Si se dibuja el arreglo con píxeles
cuadrados, cada corte ocupa un píxel de alto aunque mida 3 mm. El factor de corrección es
Δz / Δplano. El error de medida para un segmento vertical es directo: aparece con longitud
L · Δplano / Δz. Para un segmento oblicuo el error depende del ángulo; la función lo
calcula para cualquier caso."""),
("code", """for _, r in geo.iterrows():
    e90 = measurement_error_if_aspect_ignored(30, 90, r.row_spacing_mm, r.gap_mean_mm)
    e45 = measurement_error_if_aspect_ignored(30, 45, r.row_spacing_mm, r.gap_mean_mm)
    print(f"{r.patient_id} {r.modality}: aspecto {r.aspect_coronal:.2f} | un segmento vertical de 30 mm 'mide' {30*(1+e90):.1f} mm ({e90:+.0%}); a 45°, {30*(1+e45):.1f} mm ({e45:+.0%})")

# vistas coronal y sagital con y sin corrección, del primer paciente (desde los NIfTI si existen)
nii = sorted((RAIZ / "data/interim/nifti").glob(f"{pid0}/*/SUV.nii.gz")) if reales else []
if nii:
    suv = sitk.ReadImage(str(nii[0])); ct = sitk.ReadImage(str(nii[0].parent / "CT.nii.gz"))
    A, C = sitk.GetArrayFromImage(suv), sitk.GetArrayFromImage(ct)
    sp, sc = suv.GetSpacing(), ct.GetSpacing()
    fig, ax = plt.subplots(1, 4, figsize=(13, 6))
    ax[0].imshow(np.flipud(A[:, A.shape[1]//2, :]), cmap="gray_r", vmin=0, vmax=6, aspect=sp[2]/sp[0]); ax[0].set_title(f"PET coronal, aspecto {sp[2]/sp[0]:.2f}")
    ax[1].imshow(np.flipud(A[:, A.shape[1]//2, :]), cmap="gray_r", vmin=0, vmax=6, aspect=1); ax[1].set_title("PET coronal, aspecto ignorado")
    ax[2].imshow(np.flipud(C[:, C.shape[1]//2, :]), cmap="gray", vmin=-200, vmax=300, aspect=sc[2]/sc[0]); ax[2].set_title(f"CT coronal, aspecto {sc[2]/sc[0]:.2f}")
    ax[3].imshow(np.flipud(C[:, C.shape[1]//2, :]), cmap="gray", vmin=-200, vmax=300, aspect=1); ax[3].set_title("CT coronal, aspecto ignorado")
    for a in ax: a.axis("off")
    plt.tight_layout(); plt.show()
else:
    print("(las vistas coronales se muestran cuando existen los NIfTI del Paso 1)")"""),
("md", """La cabeza va arriba en las figuras porque se voltea el eje z para dibujar: en el arreglo,
el índice 0 es el corte más inferior.

## 6. La segmentación es distinta: un solo archivo con muchos frames

El DICOM SEG de autoPET trae los 284 cortes de la máscara como frames de un único objeto,
cada uno con su propia posición, y con las filas recorridas al revés que el PET
(`ImageOrientationPatient` 1,0,0,0,−1,0). Si se apilan los frames sin mirar la
orientación, la máscara queda reflejada. El fantoma sintético reproduce ese caso y la
conversión lo resuelve ubicando las dos esquinas físicas de cada frame en la grilla del
PET. Aquí se muestra la cabecera de un SEG real si existe."""),
("code", """seg_ds = None
if reales:
    for d in sorted(p for p in raw.iterdir() if p.is_dir()):
        dcms = sorted(d.glob("*.dcm"))
        if len(dcms) == 1:                      # el SEG es un solo archivo multiframe
            ds = pydicom.dcmread(str(dcms[0]), stop_before_pixels=True)
            if ds.Modality == "SEG":
                seg_ds = ds; break
if seg_ds is not None:
    sh = seg_ds.SharedFunctionalGroupsSequence[0]
    fr = seg_ds.PerFrameFunctionalGroupsSequence
    print("frames:", seg_ds.NumberOfFrames, "| Rows x Cols:", seg_ds.Rows, "x", seg_ds.Columns)
    print("orientación compartida:", list(sh.PlaneOrientationSequence[0].ImageOrientationPatient))
    print("PixelSpacing compartido:", list(sh.PixelMeasuresSequence[0].PixelSpacing))
    print("posición de los 3 primeros frames:", [list(map(float, fg.PlanePositionSequence[0].ImagePositionPatient)) for fg in fr[:3]])
    print("segmentos:", [s.SegmentLabel for s in seg_ds.SegmentSequence])
else:
    print("sin SEG real disponible; ver tests/synthetic.py::write_seg para el caso reproducido")"""),
("md", """## Qué registrar en la bitácora

Cuando la descarga esté completa: cuántas series CT vienen con cada grosor y espaciado,
si alguna no es uniforme, cuántos pacientes tienen un campo de visión de CT que no cubre
los brazos, y si aparece alguna serie con orientación distinta de la axial pura. Esa es
la descripción geométrica de los datos para el informe."""),
]

nb(nb01b, HERE / "01b_geometria_dicom.ipynb")

nb(nb00, HERE / "00_entorno.ipynb")
nb(nb01, HERE / "01_datos_suv_conversion.ipynb")
