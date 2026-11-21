"""Baca jarum meteran lokal berdasarkan pusat dan skala yang dirujuk.

Setiap sudut dinilai dari jumlah piksel tinta pada annulus. Kandidat
di luar lebar puncak menjadi pembanding untuk menahan jarum ganda.
Nilai hanya dihitung pada sweep terkalibrasi dengan bukti yang cukup,
menggunakan interpolasi rasional dari sudut yang terpilih.
"""
import argparse
from fractions import Fraction
from hashlib import sha256
from math import cos, radians, sin
from pathlib import Path
import sys

from . import _raster, _vision
from .audio_pipeline import _canonical, _integer
from .diagram_reader import AXIS_VALUE
from .document_extractor import _token


def _tick(raw):
    if not isinstance(raw, dict) or set(raw) != {"degrees", "value", "ref"}:
        raise ValueError("Titik meteran perlu sudut, nilai dan rujukan.")
    degrees = _integer(raw["degrees"], 0, 359, "Sudut meteran")
    value = raw["value"]
    if not isinstance(value, str) or not AXIS_VALUE.fullmatch(value):
        raise ValueError("Nilai skala perlu desimal eksak.")
    return degrees, Fraction(value), _token(raw["ref"], "Rujukan titik meteran")


def _fraction(value):
    return {"numerator": value.numerator, "denominator": value.denominator} if value is not None else None


def _ray(image, point, begin, end, degree, threshold, light):
    direction = radians(degree)
    ux, uy = cos(direction), sin(direction)
    cells = {(round(point[0]+r*ux), round(point[1]+r*uy)) for r in range(begin, end+1)}
    count = 0
    for x, y in cells:
        value = image.pixels[y*image.width+x]
        count += int(value > threshold if light else value <= threshold)
    return Fraction(count, len(cells)), count, len(cells)


def estimate(data, layout):
    image = _raster.decode(data)
    opts = _vision.spec(layout, "ace.perception-gauge-layout.v1",
                       ("center", "inner_radius", "outer_radius", "threshold", "light_ink", "scale", "sweep",
                        "minimum_ink_bp", "minimum_margin_bp", "peak_width_degrees", "unit"))
    center = opts["center"]
    if not isinstance(center, list) or len(center) != 2:
        raise ValueError("Pusat meteran perlu dua koordinat.")
    point = (_integer(center[0], 0, image.width-1, "Pusat x"), _integer(center[1], 0, image.height-1, "Pusat y"))
    pad = min(point[0], point[1], image.width-1-point[0], image.height-1-point[1])
    begin = _integer(opts["inner_radius"], 1, min(pad, 512), "Radius dalam")
    end = _integer(opts["outer_radius"], begin+1, min(pad, 1024), "Radius luar")
    cutoff = _integer(opts["threshold"], 0, image.maximum, "Ambang tinta")
    support = _integer(opts["minimum_ink_bp"], 1, 10_000, "Tinta minimum")
    margin = _integer(opts["minimum_margin_bp"], 1, 10_000, "Margin jarum")
    peak_width = _integer(opts["peak_width_degrees"], 0, 30, "Lebar puncak")
    if type(opts["light_ink"]) is not bool or opts["sweep"] not in ("clockwise", "counterclockwise"):
        raise ValueError("Polaritas atau arah putar meteran tidak sah.")
    scale = opts["scale"]
    if not isinstance(scale, list) or len(scale) != 2:
        raise ValueError("Perlu dua titik skala meteran.")
    first, last = map(_tick, scale)
    sign = 1 if opts["sweep"] == "clockwise" else -1
    arc = ((last[0]-first[0])*sign) % 360
    if not arc or first[1] == last[1] or first[2] == last[2] or peak_width >= arc:
        raise ValueError("Skala meteran memberi sweep atau rujukan yang tidak terbedakan.")
    angles = [(first[0]+offset*sign) % 360 for offset in range(arc+1)]
    evidence = [_ray(image, point, begin, end, degree, cutoff, opts["light_ink"]) for degree in angles]
    ranking = sorted(range(len(angles)), key=lambda index: (-evidence[index][0], index))
    initial = ranking[0]
    top = evidence[initial][0]
    tied = [index for index in ranking if evidence[index][0] == top]
    selected = tied[(len(tied)-1)//2]
    nearby = max(tied)-min(tied) <= peak_width and max(tied)-min(tied)+1 == len(tied)
    competitors = [index for index in ranking if abs(index-selected) > peak_width]
    runner = evidence[competitors[0]][0] if competitors else None
    if top*10_000 < support:
        status = "insufficient_ink"
    elif not nearby or runner is None or (top-runner)*10_000 < margin:
        status = "ambiguous"
    else:
        status = "read"
    value = first[1]+(last[1]-first[1])*Fraction(selected, arc) if status == "read" else None
    return {"schema": "ace.perception-gauge-read.v1", "image_sha256": sha256(data).hexdigest(),
            "layout_sha256": sha256(layout).hexdigest(), "status": status, "unit": _token(opts["unit"], "Satuan"),
            "center": list(point), "value": _fraction(value), "needle_degrees": angles[selected] if status == "read" else None,
            "tied_angles": [angles[index] for index in sorted(tied)], "peak_ink_ratio": _fraction(top),
            "runner_ink_ratio": _fraction(runner), "scale_refs": [first[2], last[2]],
            "rays": [{"degrees": degree, "ink": item[1], "pixels": item[2]}
                     for degree, item in zip(angles, evidence, strict=True)]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("layout", type=Path)
    args = parser.parse_args(argv)
    try:
        report = estimate(_raster.read(args.image), _raster.read(args.layout, _vision.MAX_SPEC_BYTES))
        sys.stdout.buffer.write(_canonical(report)+b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report["status"] != "read")


if __name__ == "__main__":
    raise SystemExit(main())
