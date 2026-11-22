"""Audit struktur heading, label dan tabel pada Markdown atau DOCX secara baca-saja."""
import re

from ._artifacts import unpack
from ._contracts import ProductionError, anchor, cli, obj, schema, source_bytes
from ._docx import NS
from .artifact_qa import safe_xml


W = "{" + NS + "}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
ATX = re.compile(r"^ {0,3}(#{1,6})\s+(.+)$")
IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
LINK = re.compile(r"(?<!!)\[([^\]]*)\]\([^)]*\)")


def _headings(entries):
    findings = []
    previous = 0
    for item in entries:
        level, location, value = item
        if not value.strip():
            findings.append({"rule": "empty_heading", **location})
        if level > previous + 1:
            findings.append({"rule": "heading_level_skipped", **location, "previous_level": previous, "level": level})
        previous = level
    if not entries:
        findings.append({"rule": "missing_heading_structure"})
    return findings


def _markdown(raw):
    headings = []
    issues = []
    fence = None
    for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        signal = line.lstrip()[:3]
        if signal in ("```", "~~~"):
            fence = signal if fence is None else (None if signal == fence else fence)
            continue
        if fence:
            continue
        header = ATX.fullmatch(line)
        if header:
            headings.append((len(header[1]), {"line": number}, header[2].strip(" #")))
        for match in IMAGE.finditer(line):
            if not match[1].strip():
                issues.append({"rule": "missing_image_alt", "line": number, "column": match.start() + 1})
        for match in LINK.finditer(line):
            if match[1].strip().casefold() in ("", "click here", "here", "klik di sini", "di sini"):
                issues.append({"rule": "ambiguous_link_label", "line": number, "column": match.start() + 1})
    return headings, issues


def _docx(raw):
    packed = unpack(raw)
    content = safe_xml(packed["word/document.xml"])
    headings = []
    issues = []
    for index, item in enumerate(content.findall(f".//{W}p"), 1):
        style = item.find(f"{W}pPr/{W}pStyle")
        if style is not None:
            token = re.fullmatch(r"Heading([1-9])", style.get(W + "val", ""))
            if token:
                body = "".join(a.text or "" for a in item.findall(f".//{W}t"))
                headings.append((int(token[1]), {"paragraph": index}, body))
        for draw in item.findall(f".//{WP}docPr"):
            if not draw.get("descr", "").strip():
                issues.append({"rule": "missing_image_alt", "paragraph": index})
    for index, table in enumerate(content.findall(f".//{W}tbl"), 1):
        rows = table.findall(f"{W}tr")
        if not rows or rows[0].find(f"{W}trPr/{W}tblHeader") is None:
            issues.append({"rule": "table_header_not_marked", "table": index})
    return headings, issues


def inspect_accessibility(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.production.doc-a11y-plan.v1", ("file", "kind"))
    ref = obj(plan["file"], ("path", "sha256"))
    raw = source_bytes(root, ref["path"], ref["sha256"], 8000000)
    kind = plan["kind"]
    if kind not in ("markdown", "docx"):
        raise ProductionError("Audit struktur mendukung Markdown dan DOCX.")
    headings, issues = (_markdown if kind == "markdown" else _docx)(raw)
    issues.extend(_headings(headings))
    return {"schema": "ace.production.doc-a11y.v1", "plan_sha256": expected, "source": ref,
            "headings": [{"level": level, **location, "title": title} for level, location, title in headings],
            "findings": issues, "scope": "structural_subset", "status": "no_listed_findings" if not issues else "review"}


if __name__ == "__main__":
    raise SystemExit(cli(inspect_accessibility, __doc__, rooted=True))
