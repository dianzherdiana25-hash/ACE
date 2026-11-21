"""Susun klaim terstruktur dari baris OCR dengan aturan yang didaftarkan.

Aturan menetapkan prefiks literal, tipe, dan wilayah dokumen yang
diizinkan. Klaim membutuhkan satu baris utuh yang terbaca dan
unik di wilayah tersebut. Klaim konflik, bentuk nilai salah, atau
bacaan tak lengkap tetap membawa penunjuk OCR untuk diperiksa.
"""
import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

from . import _raster, ocr_engine


MAX_LAYOUT_BYTES = 250_000
MAX_FIELDS = 128
INTEGER = re.compile(r"[-+]?[0-9]{1,18}")
DECIMAL = re.compile(r"([-+]?)([0-9]{1,18})([.,])([0-9]{1,6})")


def _token(value, label):
    if not isinstance(value, str) or not 1 <= len(value) <= 128 or not value.isprintable() or not value.strip():
        raise ValueError(f"{label} harus teks cetak.")
    return value


def _zone(raw):
    if raw is None:
        return None
    if not isinstance(raw, list) or len(raw) != 4 or any(type(value) is not int for value in raw):
        raise ValueError("Boks aturan perlu empat integer.")
    x0, y0, x1, y1 = raw
    if not (0 <= x0 < x1 <= _raster.MAX_PIXELS and 0 <= y0 < y1 <= _raster.MAX_PIXELS):
        raise ValueError("Boks aturan tidak sah.")
    return raw


def _layout(data):
    if not isinstance(data, bytes) or len(data) > MAX_LAYOUT_BYTES:
        raise ValueError("Layout melebihi batas byte.")
    raw = json.loads(data.decode("utf-8"), object_pairs_hook=ocr_engine._pairs)
    if not isinstance(raw, dict) or set(raw) != {"schema", "document_kind", "fields"} or raw["schema"] != "ace.perception-layout.v1":
        raise ValueError("Skema layout tidak dikenal.")
    name = _token(raw["document_kind"], "Jenis dokumen")
    fields = raw["fields"]
    if not isinstance(fields, list) or not 1 <= len(fields) <= MAX_FIELDS:
        raise ValueError("Jumlah aturan klaim di luar batas.")
    ids = set()
    result = []
    for row in fields:
        if not isinstance(row, dict) or set(row) != {"id", "prefix", "type", "box", "required"}:
            raise ValueError("Bentuk aturan klaim tidak dikenal.")
        key = _token(row["id"], "ID klaim")
        prefix = _token(row["prefix"], "Prefiks klaim")
        kind = row["type"]
        if key in ids or kind not in ("text", "integer", "decimal", "iso_date") or type(row["required"]) is not bool:
            raise ValueError("ID aturan ganda atau jenis/required tidak sah.")
        ids.add(key)
        result.append({"id": key, "prefix": prefix, "type": kind,
                       "box": _zone(row["box"]), "required": row["required"]})
    return name, result


def _value(kind, source):
    if not source:
        return None
    if kind == "text":
        return source
    if kind == "integer":
        return int(source) if INTEGER.fullmatch(source) else None
    if kind == "decimal":
        parsed = DECIMAL.fullmatch(source)
        if parsed is None:
            return None
        sign, whole, _, tail = parsed.groups()
        scaled = int(whole+tail)
        return {"unscaled": -scaled if sign == "-" else scaled, "scale": len(tail)}
    try:
        accepted = date.fromisoformat(source)
    except ValueError:
        return None
    return accepted.isoformat() if accepted.isoformat() == source else None


def _text_lines(ocr):
    lines = []
    for index, row in enumerate(ocr["lines"], 1):
        boxes = [glyph["box"] for glyph in row["glyphs"]]
        box = [min(cell[0] for cell in boxes), min(cell[1] for cell in boxes),
               max(cell[2] for cell in boxes), max(cell[3] for cell in boxes)]
        lines.append((row["text"], {"line": index, "box": box},
                      any(glyph["status"] != "agreed" for glyph in row["glyphs"])))
    return lines


def _inside(box, zone):
    return zone is None or zone[0] <= box[0] and zone[1] <= box[1] and box[2] <= zone[2] and box[3] <= zone[3]


def _near_match(text, prefix):
    segment = text[:len(prefix)]
    return len(segment) == len(prefix) and all(actual == target or actual == "\ufffd"
                                              for actual, target in zip(segment, prefix, strict=True))


def _claim(rule, lines, width, height):
    key = rule["id"]
    zone = rule["box"]
    if zone is not None and (zone[2] > width or zone[3] > height):
        raise ValueError(f"Wilayah klaim {key} di luar raster.")
    prefix = rule["prefix"]
    hits = []
    uncertain = []
    for text, source, partial in lines:
        if not _inside(source["box"], zone) or not _near_match(text, prefix):
            continue
        if partial:
            uncertain.append(source)
        else:
            value = _value(rule["type"], text[len(prefix):].strip())
            hits.append((value, source))
    value = None
    if len(hits)+len(uncertain) > 1:
        status = "ambiguous"
    elif uncertain:
        status = "unresolved_ocr"
    elif not hits:
        status = "missing"
    else:
        value = hits[0][0]
        status = "invalid_value" if value is None else "extracted"
    return {"id": key, "type": rule["type"], "required": rule["required"], "status": status,
            "value": value, "evidence": sorted([source for _, source in hits] + uncertain, key=lambda row: row["line"])}


def extract(image_data, font_data, layout_data, *, limit_bp=0, word_gap=4, light_ink=False):
    name, rules = _layout(layout_data)
    scanner = ocr_engine.recognize(image_data, font_data, limit_bp=limit_bp, word_gap=word_gap, light_ink=light_ink)
    lines = _text_lines(scanner)
    claims = [_claim(rule, lines, scanner["width"], scanner["height"]) for rule in rules]
    required_open = [row["id"] for row in claims if row["required"] and row["status"] != "extracted"]
    return {"schema": "ace.perception-document-claims.v1", "document_kind": name,
            "image_sha256": scanner["image_sha256"], "font_sha256": scanner["font_sha256"],
            "layout_sha256": sha256(layout_data).hexdigest(), "ocr_status": scanner["status"],
            "status": "incomplete" if required_open else "extracted", "required_open": required_open,
            "claims": claims}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("font", type=Path)
    parser.add_argument("layout", type=Path)
    parser.add_argument("--word-gap", type=int, default=4)
    parser.add_argument("--limit-bp", type=int, default=0)
    parser.add_argument("--light-ink", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = extract(_raster.read(args.image), _raster.read(args.font, ocr_engine.MAX_FONT_BYTES),
                         _raster.read(args.layout, MAX_LAYOUT_BYTES), limit_bp=args.limit_bp,
                         word_gap=args.word_gap, light_ink=args.light_ink)
        sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))+"\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] != "extracted")


if __name__ == "__main__":
    raise SystemExit(main())
