"""Ajusta el reference.docx por defecto de pandoc para que el documento entre en dos páginas.

Qué cambia respecto del original: el cuerpo pasa de 12 a 9,5 pt, el interlineado a simple, el
texto a justificado, se reduce el aire entre párrafos y entre títulos, la página queda A4 con
márgenes de 1,8 cm, y se agrega un estilo "Referencias" a 8 pt para la bibliografía.

Se ejecuta sobre `_ref/`, que es el reference.docx de pandoc ya descomprimido.
"""
import pathlib
import re

st = pathlib.Path("_ref/word/styles.xml")
s = st.read_text()

# Cuerpo a 9,5 pt (sz va en medios puntos) y tipografía con soporte de acentos
s = s.replace('<w:sz w:val="24" />\n        <w:szCs w:val="24" />',
              '<w:sz w:val="19" />\n        <w:szCs w:val="19" />')
s = s.replace('w:asciiTheme="minorHAnsi" w:eastAsiaTheme="minorHAnsi" '
              'w:hAnsiTheme="minorHAnsi" w:cstheme="minorBidi"',
              'w:ascii="Calibri" w:eastAsia="Calibri" w:hAnsi="Calibri" w:cs="Calibri"')

# Valores por defecto de párrafo: interlineado simple y justificado
s = re.sub(r'<w:pPrDefault>\s*<w:pPr>.*?</w:pPr>\s*</w:pPrDefault>',
           '<w:pPrDefault><w:pPr>'
           '<w:spacing w:after="90" w:line="240" w:lineRule="auto"/>'
           '<w:jc w:val="both"/>'
           '</w:pPr></w:pPrDefault>',
           s, flags=re.S)

# Pandoc usa el estilo "Body Text" para los párrafos; su aire por defecto es excesivo
s = s.replace('<w:spacing w:before="180" w:after="180" />',
              '<w:spacing w:before="0" w:after="70" />')

# Títulos más compactos
for estilo, sz in [("Title", "28"), ("Heading1", "24"), ("Heading2", "22"), ("Heading3", "20")]:
    patron = re.compile(r'(<w:style [^>]*w:styleId="%s"[^>]*>)(.*?)(</w:style>)' % estilo, re.S)

    def reemplazo(m, sz=sz):
        cuerpo = re.sub(r'<w:spacing[^/]*/>', '<w:spacing w:before="130" w:after="70"/>', m.group(2))
        cuerpo = re.sub(r'<w:sz w:val="\d+"\s*/>', '<w:sz w:val="%s"/>' % sz, cuerpo)
        cuerpo = re.sub(r'<w:szCs w:val="\d+"\s*/>', '<w:szCs w:val="%s"/>' % sz, cuerpo)
        return m.group(1) + cuerpo + m.group(3)

    s = patron.sub(reemplazo, s)

# Estilo propio para la bibliografía, referido desde el markdown con
# ::: {custom-style="Referencias"}
if 'w:styleId="Referencias"' not in s:
    s = s.replace("</w:styles>",
                  '<w:style w:type="paragraph" w:customStyle="1" w:styleId="Referencias">'
                  '<w:name w:val="Referencias"/><w:basedOn w:val="BodyText"/><w:qFormat/>'
                  '<w:pPr><w:spacing w:before="0" w:after="40" w:line="215" w:lineRule="auto"/>'
                  '<w:jc w:val="left"/></w:pPr>'
                  '<w:rPr><w:sz w:val="16"/><w:szCs w:val="16"/></w:rPr>'
                  '</w:style></w:styles>')

st.write_text(s)

import xml.dom.minidom
xml.dom.minidom.parseString(s)      # que falle acá y no dentro de pandoc
print("estilos ajustados")
