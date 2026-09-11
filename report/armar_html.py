"""Markdown -> HTML con la cabecera y la hoja de estilo, para pasarlo a PDF."""
import pathlib, re, subprocess

md = pathlib.Path("definicion_de_tema.md").read_text()
titulo = re.search(r'title: "(.+?)"', md).group(1)
cuerpo = md.split("---\n", 2)[2]
meta = "BME423, Procesamiento de imágenes médicas. Definición de tema del mini-proyecto. Segundo semestre 2026.\n"
cuerpo = cuerpo.replace(meta, "")
pathlib.Path("_c.md").write_text(cuerpo)
subprocess.run(["pandoc", "_c.md", "-f", "markdown", "-t", "html5", "-o", "_c.html"], check=True)
html = ('<!doctype html><html><head><meta charset="utf-8">'
        '<link rel="stylesheet" href="estilo.css"></head><body>'
        f'<p class="meta">{meta.strip()}</p><h1>{titulo}</h1>'
        + pathlib.Path("_c.html").read_text() + "</body></html>")
pathlib.Path("_doc.html").write_text(html)
pathlib.Path("_c.md").unlink(); pathlib.Path("_c.html").unlink()
print("html listo")
