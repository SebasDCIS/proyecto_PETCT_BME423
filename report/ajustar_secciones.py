"""Post-proceso del .docx que genera pandoc: fija el tamaño de página y los márgenes.

Pandoc deja el <w:sectPr> del cuerpo vacío, así que el documento sale con la página por
defecto de Word en vez de la A4 con márgenes de 1,8 cm que hace falta para entrar en dos
páginas. Acá se escribe ese sectPr y se repite en un corte de sección continuo.

Nota para quien lo toque: en OOXML un <w:sectPr> incrustado en un párrafo describe la sección
que TERMINA en ese párrafo, y si no se declara <w:type w:val="continuous"/> el valor por
defecto es nextPage, con lo que la sección siguiente arranca en una página nueva. Eso pasó en
el primer intento y dejó media página en blanco.
"""
import pathlib

PG = ('<w:pgSz w:w="11906" w:h="16838"/>'
      '<w:pgMar w:top="1000" w:right="1020" w:bottom="1000" w:left="1020" '
      'w:header="600" w:footer="600" w:gutter="0"/>')

d = pathlib.Path("_out/word/document.xml")
x = d.read_text()

final = ('<w:sectPr><w:type w:val="continuous"/>' + PG
         + '<w:cols w:space="708"/></w:sectPr>')
assert '<w:sectPr />' in x, "pandoc no dejó el sectPr vacío que esperaba"
x = x.replace('<w:sectPr />', final)

i = x.index("Artículos relacionados")
ini = max(x.rfind("<w:p ", 0, i), x.rfind("<w:p>", 0, i))
fin = x.index("</w:p>", i) + len("</w:p>")
par = x[ini:fin]
corte = ('<w:sectPr><w:type w:val="continuous"/>' + PG
         + '<w:cols w:space="708"/></w:sectPr>')
if "<w:pPr>" in par:
    par = par.replace("</w:pPr>", corte + "</w:pPr>", 1)
else:
    k = par.index(">") + 1
    par = par[:k] + "<w:pPr>" + corte + "</w:pPr>" + par[k:]
x = x[:ini] + par + x[fin:]

d.write_text(x)

import xml.dom.minidom
xml.dom.minidom.parseString(x)      # falla acá antes que en Word
print("página y márgenes fijados, XML válido")
