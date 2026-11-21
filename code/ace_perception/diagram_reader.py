"""Ubah diagram batang raster menjadi tabel data dengan kalibrasi eksplisit.

Wilayah plot bebas sumbu ditetapkan bersama pita tiap kategori.
Dua tanda skala memberi interpolasi linear rasional dari tepi
batang. Batang kosong, ganda, di luar kalibrasi, atau melintasi
baseline tidak diberi nilai. Laporan menyimpan boks yang dinilai.
"""
import argparse
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

from . import _raster, ocr_engine
from .document_extractor import _token, _zone
from .screen_understanding import _components


MAX_LAYOUT_BYTES = 250_000
MAX_CATEGORIES = 128
MAX_PLOT_PIXELS = 1_200_000
AXIS_VALUE = re.compile(r"[-+]?[0-9]{1,18}(?:\.[0-9]{1,8})?")


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("Posisi integer diagram di luar batas.")
    return value


def _tick(raw, plot):
    if not isinstance(raw, dict) or set(raw) != {"y", "value", "ref"}:
        raise ValueError("Kalibrasi memerlukan y, value, dan ref.")
    number = raw["value"]
    if not isinstance(number, str) or not AXIS_VALUE.fullmatch(number):
        raise ValueError("Nilai sumbu perlu string desimal bertitik.")
    return _integer(raw["y"], plot[1], plot[3]), Fraction(number), _token(raw["ref"], "Rujukan tick")


def _categories(raw, plot):
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_CATEGORIES:
        raise ValueError("Jumlah kategori di luar batas.")
    bands = []
    names = set()
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"id", "x_start", "x_stop"}:
            raise ValueError("Bentuk pita kategori tidak dikenal.")
        key = _token(item["id"], "Kategori")
        start = _integer(item["x_start"], plot[0], plot[2]-1)
        stop = _integer(item["x_stop"], start+1, plot[2])
        if key in names:
            raise ValueError("Kategori diagram ganda.")
        bands.append((start, stop, key))
        names.add(key)
    bands.sort()
    if any(prior[1] > current[0] for prior, current in zip(bands, bands[1:])):
        raise ValueError("Pita kategori tidak boleh beririsan.")
    return bands


def _layout(layout_data, image):
    if not isinstance(layout_data, bytes) or len(layout_data) > MAX_LAYOUT_BYTES:
        raise ValueError("Layout diagram terlalu besar.")
    raw = json.loads(layout_data.decode("utf-8"), object_pairs_hook=ocr_engine._pairs)
    fields = {"schema", "plot", "baseline_y", "ticks", "categories", "minimum_fill_bp", "minimum_width", "light_ink", "unit"}
    if not isinstance(raw, dict) or set(raw) != fields or raw["schema"] != "ace.perception-bar-layout.v1":
        raise ValueError("Skema layout diagram tidak sah.")
    plot = _zone(raw["plot"])
    if plot is None or plot[2] > image.width or plot[3] > image.height:
        raise ValueError("Plot di luar raster.")
    if (plot[2]-plot[0])*(plot[3]-plot[1]) > MAX_PLOT_PIXELS:
        raise ValueError("Plot melebihi batas piksel.")
    baseline = _integer(raw["baseline_y"], plot[1], plot[3])
    if not isinstance(raw["ticks"], list) or len(raw["ticks"]) != 2:
        raise ValueError("Kalibrasi membutuhkan dua tanda skala.")
    first, second = sorted((_tick(row, plot) for row in raw["ticks"]), key=lambda item: item[0])
    if first[0] == second[0] or first[1] == second[1] or first[2] == second[2]:
        raise ValueError("Tanda skala harus berbeda posisi, nilai, dan sumber.")
    slope = (second[1]-first[1])/(second[0]-first[0])
    if not first[0] <= baseline <= second[0] or first[1]+(baseline-first[0])*slope != 0:
        raise ValueError("Baseline tidak cocok dengan titik nol hasil kalibrasi.")
    if type(raw["light_ink"]) is not bool:
        raise ValueError("Polaritas plot perlu boolean.")
    fill = _integer(raw["minimum_fill_bp"], 1, 10_000)
    width = _integer(raw["minimum_width"], 1, plot[2]-plot[0])
    return plot, (first, second, slope), baseline, _categories(raw["categories"], plot), fill, width, raw["light_ink"], _token(raw["unit"], "Satuan")


def _allocate(components, bands, plot, minimum_fill, minimum_width):
    unassigned = []
    found = {key: [] for _, _, key in bands}
    for box, count in components:
        x0, y0, x1, y1 = box
        width, height = x1-x0, y1-y0
        if width < minimum_width or count*10_000 < width*height*minimum_fill:
            continue
        box = [x0+plot[0], y0+plot[1], x1+plot[0], y1+plot[1]]
        item = {"box": box, "filled_pixels": count}
        eligible = [key for start, stop, key in bands if start <= box[0] and box[2] <= stop]
        if eligible:
            found[eligible[0]].append(item)
        else:
            unassigned.append(item)
    return found, unassigned


def _cell(key, items, baseline, first, second, slope):
    value = None
    extreme = None
    if not items:
        status = "missing"
    elif len(items) > 1:
        status = "ambiguous"
    else:
        _, y0, _, y1 = items[0]["box"]
        if baseline == y1:
            extreme = y0
        elif baseline == y0:
            extreme = y1
        if extreme is None:
            status = "unattached_bar"
        elif not first[0] <= extreme <= second[0]:
            status = "outside_calibration"
        else:
            value = first[1] + (extreme-first[0])*slope
            status = "read"
    return {"category": key, "status": status, "value": None if value is None else {
        "numerator": value.numerator, "denominator": value.denominator}, "measured_y": extreme, "evidence": items}


def read_chart(image_data, layout_data):
    image = _raster.decode(image_data)
    plot, (first, second, slope), baseline, bands, minimum_fill, width, positive, unit = _layout(layout_data, image)
    samples = image.rectangle(plot)
    level = ocr_engine._otsu(samples, image.maximum)
    if level is None:
        components = []
    else:
        mask = tuple((value > level) if positive else (value <= level) for value in samples)
        components = _components(mask, plot[2]-plot[0])
    found, unassigned = _allocate(components, bands, plot, minimum_fill, width)
    rows = [_cell(key, found[key], baseline, first, second, slope) for _, _, key in bands]
    return {"schema": "ace.perception-diagram-table.v1", "image_sha256": sha256(image_data).hexdigest(),
            "layout_sha256": sha256(layout_data).hexdigest(), "unit": unit, "plot": plot, "baseline_y": baseline,
            "calibration_refs": [{"y": item[0], "ref": item[2]} for item in (first, second)], "threshold": level,
            "status": "complete" if all(row["status"] == "read" for row in rows) and not unassigned else "incomplete",
            "rows": rows, "unassigned_bars": unassigned}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("layout", type=Path)
    args = parser.parse_args(argv)
    try:
        result = read_chart(_raster.read(args.image), _raster.read(args.layout, MAX_LAYOUT_BYTES))
        sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))+"\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] != "complete")


if __name__ == "__main__":
    raise SystemExit(main())
