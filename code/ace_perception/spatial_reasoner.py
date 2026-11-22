"""Hitung relasi dan jarak dua dimensi dari boks media tertambat.

Jarak pusat, jarak antartepi, serta IoU dihitung sebagai pecahan.
Kalibrasi opsional memakai dua titik dan panjang bersumber. Relasi
boks dibedakan dari posisi pusat, sehingga overlap dan sentuhan
tidak dianggap bukti arah yang lebih kuat.
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
from .perceptual_memory import _digest


MAX_OBJECTS = 128
MAX_QUERIES = 512


def _q(value):
    return None if value is None else {"numerator": value.numerator, "denominator": value.denominator}


def _area(box):
    return (box[2]-box[0])*(box[3]-box[1])


def _scale(raw, image):
    if raw is None:
        return None, None
    if not isinstance(raw, dict) or set(raw) != {"points", "length", "unit", "ref"}:
        raise ValueError("Bentuk kalibrasi spasial tidak sah.")
    points = raw["points"]
    if not isinstance(points, list) or len(points) != 2:
        raise ValueError("Kalibrasi membutuhkan dua titik.")
    confirmed = []
    for row in points:
        if not isinstance(row, list) or len(row) != 2:
            raise ValueError("Titik kalibrasi memerlukan dua koordinat.")
        confirmed.append((_integer(row[0], 0, image.width-1, "Titik x"),
                          _integer(row[1], 0, image.height-1, "Titik y")))
    a, b = confirmed
    dist = (a[0]-b[0])**2+(a[1]-b[1])**2
    number = raw["length"]
    if not isinstance(number, str) or not AXIS_VALUE.fullmatch(number) or Fraction(number) <= 0 or not dist:
        raise ValueError("Kalibrasi perlu panjang positif dan titik yang berbeda.")
    scale = Fraction(number)**2/dist
    return scale, {"points": points, "ref": _token(raw["ref"], "Rujukan kalibrasi"),
                   "unit": _token(raw["unit"], "Satuan"), "unit_square_per_pixel_square": _q(scale)}


def _relation(a, b, scale):
    dx = Fraction(a[0]+a[2]-b[0]-b[2], 2)
    dy = Fraction(a[1]+a[3]-b[1]-b[3], 2)
    gx = max(a[0]-b[2], b[0]-a[2], 0)
    gy = max(a[1]-b[3], b[1]-a[3], 0)
    core_x = max(0, min(a[2], b[2])-max(a[0], b[0]))
    core_y = max(0, min(a[3], b[3])-max(a[1], b[1]))
    area = core_x*core_y
    overlap = Fraction(area, _area(a)+_area(b)-area)
    center = dx*dx+dy*dy
    edge = Fraction(gx*gx+gy*gy)
    horizontal = "left_of" if a[2] <= b[0] else "right_of" if b[2] <= a[0] else "horizontal_overlap"
    vertical = "above" if a[3] <= b[1] else "below" if b[3] <= a[1] else "vertical_overlap"
    return {"horizontal": horizontal, "vertical": vertical,
            "box_interaction": "overlaps" if area else "touches" if not edge else "separated",
            "intersection_pixels": area, "iou": _q(overlap), "center_delta_x": _q(dx), "center_delta_y": _q(dy),
            "center_pixel_distance_squared": _q(center), "edge_pixel_distance_squared": _q(edge),
            "center_unit_distance_squared": _q(center*scale if scale is not None else None),
            "edge_unit_distance_squared": _q(edge*scale if scale is not None else None)}


def reason(image_data, layout):
    image = _raster.decode(image_data)
    checksum = sha256(image_data).hexdigest()
    raw = _vision.spec(layout, "ace.perception-spatial-layout.v1", ("image_sha256", "objects", "queries", "scale"))
    if _digest(raw["image_sha256"]) != checksum:
        raise ValueError("Relasi spasial menunjuk gambar berbeda.")
    width = raw["objects"]
    if not isinstance(width, list) or len(width) > MAX_OBJECTS:
        raise ValueError("Jumlah boks di luar batas.")
    objects = {}
    for row in width:
        if not isinstance(row, dict) or set(row) != {"id", "box", "ref"}:
            raise ValueError("Bentuk objek spasial tidak sah.")
        key = _token(row["id"], "ID objek")
        if key in objects:
            raise ValueError("ID boks spasial ganda.")
        objects[key] = (_vision.bounded_box(row["box"], image), _token(row["ref"], "Rujukan boks"))
    if not isinstance(raw["queries"], list) or len(raw["queries"]) > MAX_QUERIES:
        raise ValueError("Jumlah kueri relasi di luar batas.")
    ratio, proof = _scale(raw["scale"], image)
    seen = set()
    relations = []
    for pair in raw["queries"]:
        if not isinstance(pair, list) or len(pair) != 2:
            raise ValueError("Kueri spasial perlu dua ID.")
        a, b = (_token(key, "ID kueri") for key in pair)
        if a == b or a not in objects or b not in objects or (a, b) in seen:
            raise ValueError("Kueri spasial belum terdaftar atau ganda.")
        seen.add((a, b))
        box_a, ref_a = objects[a]
        box_b, ref_b = objects[b]
        relations.append({"a": a, "b": b, "a_ref": ref_a, "b_ref": ref_b, **_relation(box_a, box_b, ratio)})
    return {"schema": "ace.perception-spatial-relations.v1", "image_sha256": checksum,
            "layout_sha256": sha256(layout).hexdigest(), "calibration": proof, "relations": relations}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("layout", type=Path)
    args = parser.parse_args(argv)
    try:
        result = reason(_raster.read(args.image), _raster.read(args.layout, _vision.MAX_SPEC_BYTES))
        sys.stdout.buffer.write(_canonical(result)+b"\n")
    except (OSError, OverflowError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
