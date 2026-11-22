"""Gerbang artefak berdasarkan hash, format terbaca dan kontrak struktur minimum."""
from hashlib import sha256
from io import BytesIO
from pathlib import PurePosixPath
from xml.etree import ElementTree as ET

from ._artifacts import unpack
from ._contracts import ProductionError, anchor, cli, integer, items, obj, schema, source_bytes
from ._docx import NS as WORD
from .sheet_builder import NS as SHEET


PPT = "http://schemas.openxmlformats.org/presentationml/2006/main"
SVG = "http://www.w3.org/2000/svg"
FORMATS = ("docx", "pdf", "xlsx", "pptx", "svg")


def safe_xml(raw):
    lower = raw.lower()
    if b"<!doctype" in lower or b"<!entity" in lower:
        raise ProductionError("XML subset tidak menerima DTD atau entitas deklaratif.")
    return ET.fromstring(raw)


def _check_links(parts):
    blocked = []
    for name, payload in parts.items():
        if name.endswith(".rels"):
            for item in safe_xml(payload):
                target = item.get("Target", "")
                if item.get("TargetMode") == "External" or target.startswith(("//", "/")) or ":" in target:
                    blocked.append(name)
    return sorted(set(blocked))


def _pdf(data):
    if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-160:]:
        raise ProductionError("Header atau akhir PDF rusak.")
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as error:
        raise ProductionError("Backend verifikasi PDF pypdf diperlukan.") from error
    try:
        proof = PdfReader(BytesIO(data), strict=True)
        if proof.is_encrypted:
            raise ProductionError("PDF terenkripsi tidak dapat diperiksa.")
        root = proof.trailer["/Root"]
        active = sorted(str(flag) for flag in ("/OpenAction", "/AA", "/JavaScript") if flag in root)
        names = root.get("/Names")
        if names and ("/JavaScript" in names.get_object() or "/EmbeddedFiles" in names.get_object()):
            active.append("active_or_embedded_names")
        return {"pages": len(proof.pages), "active_features": active}
    except (PdfReadError, KeyError, TypeError) as error:
        raise ProductionError("Struktur PDF tidak sah.") from error


def _office(data, kind):
    parts = unpack(data)
    safe_xml(parts["[Content_Types].xml"])
    safe_xml(parts["_rels/.rels"])
    links = _check_links(parts)
    if kind == "docx":
        root = safe_xml(parts["word/document.xml"])
        if root.tag != f"{{{WORD}}}document":
            raise ProductionError("Bagian DOCX bukan dokumen WordprocessingML.")
        metrics = {"paragraphs": len(root.findall(f".//{{{WORD}}}p")), "tables": len(root.findall(f".//{{{WORD}}}tbl"))}
    elif kind == "xlsx":
        root = safe_xml(parts["xl/workbook.xml"])
        if root.tag != f"{{{SHEET}}}workbook":
            raise ProductionError("Bagian XLSX bukan workbook.")
        sheet_count = len(root.findall(f".//{{{SHEET}}}sheet"))
        named = [name for name in parts if PurePosixPath(name).parent.as_posix() == "xl/worksheets" and name.endswith(".xml")]
        if len(named) != sheet_count:
            raise ProductionError("Daftar lembar XLSX berbeda dari bagian fisik.")
        formulas = sum(len(safe_xml(parts[name]).findall(f".//{{{SHEET}}}f")) for name in named)
        metrics = {"sheets": sheet_count, "formulas": formulas}
    else:
        root = safe_xml(parts["ppt/presentation.xml"])
        if root.tag != f"{{{PPT}}}presentation":
            raise ProductionError("Bagian PPTX bukan presentasi.")
        slide_count = len(root.findall(f".//{{{PPT}}}sldId"))
        named = [name for name in parts if PurePosixPath(name).parent.as_posix() == "ppt/slides" and name.endswith(".xml")]
        if len(named) != slide_count or any(safe_xml(parts[name]).tag != f"{{{PPT}}}sld" for name in named):
            raise ProductionError("Deklarasi slide tidak cocok dengan bagian fisik.")
        metrics = {"slides": slide_count}
    active = links + [name for name in parts if PurePosixPath(name).name.lower() in ("vbaproject.bin", "vbadata.xml")]
    return {**metrics, "active_features": sorted(active)}


def _svg(data):
    root = safe_xml(data)
    if root.tag != f"{{{SVG}}}svg":
        raise ProductionError("Konten bukan SVG.")
    active = [child.tag for child in root.iter() if child.tag.rsplit("}", 1)[-1] in {"script", "foreignObject", "iframe"}
              or any(key.rsplit("}", 1)[-1].lower().startswith("on") or key.rsplit("}", 1)[-1] == "href"
                     for key in child.attrib)]
    return {"accessible_title": int(bool(root.findtext(f"{{{SVG}}}title"))), "active_features": active}


def inspect(data, kind):
    if kind == "pdf":
        return _pdf(data)
    if kind == "svg":
        return _svg(data)
    if kind in ("docx", "xlsx", "pptx"):
        return _office(data, kind)
    raise ProductionError("Format QA belum didukung.")


def audit(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.production.artifact-qa-plan.v1", ("artifacts",))
    results = []
    unique = set()
    for row in items(plan["artifacts"], 100, 1):
        obj(row, ("path", "sha256", "format", "minimum"))
        name = row["path"]
        kind = row["format"]
        if kind not in FORMATS or name in unique or not isinstance(name, str) or not name.endswith("." + kind):
            raise ProductionError("Path atau format artefak salah atau ganda.")
        unique.add(name)
        if not isinstance(row["minimum"], dict):
            raise ProductionError("Minimum struktur harus objek.")
        checks = []
        fault = None
        raw = None
        try:
            raw = source_bytes(root, name, row["sha256"], 24_000_000)
            metrics = inspect(raw, kind)
        except (ProductionError, OSError, ET.ParseError, KeyError, IndexError) as error:
            metrics = None
            fault = str(error)[:250]
        if metrics is not None:
            for rule, threshold in sorted(row["minimum"].items()):
                wanted = integer(threshold, "Ambang struktur", 1, 100000)
                checks.append({"id": rule, "actual": metrics.get(rule), "minimum": wanted,
                               "pass": type(metrics.get(rule)) is int and metrics[rule] >= wanted})
            checks.append({"id": "no_active_features", "pass": not metrics["active_features"]})
        results.append({"path": name, "sha256": sha256(raw).hexdigest() if raw else None,
                        "format": kind, "metrics": metrics, "error": fault,
                        "checks": checks, "status": "pass" if checks and all(item["pass"] for item in checks) else "hold"})
    passed = sum(row["status"] == "pass" for row in results)
    return {"schema": "ace.production.artifact-qa.v1", "plan_sha256": expected, "formats": results,
            "pass_count": passed, "total": len(results), "status": "pass" if passed == len(results) else "hold"}


if __name__ == "__main__":
    raise SystemExit(cli(audit, __doc__, rooted=True))
