"""Keluarkan WordprocessingML asli agar judul dan tabel tetap semantik."""
from ._artifacts import e, package, xml


NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _paragraph(body, style=None):
    options = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f'<w:p>{options}<w:r><w:t xml:space="preserve">{e(body)}</w:t></w:r></w:p>'


def _table(table):
    cols = table["columns"]
    extent = 9000 // len(cols)
    grid = "".join(f'<w:gridCol w:w="{extent}"/>' for _ in cols)
    rows = []
    for index, cells in enumerate([cols, *table["rows"]]):
        stamp = "<w:trPr><w:tblHeader/></w:trPr>" if index == 0 else ""
        entries = "".join(f'<w:tc><w:tcPr><w:tcW w:w="{extent}" w:type="dxa"/></w:tcPr>{_paragraph(cell)}</w:tc>'
                          for cell in cells)
        rows.append(f"<w:tr>{stamp}{entries}</w:tr>")
    return ('<w:tbl><w:tblPr><w:tblW w:w="9000" w:type="dxa"/>'
            '<w:tblBorders><w:top w:val="single" w:sz="4"/><w:bottom w:val="single" w:sz="4"/>'
            '<w:insideH w:val="single" w:sz="4"/></w:tblBorders></w:tblPr>'
            f"<w:tblGrid>{grid}</w:tblGrid>{''.join(rows)}</w:tbl>")


def _styles():
    rows = ['<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
            '<w:rPr><w:sz w:val="22"/></w:rPr></w:style>',
            '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>'
            '<w:rPr><w:b/><w:sz w:val="44"/></w:rPr></w:style>']
    for level in range(1, 6):
        height = 34 - level * 2
        rows.append(f'<w:style w:type="paragraph" w:styleId="Heading{level}"><w:name w:val="heading {level}"/>'
                    f'<w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:pPr><w:keepNext/>'
                    f'<w:outlineLvl w:val="{level - 1}"/></w:pPr><w:rPr><w:b/><w:sz w:val="{height}"/></w:rPr></w:style>')
    return xml(f'<w:styles xmlns:w="{NS}">{"".join(rows)}</w:styles>')


def build_docx(title, blocks):
    sections = [_paragraph(title, "Title")]
    for block in blocks:
        kind = block["kind"]
        if kind == "heading":
            sections.append(_paragraph(block["body"], f"Heading{block['level']}"))
        elif kind == "paragraph":
            sections.append(_paragraph(block["body"]))
        elif kind == "table":
            sections.append(_table(block))
        elif kind == "bookmark":
            index, name = block["index"], block["name"]
            link = (f'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:bookmarkStart w:id="{index}" w:name="{name}"/>'
                    f'<w:r><w:t>{e(block["body"])}</w:t></w:r><w:bookmarkEnd w:id="{index}"/></w:p>')
            sections.append(link)
        elif kind == "toc":
            for index, entry in enumerate(block["entries"], 1):
                headline = e(f'{index}. {entry["title"]}') if entry["level"] == 1 else e("    " + entry["title"])
                sections.append(f'<w:p><w:hyperlink w:anchor="{entry["name"]}"><w:r><w:rPr><w:color w:val="246478"/>'
                                f'<w:u w:val="single"/></w:rPr><w:t xml:space="preserve">{headline}</w:t></w:r></w:hyperlink></w:p>')
        else:
            sections.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
    body = (f'<w:document xmlns:w="{NS}"><w:body>{"".join(sections)}'
            '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1150" w:right="1150" '
            'w:bottom="1150" w:left="1150" w:header="600" w:footer="600" w:gutter="0"/>'
            '</w:sectPr></w:body></w:document>')
    parts = {
        "[Content_Types].xml": xml(f'<Types xmlns="{TYPES}">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            '</Types>'),
        "_rels/.rels": xml(f'<Relationships xmlns="{REL}"><Relationship Id="rId1" Type="{OFFICE}/officeDocument" Target="word/document.xml"/></Relationships>'),
        "word/_rels/document.xml.rels": xml(f'<Relationships xmlns="{REL}"><Relationship Id="rId1" Type="{OFFICE}/styles" Target="styles.xml"/></Relationships>'),
        "word/document.xml": xml(body),
        "word/styles.xml": _styles(),
    }
    return package(parts)
