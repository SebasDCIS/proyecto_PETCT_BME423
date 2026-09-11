#!/usr/bin/env bash
# Genera el .docx y el .pdf de la definicion de tema desde definicion_de_tema.md.
# El .docx es el entregable editable; el .pdf es la version para imprimir o subir.
set -e
cd "$(dirname "$0")"

# --- Word -------------------------------------------------------------------
pandoc --print-default-data-file reference.docx > _ref.docx
rm -rf _ref && mkdir _ref && (cd _ref && unzip -q ../_ref.docx)
python3 ajustar_estilos.py                 # cuerpo a 9,5 pt, margenes, estilo Referencias
(cd _ref && zip -Xrq ../_ref2.docx .)
pandoc definicion_de_tema.md -f markdown -t docx --reference-doc=_ref2.docx -o definicion_de_tema.docx
rm -rf _out && mkdir _out && (cd _out && unzip -q ../definicion_de_tema.docx)
python3 ajustar_secciones.py                            # pandoc deja el sectPr vacio; aca va la pagina A4
(cd _out && zip -Xrq ../_n.docx .) && mv -f _n.docx definicion_de_tema.docx

# --- PDF --------------------------------------------------------------------
python3 armar_html.py
wkhtmltopdf --quiet --enable-local-file-access --page-size A4 \
  --margin-top 0 --margin-bottom 0 --margin-left 0 --margin-right 0 \
  _doc.html definicion_de_tema.pdf

rm -rf _ref _ref.docx _ref2.docx _out _doc.html
python3 - <<'PY'
from pypdf import PdfReader
print("PDF:", len(PdfReader("definicion_de_tema.pdf").pages), "paginas")
PY
