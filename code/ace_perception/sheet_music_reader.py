"""Baca posisi notehead hitam pada satu staf bergaris dari raster.

Lima garis dan jaraknya perlu terbaca sebelum pitch diberikan.
Pemisah horizontal membantu menolak stem tipis dan garis staf.
Keluaran memakai urutan posisi x serta pitch diatonik dari clef
yang dinyatakan. Rhythm dan accidental belum dinilai di sini.
"""
import argparse
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from statistics import median
import sys

from . import _raster, _vision, ocr_engine
from .audio_pipeline import _canonical, _integer
from .screen_understanding import _components


CLEF = {"treble": ("E", 4), "bass": ("G", 2)}
SCALE = "CDEFGAB"


def _staff(mask, width, height, density):
    bands = list(ocr_engine._bands(sum(mask[y*width:(y+1)*width])*10_000 >= density*width
                                   for y in range(height)))
    if len(bands) != 5:
        return bands, None
    centers2 = [left+right-1 for left, right in bands]
    intervals = [right-left for left, right in zip(centers2, centers2[1:])]
    stride = median(intervals)
    if stride < 6 or any(abs(item-stride) > 2 for item in intervals):
        return bands, None
    return bands, Fraction(stride)/2


def _note_mask(mask, width, height, staff, low, high):
    without_stems = bytearray(width*height)
    excluded = {y for start, stop in staff for y in range(start, stop)}
    for y in range(height):
        if y in excluded:
            continue
        start = y*width
        for lo, hi in ocr_engine._bands(mask[start:start+width]):
            if low <= hi-lo <= high:
                without_stems[start+lo:start+hi] = b"\x01"*(hi-lo)
    for top, bottom in staff:
        if top == 0 or bottom == height:
            continue
        for x in range(width):
            if without_stems[(top-1)*width+x] and without_stems[bottom*width+x]:
                for y in range(top, bottom):
                    without_stems[y*width+x] = 1
    return without_stems


def _pitch(clef, step):
    label, octave = CLEF[clef]
    index = octave*7+SCALE.index(label)+step
    octave, letter = divmod(index, 7)
    return f"{SCALE[letter]}{octave}"


def read_staff(image_data, layout):
    image = _raster.decode(image_data)
    fields = ("box", "clef", "light_ink", "line_coverage_bp", "min_head_width_px", "max_head_width_px",
              "min_head_pixels", "pitch_tolerance_bp")
    raw = _vision.spec(layout, "ace.perception-sheet-layout.v1", fields)
    staff = _vision.bounded_box(raw["box"], image)
    x0, y0, x1, y1 = staff
    width, height = x1-x0, y1-y0
    if width*height > 600_000:
        raise ValueError("Area staf terlalu besar.")
    clef = raw["clef"]
    if type(raw["light_ink"]) is not bool or not isinstance(clef, str) or clef not in CLEF:
        raise ValueError("Clef atau polaritas staf tidak sah.")
    coverage = _integer(raw["line_coverage_bp"], 6000, 10000, "Coverage garis staf")
    low = _integer(raw["min_head_width_px"], 2, width, "Lebar minimum notehead")
    high = _integer(raw["max_head_width_px"], low, min(width, 64), "Lebar maksimum notehead")
    minimum = _integer(raw["min_head_pixels"], 1, 1024, "Piksel minimum notehead")
    tolerance = _integer(raw["pitch_tolerance_bp"], 1, 5000, "Toleransi pitch")
    samples = image.rectangle(staff)
    level = ocr_engine._otsu(samples, image.maximum)
    if level is None:
        mask = []
        bands, spacing = [], None
    else:
        mask = [value > level if raw["light_ink"] else value <= level for value in samples]
        bands, spacing = _staff(mask, width, height, coverage)
    rows = []
    if spacing is not None:
        body = _note_mask(mask, width, height, bands, low, high)
        baseline = Fraction(sum(bands[-1])-1, 2)
        for box, count in _components(body, width):
            if count < minimum:
                continue
            left, top, right, bottom = box
            if right-left > high or bottom-top > 2*spacing:
                continue
            position = Fraction(baseline-Fraction(top+bottom-1, 2))*2/spacing
            step = round(position)
            meaningful = abs(step-position)*10000 <= tolerance
            rows.append({"box": [x0+left, y0+top, x0+right, y0+bottom], "ink_pixels": count,
                         "step_from_bottom": step if meaningful else None,
                         "pitch": _pitch(clef, step) if meaningful else None,
                         "status": "read" if meaningful else "unresolved_pitch"})
            if len(rows) > 512:
                raise ValueError("Jumlah notehead melebihi batas.")
        rows.sort(key=lambda row: (row["box"][0], row["box"][1], row["box"]))
    return {"schema": "ace.perception-sheet-notes.v1", "image_sha256": sha256(image_data).hexdigest(),
            "layout_sha256": sha256(layout).hexdigest(), "clef": clef, "threshold": level,
            "status": "unresolved_staff" if spacing is None else "partial" if any(row["pitch"] is None for row in rows) else "read",
            "staff_bands": [[y0+a, y0+b] for a, b in bands], "notes": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("layout", type=Path)
    args = parser.parse_args(argv)
    try:
        report = read_staff(_raster.read(args.image), _raster.read(args.layout, _vision.MAX_SPEC_BYTES))
        sys.stdout.buffer.write(_canonical(report)+b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report["status"] != "read")


if __name__ == "__main__":
    raise SystemExit(main())
