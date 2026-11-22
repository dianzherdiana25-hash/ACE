"""Susun EPUB yang dapat dibaca lokal dari naskah bab dengan TOC dan metadata."""
import argparse
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import sys
from xml.etree import ElementTree as ET
from zipfile import ZIP_STORED, ZipFile

from ._artifacts import a, e, package, unpack, xml
from ._contracts import (ProductionError, anchor, canonical, day, decode, identifier,
                         items, obj, read, schema, source_bytes, text)
from .artifact_qa import safe_xml


BOOK = "application/epub+zip"
XHTML = "http://www.w3.org/1999/xhtml"
OPF = "http://www.idpf.org/2007/opf"
CTA = "urn:oasis:names:tc:opendocument:xmlns:container"
LANGS = ("id", "en")


def _page(title, body, language):
    return xml(f'<html xmlns="{XHTML}" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang={a(language)}>'
               f'<head><title>{e(title)}</title><link rel="stylesheet" href="style.css" type="text/css"/></head>'
               f'<body>{body}</body></html>')


def _body(raw):
    paragraphs = []
    for source_line, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = text(line.strip(), "Baris naskah", 2000)
        if value.startswith("## "):
            paragraphs.append(f'<h2 id="l{source_line}">{e(value[3:])}</h2>')
        else:
            paragraphs.append(f'<p id="l{source_line}">{e(value)}</p>')
    if not paragraphs:
        raise ProductionError("Bab harus berisi paragraf.")
    return "".join(paragraphs)


def build_epub(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.production.epub-plan.v1", ("id", "title", "creator", "language", "revision_date", "chapters"))
    identity = identifier(plan["id"], "ID publikasi")
    title = text(plan["title"], "Judul buku", 160)
    creator = text(plan["creator"], "Atribusi buku", 140)
    lang = plan["language"]
    if lang not in LANGS:
        raise ProductionError("Bahasa EPUB dibatasi pada id atau en.")
    revised = day(plan["revision_date"]).isoformat()
    toc = []
    manifest = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                '<item id="style" href="style.css" media-type="text/css"/>']
    spine = []
    chapters = []
    seen = set()
    total = 0
    parts = {"mimetype": BOOK.encode(), "META-INF/container.xml": xml(f'<container xmlns="{CTA}" version="1.0">'
             '<rootfiles><rootfile full-path="EPUB/package.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'),
             "EPUB/style.css": b"body{font-family:serif;line-height:1.55}h1,h2{line-height:1.2}p{margin-block:1em}\n"}
    for row in items(plan["chapters"], 100, 1):
        obj(row, ("id", "title", "path", "sha256"))
        key = identifier(row["id"], "ID bab")
        label = text(row["title"], "Judul bab", 120)
        if key in seen or key == "nav":
            raise ProductionError("ID bab EPUB ganda atau dicadangkan.")
        seen.add(key)
        raw = source_bytes(root, row["path"], row["sha256"], 450000)
        total += len(raw)
        if total > 8_000_000:
            raise ProductionError("Jumlah naskah EPUB melampaui batas.")
        filename = key + ".xhtml"
        parts["EPUB/" + filename] = _page(label, f"<h1>{e(label)}</h1>" + _body(raw), lang)
        manifest.append(f'<item id={a("ch_" + key)} href={a(filename)} media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref={a("ch_" + key)}/>')
        toc.append(f'<li><a href={a(filename)}>{e(label)}</a></li>')
        chapters.append({"id": key, "href": filename, "source_sha256": row["sha256"], "source_path": row["path"]})
    toc_title = "Daftar Isi" if lang == "id" else "Contents"
    parts["EPUB/nav.xhtml"] = _page(toc_title, f'<nav epub:type="toc"><h1>{toc_title}</h1><ol>{"".join(toc)}</ol></nav>', lang)
    parts["EPUB/package.opf"] = xml(f'<package xmlns="{OPF}" unique-identifier="book_id" version="3.0">'
       '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
       f'<dc:identifier id="book_id">urn:ace:{e(identity)}</dc:identifier><dc:title>{e(title)}</dc:title>'
       f'<dc:creator>{e(creator)}</dc:creator><dc:language>{e(lang)}</dc:language>'
       f'<meta property="dcterms:modified">{revised}T00:00:00Z</meta></metadata>'
       f'<manifest>{"".join(manifest)}</manifest><spine>{"".join(spine)}</spine></package>')
    product = package(parts, first="mimetype")
    return product, {"schema": "ace.production.epub-receipt.v1", "plan_sha256": expected, "title": title,
                     "epub_sha256": sha256(product).hexdigest(), "chapters": chapters,
                     "verified_chapters": verify_epub(product)}


def verify_epub(data):
    with ZipFile(BytesIO(data)) as archive:
        first = archive.infolist()[0]
        if first.filename != "mimetype" or first.compress_type != ZIP_STORED or archive.read(first) != BOOK.encode():
            raise ProductionError("mimetype EPUB perlu member pertama tanpa kompresi.")
    parts = unpack(data)
    container = safe_xml(parts["META-INF/container.xml"])
    entry = container.find(f".//{{{CTA}}}rootfile")
    if entry is None or entry.get("full-path") != "EPUB/package.opf":
        raise ProductionError("Container EPUB tidak menunjuk package.")
    root = safe_xml(parts["EPUB/package.opf"])
    refs = {item.get("id"): item.get("href") for item in root.findall(f".//{{{OPF}}}item")}
    spine = [row.get("idref") for row in root.findall(f".//{{{OPF}}}itemref")]
    nav = safe_xml(parts["EPUB/nav.xhtml"])
    tocs = [row.get("href") for row in nav.findall(f".//{{{XHTML}}}a")]
    if not spine or [refs[key] for key in spine] != tocs:
        raise ProductionError("Daftar isi dan spine EPUB tidak konsisten.")
    for name in tocs:
        page = safe_xml(parts["EPUB/" + name])
        if page.findtext(f".//{{{XHTML}}}h1") is None:
            raise ProductionError("Halaman bab kehilangan heading.")
    return len(spine)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        product, receipt = build_epub(decode(read(args.plan)), args.expect_sha256, args.root)
        with args.output.open("xb") as stream:
            stream.write(product)
        sys.stdout.buffer.write(canonical(receipt) + b"\n")
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
