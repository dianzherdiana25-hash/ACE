"""Ekstrak blok infografik dan hubungkan caption dengan region terdekat.

Zona memberikan jenis yang diharapkan. Isi teks dan angka
diverifikasi melalui OCR, sedangkan wilayah gambar membawa
observasi komponen lokal. Caption hanya dipasangkan bila kandidat
vertikal terdekat bersifat unik. Semua boks mengacu pada raster asal.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from . import _raster, _vision, document_extractor, ocr_engine, scene_describer, table_extractor
from .audio_pipeline import _canonical, _integer
from .document_extractor import _token
from .perceptual_memory import _digest


KINDS = {"heading", "text", "caption", "metric", "table", "figure"}
MAX_ZONES = 64


def _crop(image, box):
    x0,y0,x1,y1 = box
    return _vision.encode(x1-x0, y1-y0, image.rectangle(box), image.maximum)


def _box_at(inner, outer):
    return [inner[0]+outer[0], inner[1]+outer[1], inner[2]+outer[0], inner[3]+outer[1]]


def _interpret(image, box, role, options, font, light, gap):
    if role == "figure":
        if options != {}:
            raise ValueError("Opsi region figure tidak didukung.")
        result = scene_describer.describe(_crop(image, box), light_ink=light)
        for item in result["regions"]:
            item["box"] = _box_at(item["box"], box)
            for axis, zero in (("x",box[0]),("y",box[1])):
                value = item["centroid_box_ink"][axis]
                value[0] += value[1]*zero
        return "read" if result["regions"] else "empty", {"shape_counts": result["visible_shape_counts"],
                                                           "regions": result["regions"], "crop_sha256": result["image_sha256"]}
    if role == "table":
        if not isinstance(options, dict) or set(options) != {"rows", "columns", "separator_bp"}:
            raise ValueError("Opsi tabel infografik tidak sah.")
        spec = {"schema": "ace.perception-table-layout.v1", "box": [0,0,box[2]-box[0],box[3]-box[1]],
                "expected_rows": options["rows"], "expected_columns": options["columns"],
                "light_ink": light, "separator_bp": options["separator_bp"], "word_gap": gap}
        result = table_extractor.extract(_crop(image, box), font, _canonical(spec))
        for cell in result["cells"]:
            cell["box"] = _box_at(cell["box"], box)
            for char in cell["glyphs"]:
                char["box"] = _box_at(char["box"], box)
        return "read" if result["status"] == "extracted" else result["status"], {
            "rows": result["rows"], "columns": result["columns"], "crop_sha256": result["image_sha256"],
            "cells": result["cells"], "reasons": result["reasons"]}
    result = ocr_engine.read_area(image, box, font, light_ink=light, word_gap=gap)
    if role != "metric":
        if options != {}:
            raise ValueError("Opsi region teks tidak didukung.")
        return result["status"], result
    if not isinstance(options, dict) or set(options) != {"prefix", "type", "unit"} or options["type"] not in ("integer","decimal"):
        raise ValueError("Deklarasi metrik tidak sah.")
    prefix = _token(options["prefix"], "Awalan metrik")
    unit = _token(options["unit"], "Satuan metrik")
    text = result["text"]
    if not text or not text.startswith(prefix):
        value = None
    else:
        value = document_extractor._value(options["type"], text[len(prefix):].strip())
    return ("read" if value is not None else "metric_unresolved"), {**result, "value": value, "declared_unit": unit}


def _captions(rows, maximum_gap):
    figures = [item for item in rows if item["role"] in ("figure", "table", "metric")]
    captions = []
    for row in (item for item in rows if item["role"] == "caption"):
        box = row["box"]
        distances = []
        for target in figures:
            candidate = target["box"]
            distance = box[1]-candidate[3]
            common = min(box[2],candidate[2])-max(box[0],candidate[0])
            if 0 <= distance <= maximum_gap and common > 0:
                distances.append((distance,target["id"]))
        distances.sort()
        choices = [name for gap,name in distances if gap == distances[0][0]] if distances else []
        reason = "caption_unresolved" if row["status"] != "read" else "matched" if len(choices) == 1 else (
            "ambiguous" if choices else "no_target")
        captions.append({"caption_id": row["id"], "status": reason, "target_ids": choices,
                         "gap_px": distances[0][0] if choices else None})
    return captions


def extract(data, font, layout):
    image = _raster.decode(data)
    font_info = ocr_engine.Font.decode(font)
    opts = _vision.spec(layout, "ace.perception-infographic-layout.v1",
                       ("image_sha256", "light_ink", "word_gap", "maximum_caption_gap_px", "zones"))
    key = sha256(data).hexdigest()
    if _digest(opts["image_sha256"]) != key or type(opts["light_ink"]) is not bool:
        raise ValueError("Anchor raster atau polaritas infografik tidak sah.")
    gap = _integer(opts["word_gap"], 1, 4096, "Celah kata")
    captions = _integer(opts["maximum_caption_gap_px"], 0, 4096, "Jarak caption")
    zones = opts["zones"]
    if not isinstance(zones, list) or not 1 <= len(zones) <= MAX_ZONES:
        raise ValueError("Jumlah zona infografik di luar batas.")
    ordered = []
    checked = set()
    budget = 0
    for row in zones:
        if not isinstance(row, dict) or set(row) != {"id","kind","box","source_ref","options"}:
            raise ValueError("Bentuk zona infografik tidak sah.")
        key_id, role, ref = (_token(row[field], field) for field in ("id","kind","source_ref"))
        if key_id in checked or role not in KINDS:
            raise ValueError("Zona ganda atau jenis belum didukung.")
        box = _vision.bounded_box(row["box"], image)
        budget += (box[2]-box[0])*(box[3]-box[1])
        checked.add(key_id)
        ordered.append((box[1],box[0],key_id,role,box,ref,row["options"]))
    if budget > 1_500_000:
        raise ValueError("Total area infografik melampaui batas.")
    results = []
    for _,_,key_id,role,box,ref,options in sorted(ordered):
        status, payload = _interpret(image, box, role, options, font, opts["light_ink"], gap)
        results.append({"id":key_id, "role":role, "box":box, "source_ref":ref, "status":status, "data":payload})
    return {"schema":"ace.perception-infographic.v1", "image_sha256":key, "font_sha256":font_info.checksum,
            "layout_sha256":sha256(layout).hexdigest(), "regions":results, "caption_links":_captions(results,captions),
            "unresolved":[row["id"] for row in results if row["status"] != "read"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("image","font","layout"):
        parser.add_argument(name,type=Path)
    args = parser.parse_args(argv)
    try:
        result = extract(_raster.read(args.image), _raster.read(args.font,ocr_engine.MAX_FONT_BYTES),
                         _raster.read(args.layout,_vision.MAX_SPEC_BYTES))
        sys.stdout.buffer.write(_canonical(result)+b"\n")
    except (OSError,OverflowError,RecursionError,ValueError) as error:
        parser.exit(2,f"Error: {error}\n")
    return int(bool(result["unresolved"]))


if __name__ == "__main__":
    raise SystemExit(main())
