"""Cocokkan kandidat stempel dengan pola raster yang ditambatkan.

Silhouette dari zona yang ditetapkan dibandingkan memakai IoU
pada grid standar dan pergeseran kecil. Ambang dan margin
antar pola menahan kandidat meragukan. Report menyatakan
kemiripan bentuk dan rujukan pola, tanpa autentikasi stempel.
"""
import argparse
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import sys

from . import _perception_io, _raster, _vision, ocr_engine
from .audio_pipeline import _canonical, _integer
from .document_extractor import _token
from .perceptual_memory import _digest


EDGE = 18
MAX_PATTERNS = 32


def _silhouette(image, box, light):
    raw = image.rectangle(box)
    boundary = ocr_engine._otsu(raw, image.maximum)
    if boundary is None:
        return None
    width = box[2]-box[0]
    on = [i for i, value in enumerate(raw) if (value > boundary if light else value <= boundary)]
    if not on:
        return None
    left, right = min(i%width for i in on), max(i%width for i in on)+1
    top, bottom = min(i//width for i in on), max(i//width for i in on)+1
    chosen = set(on)
    cropped = [y*width+x in chosen for y in range(top,bottom) for x in range(left,right)]
    grid = ocr_engine._scale(right-left, bottom-top, cropped, EDGE, EDGE)
    return {(index%EDGE, index//EDGE) for index, enabled in enumerate(grid) if enabled}


def _score(observed, expected, jitter):
    result = []
    for dy in range(-jitter, jitter+1):
        for dx in range(-jitter, jitter+1):
            moved = {(x+dx, y+dy) for x,y in expected}
            ratio = Fraction(len(moved & observed), len(moved | observed))
            result.append((ratio, abs(dx)+abs(dy), dx,dy))
    strength, _, x,y = min(result,key=lambda row:(-row[0], *row[1:]))
    return strength, [x,y]


def _templates(root, raw):
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_PATTERNS:
        raise ValueError("Jumlah template stempel di luar batas.")
    templates, ids = [], set()
    for row in raw:
        if not isinstance(row, dict) or set(row) != {"id", "path", "bytes", "sha256", "source_ref", "light_ink"}:
            raise ValueError("Bentuk pola stempel tidak sah.")
        key, ref = _token(row["id"], "ID pola"), _token(row["source_ref"], "Rujukan pola")
        if key in ids or type(row["light_ink"]) is not bool:
            raise ValueError("Identitas pola ganda atau polaritas tidak sah.")
        ids.add(key)
        checksum = _digest(row["sha256"])
        size = _integer(row["bytes"], 1, 800_000, "Byte pola stempel")
        content = _perception_io.read_relative(root, row["path"], size, checksum)
        if len(content) != size:
            raise ValueError("Ukuran pola stempel berbeda.")
        asset = _raster.decode(content)
        if asset.width*asset.height > 160_000:
            raise ValueError("Raster pola terlalu besar.")
        expected = _silhouette(asset, (0,0,asset.width,asset.height), row["light_ink"])
        if not expected:
            raise ValueError("Pola stempel perlu foreground.")
        templates.append((key, ref, checksum, expected))
    return templates


def read_stamp(img, root, layout):
    image = _raster.decode(img)
    plan = _vision.spec(layout, "ace.perception-stamp-layout.v1",
                        ("box", "expected_image_sha256", "minimum_iou_bp", "minimum_margin_bp", "jitter", "light_ink", "templates"))
    key = sha256(img).hexdigest()
    if _digest(plan["expected_image_sha256"]) != key:
        raise ValueError("Layout stempel merujuk gambar berbeda.")
    box = _vision.bounded_box(plan["box"], image)
    if type(plan["light_ink"]) is not bool or (box[2]-box[0])*(box[3]-box[1]) > 250_000:
        raise ValueError("Polaritas atau area stempel tidak sah.")
    threshold = _integer(plan["minimum_iou_bp"], 1, 10000, "IoU minimum")
    margin = _integer(plan["minimum_margin_bp"], 1, 10000, "Margin")
    jitter = _integer(plan["jitter"], 0, 3, "Jarak pencarian")
    templates = _templates(root, plan["templates"])
    shape = _silhouette(image, box, plan["light_ink"])
    ranking = []
    if shape:
        for label, ref, checksum, mask in templates:
            value, delta = _score(shape, mask, jitter)
            ranking.append((value,label,ref,checksum,delta))
    ranking.sort(key=lambda row:(-row[0], row[1]))
    if not ranking:
        status = "empty"
    elif ranking[0][0]*10000 < threshold:
        status = "below_threshold"
    elif len(ranking) > 1 and (ranking[0][0]-ranking[1][0])*10000 < margin:
        status = "ambiguous"
    else:
        status = "shape_match"
    return {"schema": "ace.perception-stamp-comparison.v1", "image_sha256": key, "layout_sha256": sha256(layout).hexdigest(),
            "box": box, "status": status, "pattern_id": ranking[0][1] if status == "shape_match" else None,
            "candidates": [{"pattern_id": label, "source_ref": ref, "pattern_sha256": sha, "shift": delta,
                            "iou": {"numerator": value.numerator, "denominator": value.denominator}}
                           for value,label,ref,sha,delta in ranking]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("root", type=Path)
    parser.add_argument("layout", type=Path)
    args = parser.parse_args(argv)
    try:
        result = read_stamp(_raster.read(args.image), args.root, _raster.read(args.layout, _vision.MAX_SPEC_BYTES))
        sys.stdout.buffer.write(_canonical(result)+b"\n")
    except (OSError, OverflowError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(result["status"] != "shape_match")


if __name__ == "__main__":
    raise SystemExit(main())
