"""Halaman PDF sederhana dengan xref, encoding dan paginasi yang dapat dibaca balik."""
from textwrap import wrap

from ._contracts import ProductionError


def _literal(raw):
    try:
        encoded = raw.encode("cp1252")
    except UnicodeEncodeError as error:
        raise ProductionError("PDF font dasar hanya mencakup WinAnsi. Gunakan DOCX untuk aksara lain.") from error
    return b"(" + b"".join((f"\\{value:03o}".encode() if value < 32 or value >= 127 or value in (40, 41, 92)
                            else bytes((value,))) for value in encoded) + b")"


def _render(title, blocks):
    pages = [[]]
    top = 778

    def newline(size, after, value, bold=False):
        nonlocal top
        if top - size < 54:
            pages.append([])
            top = 778
        left = 53
        pages[-1].append((left, top, size, bold, value))
        top -= size + after

    def paragraph(value, size, margin, bold=False):
        max_chars = int(472 / (size * 1.05))
        for line in wrap(value, max_chars, break_long_words=True, break_on_hyphens=True) or [""]:
            newline(size, 5, line, bold)
        top_adjust(margin)

    def top_adjust(amount):
        nonlocal top
        top -= amount

    paragraph(title, 23, 11, True)
    for block in blocks:
        kind = block["kind"]
        if kind == "break":
            if pages[-1]:
                pages.append([])
                top = 778
        elif kind == "heading":
            paragraph(block["body"], 17 - block["level"], 7, True)
        elif kind == "paragraph":
            paragraph(block["body"], 11, 9)
        else:
            paragraph(" | ".join(block["columns"]), 10, 1, True)
            for row in block["rows"]:
                paragraph(" | ".join(row), 10, 1)
            top_adjust(9)
    return [page for page in pages if page]


def build_pdf(title, blocks):
    pages = _render(title, blocks)
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", None,
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"]
    ids = []
    for page in pages:
        idx = len(objects) + 1
        ids.append(f"{idx} 0 R")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources "
                       f"<< /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {idx + 1} 0 R >>".encode())
        contents = []
        for x, y, size, bold, value in page:
            contents.append(f"BT /F{2 if bold else 1} {size} Tf 1 0 0 1 {x} {y} Tm ".encode() + _literal(value) + b" Tj ET")
        stream = b"\n".join(contents) + b"\n"
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"endstream")
    objects[1] = f"<< /Type /Pages /Count {len(pages)} /Kids [{' '.join(ids)}] >>".encode()
    result = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, body in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(f"{index} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(result)
    result.extend(f"xref\n0 {len(offsets)}\n".encode() + b"0000000000 65535 f \n")
    for pos in offsets[1:]:
        result.extend(f"{pos:010} 00000 n \n".encode())
    result.extend(f"trailer\n<< /Root 1 0 R /Size {len(offsets)} >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(result), len(pages)
