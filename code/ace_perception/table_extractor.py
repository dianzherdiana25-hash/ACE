"""Baca tabel bergaris dari raster dengan geometri sel yang eksplisit.

Pemisah dipilih dari baris/kolom dengan dukungan tinta terdaftar.
Bingkai, perpotongan, dan panjang sel diperiksa sebelum OCR.
Ketika ukuran yang diharapkan tersedia, grid parsial ditahan agar
sel yang hilang tidak menggeser kolom secara diam-diam.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from . import _raster, ocr_engine
from .audio_pipeline import _canonical, _integer
from .document_extractor import _zone


MAX_ROWS = 100
MAX_COLS = 100
MAX_CELLS = 512
MAX_LAYOUT_BYTES = 250_000
MAX_TABLE_PIXELS = 400_000


def _rulings(mask, width, height, density_bp):
    horizontal = (sum(mask[y*width:(y+1)*width])*10000 >= width*density_bp for y in range(height))
    vertical = (sum(mask[x::width])*10000 >= height*density_bp for x in range(width))
    return list(ocr_engine._bands(horizontal)), list(ocr_engine._bands(vertical))


def _intervals(bands):
    return [(start[1], stop[0]) for start, stop in zip(bands, bands[1:]) if start[1] < stop[0]]


def _intersections(mask, width, rows, columns):
    return sum(not any(mask[y*width+x] for y in range(y0, y1) for x in range(x0, x1))
               for y0, y1 in rows for x0, x1 in columns)


def _spec(raw, image):
    if not isinstance(raw, bytes) or len(raw) > MAX_LAYOUT_BYTES:
        raise ValueError("Layout tabel terlalu besar.")
    layout = json.loads(raw.decode("utf-8"), object_pairs_hook=ocr_engine._pairs)
    fields = {"schema", "box", "expected_rows", "expected_columns", "light_ink", "separator_bp", "word_gap"}
    if not isinstance(layout, dict) or set(layout) != fields or layout["schema"] != "ace.perception-table-layout.v1":
        raise ValueError("Skema layout tabel tidak sah.")
    box = _zone(layout["box"])
    if box is None or box[2] > image.width or box[3] > image.height:
        raise ValueError("Plot tabel di luar raster.")
    width, height = box[2]-box[0], box[3]-box[1]
    if width*height > MAX_TABLE_PIXELS:
        raise ValueError("Plot tabel terlalu besar.")
    rows = _integer(layout["expected_rows"], 1, MAX_ROWS, "Baris") if layout["expected_rows"] is not None else None
    columns = _integer(layout["expected_columns"], 1, MAX_COLS, "Kolom") if layout["expected_columns"] is not None else None
    separator = _integer(layout["separator_bp"], 6000, 10_000, "Dukungan pemisah")
    gap = _integer(layout["word_gap"], 1, 4096, "Jarak kata")
    polarity = layout["light_ink"]
    if type(polarity) is not bool:
        raise ValueError("Polaritas tabel perlu boolean.")
    return box, width, height, rows, columns, separator, gap, polarity


def extract(image_data, font_data, layout_data):
    image = _raster.decode(image_data)
    font = ocr_engine.Font.decode(font_data)
    box, width, height, expected_rows, expected_columns, sep, gap, light = _spec(layout_data, image)
    x0, y0, _, _ = box
    local = image.rectangle(box)
    level = ocr_engine._otsu(local, image.maximum)
    mask = [] if level is None else [(item > level) if light else (item <= level) for item in local]
    row_rules, col_rules = _rulings(mask, width, height, sep) if mask else ([], [])
    y_spans, x_spans = _intervals(row_rules), _intervals(col_rules)
    reasons = []
    if not y_spans or not x_spans:
        reasons.append("missing_rulings")
    if expected_rows is not None and expected_rows != len(y_spans):
        reasons.append("row_count_mismatch")
    if expected_columns is not None and expected_columns != len(x_spans):
        reasons.append("column_count_mismatch")
    if (len(y_spans) > MAX_ROWS or len(x_spans) > MAX_COLS or len(x_spans)*len(y_spans) > MAX_CELLS
            or len(row_rules)*len(col_rules) > MAX_CELLS*4):
        raise ValueError("Grid tabel melampaui batas.")
    joints_missing = _intersections(mask, width, row_rules, col_rules)
    if joints_missing:
        reasons.append("unjoined_rulings")
    cells = []
    if not reasons:
        for row, (top, bottom) in enumerate(y_spans, 1):
            for col, (left, right) in enumerate(x_spans, 1):
                bounds = [x0+left, y0+top, x0+right, y0+bottom]
                read = ocr_engine.read_area(image, bounds, font_data, light_ink=light, word_gap=gap)
                cells.append({"row": row, "column": col, "box": bounds, **read})
    uncertain = sum(row["status"] == "partial" for row in cells)
    return {"schema": "ace.perception-table.v1", "image_sha256": sha256(image_data).hexdigest(),
            "font_sha256": font.checksum, "layout_sha256": sha256(layout_data).hexdigest(), "box": box,
            "horizontal_rulings": [[left+y0, right+y0] for left, right in row_rules],
            "vertical_rulings": [[left+x0, right+x0] for left, right in col_rules],
            "rows": len(y_spans), "columns": len(x_spans), "missing_joints": joints_missing, "threshold": level,
            "status": "grid_incomplete" if reasons else "text_partial" if uncertain else "extracted",
            "reasons": reasons, "cells": cells}


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
