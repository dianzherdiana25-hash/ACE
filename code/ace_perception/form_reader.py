"""Baca label dan nilai formulir sebagai dua wilayah bukti terpisah.

Roster memberi boks, label yang diharapkan, dan jenis nilai. Hasil
hanya diterbitkan saat label OCR cocok dan nilai sah. Checkbox
memerlukan outline yang terukur sebelum klasifikasi tanda interior.
Wilayah meragukan tetap tampil dengan alasan serta boks sumber.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import unicodedata

from . import _raster, ocr_engine
from .audio_pipeline import _canonical, _integer
from .document_extractor import _token, _zone
from .screen_understanding import _border


MAX_FIELDS = 128
MAX_LAYOUT_BYTES = 250_000
MAX_CELLS = 400_000
DIGITS = re.compile(r"[0-9]{1,64}")


def _checked_box(raw, image):
    box = _zone(raw)
    if box is None or box[2] > image.width or box[3] > image.height:
        raise ValueError("Wilayah formulir di luar raster.")
    return box


def _overlap(left, right):
    return left[0] < right[2] and right[0] < left[2] and left[1] < right[3] and right[1] < left[3]


def _layout(data, image):
    if not isinstance(data, bytes) or len(data) > MAX_LAYOUT_BYTES:
        raise ValueError("Layout formulir terlalu besar.")
    raw = json.loads(data.decode("utf-8"), object_pairs_hook=ocr_engine._pairs)
    fields = {"schema", "form_ref", "light_ink", "word_gap", "border_bp", "unchecked_max_bp", "checked_min_bp", "fields"}
    if not isinstance(raw, dict) or set(raw) != fields or raw["schema"] != "ace.perception-form-layout.v1":
        raise ValueError("Skema formulir tidak sah.")
    form_ref = _token(raw["form_ref"], "Rujukan formulir")
    gap = _integer(raw["word_gap"], 1, 4096, "Jarak kata")
    outline = _integer(raw["border_bp"], 1, 10_000, "Ambang garis checkbox")
    low = _integer(raw["unchecked_max_bp"], 0, 9999, "Batas tidak dicentang")
    high = _integer(raw["checked_min_bp"], low+1, 10_000, "Batas dicentang")
    light = raw["light_ink"]
    if type(light) is not bool or not isinstance(raw["fields"], list) or not 1 <= len(raw["fields"]) <= MAX_FIELDS:
        raise ValueError("Polaritas atau roster bidang formulir tidak sah.")
    selected = []
    ids = set()
    tested = []
    total = 0
    for row in raw["fields"]:
        if not isinstance(row, dict) or set(row) != {"id", "expected_label", "label_box", "value_box", "type", "required"}:
            raise ValueError("Bentuk bidang formulir tidak sah.")
        key = _token(row["id"], "ID bidang")
        label = _token(row["expected_label"], "Label terdaftar")
        label_box, value_box = (_checked_box(row[item], image) for item in ("label_box", "value_box"))
        kind = row["type"]
        if key in ids or kind not in ("text", "digits", "checkbox") or type(row["required"]) is not bool:
            raise ValueError("ID bidang ganda atau tipe bidang/required tidak sah.")
        if _overlap(label_box, value_box) or any(_overlap(box, other) for box in (label_box, value_box) for other in tested):
            raise ValueError("Wilayah label atau nilai beririsan.")
        tested.extend((label_box, value_box))
        total += sum((box[2]-box[0])*(box[3]-box[1]) for box in (label_box, value_box))
        ids.add(key)
        selected.append((key, label, label_box, value_box, kind, row["required"]))
    if total > MAX_CELLS:
        raise ValueError("Jumlah area formulir melampaui batas.")
    return form_ref, gap, outline, low, high, light, selected


def _normalized(value):
    return unicodedata.normalize("NFC", " ".join(value.casefold().split()))


def _checkbox(image, box, light, level, border_limit, low, high):
    width, height = box[2]-box[0], box[3]-box[1]
    if min(width, height) < 3:
        raise ValueError("Checkbox memerlukan interior minimal satu piksel.")
    values = image.rectangle(box)
    mask = [(item > level) if light else (item <= level) for item in values] if level is not None else [False]*len(values)
    border, perimeter = _border(mask, width, (0, 0, width, height))
    marked = sum(mask[y*width+x] for y in range(1, height-1) for x in range(1, width-1))
    interior = (width-2)*(height-2)
    if border*10000 < border_limit*perimeter:
        status, value = "missing_outline", None
    elif marked*10000 <= low*interior:
        status, value = "read", False
    elif marked*10000 >= high*interior:
        status, value = "read", True
    else:
        status, value = "ambiguous_mark", None
    return {"status": status, "value": value, "border_pixels": border, "perimeter_pixels": perimeter,
            "marked_pixels": marked, "interior_pixels": interior}


def extract(image_data, font_data, layout_data):
    image = _raster.decode(image_data)
    font = ocr_engine.Font.decode(font_data)
    source, gap, outline, low, high, light, fields = _layout(layout_data, image)
    threshold = ocr_engine._otsu(image.pixels, image.maximum)
    result = []
    for key, expected, label_box, value_box, kind, required in fields:
        label = ocr_engine.read_area(image, label_box, font_data, light_ink=light, word_gap=gap)
        label_status = label["status"]
        if label_status == "read" and _normalized(expected) != _normalized(label["text"]):
            label_status = "label_mismatch"
        if kind == "checkbox":
            value = _checkbox(image, value_box, light, threshold, outline, low, high)
        else:
            read = ocr_engine.read_area(image, value_box, font_data, light_ink=light, word_gap=gap)
            value = {**read, "value": read["text"]}
            if kind == "digits" and read["status"] == "read" and not DIGITS.fullmatch(read["text"]):
                value.update(status="invalid_digits", value=None)
        status = "paired" if label_status == "read" and value["status"] == "read" else "unresolved"
        result.append({"id": key, "type": kind, "required": required, "status": status,
                       "expected_label": expected, "label": {**label, "status": label_status, "box": label_box},
                       "value": value["value"] if status == "paired" else None,
                       "value_evidence": {**value, "box": value_box}})
    pending = [row["id"] for row in result if row["required"] and row["status"] != "paired"]
    return {"schema": "ace.perception-form-pairs.v1", "form_ref": source,
            "image_sha256": sha256(image_data).hexdigest(), "font_sha256": font.checksum,
            "layout_sha256": sha256(layout_data).hexdigest(), "fields": result,
            "required_open": pending, "status": "incomplete" if pending else "extracted"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("font", type=Path)
    parser.add_argument("layout", type=Path)
    args = parser.parse_args(argv)
    try:
        result = extract(_raster.read(args.image), _raster.read(args.font, ocr_engine.MAX_FONT_BYTES),
                         _raster.read(args.layout, MAX_LAYOUT_BYTES))
        sys.stdout.buffer.write(_canonical(result) + b"\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] != "extracted")


if __name__ == "__main__":
    raise SystemExit(main())
