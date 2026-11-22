"""Digitalkan seri garis dari raster PGM dengan kalibrasi bersumber.

Pita tingkat abu-abu membedakan garis yang didaftarkan. Pemindaian
memakai satu kolom piksel per sampel, lalu mengambil titik tengah
jejak yang bersambung. Kolom kosong, jejak bercabang, serta garis
terlalu tebal mempertahankan nilai kosong dan koordinat diagnosis.
"""
import argparse
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import sys

from . import _raster, _vision
from .audio_pipeline import _canonical, _integer
from .diagram_reader import AXIS_VALUE
from .document_extractor import _token
from .ocr_engine import _bands


MAX_PLOT_PIXELS = 1_000_000
MAX_SERIES = 12
MAX_SAMPLES = 8000


def _axis(raw, low, high):
    if not isinstance(raw, list) or len(raw) != 2:
        raise ValueError("Sumbu perlu dua titik kalibrasi.")
    ticks = []
    for tick in raw:
        if not isinstance(tick, dict) or set(tick) != {"pixel", "value", "ref"}:
            raise ValueError("Kalibrasi perlu pixel, value, dan ref.")
        position = _integer(tick["pixel"], low, high, "Posisi kalibrasi")
        value = tick["value"]
        if not isinstance(value, str) or not AXIS_VALUE.fullmatch(value):
            raise ValueError("Skala memakai string desimal eksak.")
        ticks.append((position, Fraction(value), _token(tick["ref"], "Rujukan titik kalibrasi")))
    first, second = sorted(ticks, key=lambda item: item[0])
    if first[0] == second[0] or first[1] == second[1] or first[2] == second[2]:
        raise ValueError("Titik kalibrasi perlu posisi, nilai dan rujukan berbeda.")
    return first, second


def _series(raw, maximum):
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_SERIES:
        raise ValueError("Jumlah seri garis di luar batas.")
    items = []
    keys = set()
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"id", "gray_min", "gray_max", "max_stroke_px"}:
            raise ValueError("Bentuk seri garis tidak sah.")
        key = _token(item["id"], "ID seri")
        low = _integer(item["gray_min"], 0, maximum, "Abu minimum")
        high = _integer(item["gray_max"], low, maximum, "Abu maksimum")
        thickness = _integer(item["max_stroke_px"], 1, 128, "Tebal garis")
        if key in keys:
            raise ValueError("ID seri ganda.")
        keys.add(key)
        items.append((low, high, key, thickness))
    items.sort()
    if any(left[1] >= right[0] for left, right in zip(items, items[1:])):
        raise ValueError("Pita abu antarseri beririsan.")
    return items


def _value(axis, pixel):
    first, second = axis
    if not first[0] <= pixel <= second[0]:
        return None
    return first[1] + (second[1]-first[1])*(pixel-first[0])/(second[0]-first[0])


def _fraction(value):
    return None if value is None else {"numerator": value.numerator, "denominator": value.denominator}


def _column(column, x, top, series, axes):
    low, high, _, thickness = series
    strokes = [(top+a, top+b) for a, b in _bands(low <= gray <= high for gray in column)]
    xs, ys = axes
    x_value = _value(xs, x)
    y_value = None
    if not strokes:
        status = "missing"
    elif len(strokes) > 1:
        status = "multiple_traces"
    else:
        a, b = strokes[0]
        if b-a > thickness:
            status = "too_thick"
        else:
            y_value = _value(ys, Fraction(a+b-1, 2))
            status = "outside_calibration" if x_value is None or y_value is None else "read"
    return {"x_pixel": x, "x": _fraction(x_value), "y": _fraction(y_value) if status == "read" else None,
            "status": status, "stroke_y_intervals": [list(item) for item in strokes]}


def digitize(image_data, layout_data):
    image = _raster.decode(image_data)
    fields = ("plot", "x_axis", "y_axis", "stride_px", "series")
    layout = _vision.spec(layout_data, "ace.perception-line-chart.v1", fields)
    box = _vision.bounded_box(layout["plot"], image)
    x0, y0, x1, y1 = box
    if (x1-x0)*(y1-y0) > MAX_PLOT_PIXELS:
        raise ValueError("Plot garis melampaui batas piksel.")
    axes = (_axis(layout["x_axis"], x0, x1-1), _axis(layout["y_axis"], y0, y1-1))
    if len({tick[2] for axis in axes for tick in axis}) != 4:
        raise ValueError("Rujukan titik sumbu tidak boleh dipakai ulang.")
    groups = _series(layout["series"], image.maximum)
    step = _integer(layout["stride_px"], 1, 1024, "Langkah sampel")
    columns = range(x0, x1, step)
    if len(columns)*len(groups) > MAX_SAMPLES:
        raise ValueError("Pencuplikan seri melampaui batas.")
    raster = [image.pixels[x+y*image.width] for x in columns for y in range(y0, y1)]
    height = y1-y0
    rows = []
    for series in sorted(groups, key=lambda entry: entry[2]):
        observations = [_column(raster[i*height:(i+1)*height], x, y0, series, axes) for i, x in enumerate(columns)]
        rows.append({"id": series[2], "read": sum(row["status"] == "read" for row in observations),
                     "samples": observations})
    return {"schema": "ace.perception-digitized-lines.v1", "image_sha256": sha256(image_data).hexdigest(),
            "layout_sha256": sha256(layout_data).hexdigest(), "plot": box, "stride_px": step,
            "calibration": {axis: [{"pixel": tick[0], "value": _fraction(tick[1]), "ref": tick[2]} for tick in data]
                            for axis, data in zip(("x", "y"), axes, strict=True)},
            "series": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("layout", type=Path)
    args = parser.parse_args(argv)
    try:
        result = digitize(_raster.read(args.image), _raster.read(args.layout, _vision.MAX_SPEC_BYTES))
        sys.stdout.buffer.write(_canonical(result) + b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(any(group["read"] == 0 for group in result["series"]))


if __name__ == "__main__":
    raise SystemExit(main())
