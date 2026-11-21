"""Baca glyph tulisan tangan terpisah dengan contoh dari beberapa penulis.

Satu kotak berisi satu glyph. Silhouette dinormalisasi dan geometri
dibandingkan dengan Hamming, jarak profil elastis, dan aspek asli.
Skor kelas memakai beberapa penulis unik. Hasil yang lemah atau
seri mempertahankan status unresolved beserta jarak dan jejak contoh.
"""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys

from . import _raster, ocr_engine
from .audio_pipeline import _canonical, _integer
from .document_extractor import _token, _zone
from .perceptual_memory import _digest


SIZE = 12
MAX_TEMPLATES = 256
MAX_BOXES = 128
MAX_CELLS = 2_000_000
MAX_INDEX_BYTES = 2_000_000


def _shape(mask, width):
    active = [(index % width, index // width) for index, item in enumerate(mask) if item]
    if not active:
        return None
    x0, x1 = min(x for x, _ in active), max(x for x, _ in active)+1
    y0, y1 = min(y for _, y in active), max(y for _, y in active)+1
    trimmed = [mask[y*width+x] for y in range(y0, y1) for x in range(x0, x1)]
    pixels = ocr_engine._scale(x1-x0, y1-y0, trimmed, SIZE, SIZE)
    row_profile = tuple(sum(pixels[y*SIZE:(y+1)*SIZE]) for y in range(SIZE))
    col_profile = tuple(sum(pixels[x::SIZE]) for x in range(SIZE))
    return pixels, row_profile, col_profile, ocr_engine._aspect(x1-x0, y1-y0)


def _warp(first, second):
    penalty = SIZE+1
    cap = SIZE*SIZE*3
    previous = [0]+[cap]*SIZE
    for i, left in enumerate(first, 1):
        current = [cap]*(SIZE+1)
        for j in range(max(1, i-1), min(i+1, SIZE)+1):
            diagonal, repeat_first, repeat_second = previous[j-1], previous[j]+penalty, current[j-1]+penalty
            current[j] = abs(left-second[j-1]) + min(diagonal, repeat_first, repeat_second)
        previous = current
    return previous[-1]


def _distance(first, second):
    raw_first, rows_first, col_first, aspect_first = first
    raw_second, rows_second, col_second, aspect_second = second
    pixels = sum(left != right for left, right in zip(raw_first, raw_second, strict=True))*10000//(SIZE*SIZE)
    projections = (_warp(rows_first, rows_second)+_warp(col_first, col_second))*10000//(2*SIZE*SIZE)
    return (4*pixels+min(10000, projections)+abs(aspect_first-aspect_second))//6


def _templates(data):
    if not isinstance(data, bytes) or len(data) > MAX_INDEX_BYTES:
        raise ValueError("Berkas contoh tulisan terlalu besar.")
    raw = json.loads(data.decode("utf-8"), object_pairs_hook=ocr_engine._pairs)
    if not isinstance(raw, dict) or set(raw) != {"schema", "examples"} or raw["schema"] != "ace.handwriting-examples.v1":
        raise ValueError("Skema contoh tulisan tidak sah.")
    rows = raw["examples"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_TEMPLATES:
        raise ValueError("Jumlah contoh tulisan di luar batas.")
    refs = set()
    templates = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"character", "writer_code", "receipt_ref", "grid"}:
            raise ValueError("Contoh tulisan tidak sesuai skema.")
        label = _token(row["character"], "Label contoh")
        writer = _token(row["writer_code"], "Kode penulis")
        source = _token(row["receipt_ref"], "Rujukan contoh")
        if len(label) != 1 or label == "\ufffd" or source in refs:
            raise ValueError("Label bukan satu karakter atau rujukan contoh ganda.")
        refs.add(source)
        width, _, cells = ocr_engine._matrix(row["grid"])
        templates.append((label, writer, source, _shape(cells, width)))
    return templates


def _roster(data, width, height):
    if not isinstance(data, bytes) or len(data) > MAX_INDEX_BYTES:
        raise ValueError("Roster tulisan terlalu besar.")
    raw = json.loads(data.decode("utf-8"), object_pairs_hook=ocr_engine._pairs)
    if not isinstance(raw, dict) or set(raw) != {"schema", "template_sha256", "light_ink", "minimum_writers",
                                              "distance_bp", "margin_bp", "exclude_writer_code", "cells"}:
        raise ValueError("Bentuk roster tulisan tidak sah.")
    if raw["schema"] != "ace.handwriting-cells.v1" or type(raw["light_ink"]) is not bool:
        raise ValueError("Skema atau polaritas roster tulisan tidak sah.")
    if raw["exclude_writer_code"] is not None:
        _token(raw["exclude_writer_code"], "Kode penulis untuk dipisahkan")
    if not isinstance(raw["cells"], list) or not 1 <= len(raw["cells"]) <= MAX_BOXES:
        raise ValueError("Jumlah kotak tulisan di luar batas.")
    cells = []
    keys = set()
    consumed = 0
    for row in raw["cells"]:
        if not isinstance(row, dict) or set(row) != {"id", "box"}:
            raise ValueError("Bentuk kotak tulisan tidak sah.")
        key = _token(row["id"], "ID kotak")
        box = _zone(row["box"])
        if key in keys or box is None or box[2] > width or box[3] > height:
            raise ValueError("Kotak tulisan ganda atau di luar gambar.")
        keys.add(key)
        consumed += (box[2]-box[0])*(box[3]-box[1])
        cells.append((key, box))
    if consumed > MAX_CELLS:
        raise ValueError("Total ukuran kotak melampaui batas.")
    _integer(raw["minimum_writers"], 1, 8, "Jumlah penulis")
    _integer(raw["distance_bp"], 0, 10_000, "Jarak tulisan")
    _integer(raw["margin_bp"], 1, 10_000, "Margin tulisan")
    return raw, cells


def _rank(shape, templates, minimum):
    per_label = defaultdict(dict)
    for label, writer, ref, target in templates:
        result = (_distance(shape, target), ref, writer)
        if writer not in per_label[label] or result < per_label[label][writer]:
            per_label[label][writer] = result
    ranked = []
    for label, writers in per_label.items():
        if len(writers) >= minimum:
            retained = sorted(writers.values())[:minimum]
            score = sum(row[0] for row in retained)//minimum
            ranked.append({"label": label, "distance_bp": score, "evidence": [
                {"distance_bp": d, "receipt_ref": ref, "writer_code": writer} for d, ref, writer in retained]})
    return sorted(ranked, key=lambda row: (row["distance_bp"], row["label"]))


def read_cells(image_data, templates, layout):
    image = _raster.decode(image_data)
    config, cells = _roster(layout, image.width, image.height)
    target_sha = sha256(templates).hexdigest()
    if _digest(config["template_sha256"]) != target_sha:
        raise ValueError("Berkas contoh berbeda dari hash roster.")
    examples = [row for row in _templates(templates) if row[1] != config["exclude_writer_code"]]
    rows = []
    for key, box in cells:
        values = image.rectangle(box)
        threshold = ocr_engine._otsu(values, image.maximum)
        shape = None
        if threshold is not None:
            mask = [(value > threshold) if config["light_ink"] else (value <= threshold) for value in values]
            shape = _shape(mask, box[2]-box[0])
        ranked = _rank(shape, examples, config["minimum_writers"]) if shape is not None else []
        if shape is None:
            status = "empty"
        elif not ranked:
            status = "no_writer_support"
        elif ranked[0]["distance_bp"] > config["distance_bp"]:
            status = "too_far"
        elif len(ranked) > 1 and ranked[1]["distance_bp"]-ranked[0]["distance_bp"] < config["margin_bp"]:
            status = "ambiguous"
        else:
            status = "read"
        rows.append({"id": key, "box": box, "status": status, "threshold": threshold,
                     "character": ranked[0]["label"] if status == "read" else None, "candidates": ranked[:2]})
    return {"schema": "ace.perception-handwritten-cells.v1", "image_sha256": sha256(image_data).hexdigest(),
            "template_sha256": target_sha, "layout_sha256": sha256(layout).hexdigest(),
            "text": "".join(row["character"] or "\ufffd" for row in rows), "cells": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("examples", type=Path)
    parser.add_argument("layout", type=Path)
    args = parser.parse_args(argv)
    try:
        value = read_cells(_raster.read(args.image), _raster.read(args.examples, MAX_INDEX_BYTES),
                           _raster.read(args.layout, MAX_INDEX_BYTES))
        sys.stdout.buffer.write(_canonical(value) + b"\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(any(row["status"] != "read" for row in value["cells"]))


if __name__ == "__main__":
    raise SystemExit(main())
