"""Gabungkan DOCX subset produksi dengan daftar isi klik dan jejak sumber tiap bagian."""
import argparse
from hashlib import sha256
from pathlib import Path
import re
import sys
from xml.etree import ElementTree as ET

from ._artifacts import unpack
from ._contracts import (ProductionError, anchor, canonical, decode, identifier, items,
                         obj, read, schema, source_bytes, text)
from ._docx import NS, build_docx
from .artifact_qa import inspect, safe_xml


W = "{" + NS + "}"
HEADING = re.compile(r"Heading([1-5])")


def _paragraph(node):
    found = node.find(f"{W}pPr/{W}pStyle")
    style = "" if found is None else found.get(W + "val", "")
    for child in node.iter():
        if child.tag.rsplit("}", 1)[-1] in {"drawing", "pict", "hyperlink", "instrText", "object", "fldSimple"}:
            raise ProductionError("Paragraf DOCX mengandung objek yang tidak bisa ditransfer.")
    body = "".join(node.itertext()) if not node.findall(f".//{W}t") else "".join(part.text or "" for part in node.findall(f".//{W}t"))
    if node.findall(f".//{W}br") and body.strip():
        raise ProductionError("Paragraf dengan campuran break dan isi perlu diratakan dahulu.")
    if any(item.get(W + "type") == "page" for item in node.findall(f".//{W}br")):
        return {"kind": "break"}
    if not body.strip():
        return None
    body = text(body, "Paragraf DOCX", 1600)
    found = HEADING.fullmatch(style)
    if found:
        return {"kind": "heading", "body": body, "level": min(5, int(found[1]) + 1)}
    return {"kind": "paragraph", "body": body, "input_style": style or "Normal"}


def _table(node):
    if node.findall(f".//{W}tbl") or node.findall(f".//{W}gridSpan") or node.findall(f".//{W}vMerge"):
        raise ProductionError("Tabel bertingkat atau sel gabung belum didukung.")
    rows = []
    for row in node.findall(f"{W}tr"):
        values = []
        for cell in row.findall(f"{W}tc"):
            if any(child.tag not in (W + "p", W + "tcPr") for child in cell):
                raise ProductionError("Tabel memiliki jenis isi sel yang tidak didukung.")
            texts = [_paragraph(para) for para in cell.findall(f"{W}p")]
            if any(value is not None and value["kind"] != "paragraph" for value in texts):
                raise ProductionError("Sel tabel memerlukan paragraf teks biasa.")
            values.append(" / ".join(value["body"] for value in texts if value))
        rows.append(values)
    if not rows or not rows[0] or any(len(row) != len(rows[0]) for row in rows):
        raise ProductionError("Tabel DOCX sumber bukan matriks utuh.")
    return {"kind": "table", "columns": rows[0], "rows": rows[1:]}


def merge_documents(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.production.merge-plan.v1", ("title", "sources"))
    title = text(plan["title"], "Judul gabungan", 160)
    seen = set()
    headings = []
    sections = []
    source_rows = []
    for index, ref in enumerate(items(plan["sources"], 30, 2), 1):
        obj(ref, ("id", "label", "path", "sha256"))
        name = identifier(ref["id"], "Sumber penggabungan")
        if name in seen:
            raise ProductionError("Sumber gabungan ber-ID sama.")
        seen.add(name)
        label = text(ref["label"], "Judul sumber", 150)
        raw = source_bytes(root, ref["path"], ref["sha256"], 8_000_000)
        if inspect(raw, "docx")["active_features"]:
            raise ProductionError("DOCX sumber mengandung hubungan eksternal atau macro.")
        parts = unpack(raw)
        content = safe_xml(parts["word/document.xml"]).find(f"{W}body")
        if content is None or any(child.tag not in (W + "p", W + "tbl", W + "sectPr") for child in content):
            raise ProductionError("DOCX sumber memiliki struktur selain paragraf dan tabel.")
        marker = f"section_{index}"
        headings.append({"name": marker, "title": label, "level": 1})
        sections.extend([{"kind": "break"}, {"kind": "bookmark", "index": index, "name": marker, "body": label}])
        count = 0
        for child in content:
            if child.tag == W + "sectPr":
                continue
            block = _paragraph(child) if child.tag == W + "p" else _table(child)
            if block is not None:
                sections.append(block)
                count += 1
        if not count:
            raise ProductionError("Dokumen sumber tidak memiliki bagian isi.")
        source_rows.append({"id": name, "path": ref["path"], "sha256": ref["sha256"], "bookmark": marker, "blocks": count})
    blocks = [{"kind": "heading", "level": 1, "body": "Daftar Isi"}, {"kind": "toc", "entries": headings}, *sections]
    output = build_docx(title, blocks)
    return output, {"schema": "ace.production.merged-document.v1", "plan_sha256": expected,
                    "output_sha256": sha256(output).hexdigest(), "sources": source_rows, "toc": headings,
                    "transfer_scope": "native_paragraphs_tables_and_section_links"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        data, report = merge_documents(decode(read(args.plan)), args.expect_sha256, args.root)
        with args.output.open("xb") as stream:
            stream.write(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
