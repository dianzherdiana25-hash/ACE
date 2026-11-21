"""Petakan wilayah antarmuka cetak dari batas geometri dan teks interior.

Komponen tinta berbingkai menjadi kandidat, dengan rasio border dan
bukti OCR yang dapat diperiksa. Bentuk yang memiliki label disebut
kandidat kontrol. Program tidak menebak tindakan maupun status
klik dari piksel dan menyimpan koordinat relatif terhadap raster.
"""
import argparse
from collections import deque
from hashlib import sha256
import json
from pathlib import Path
import sys

from . import _raster, ocr_engine


MAX_SCREEN_PIXELS = 1_200_000
MAX_FRAMES = 128
MAX_INTERIOR_PIXELS = 2_400_000


def _neighbors(index, width, total):
    x = index % width
    if x > 0:
        yield index - 1
    if x+1 < width:
        yield index+1
    if index >= width:
        yield index-width
    if index+width < total:
        yield index+width


def _components(mask, width):
    seen = bytearray(len(mask))
    queue = deque()
    for start, active in enumerate(mask):
        if not active or seen[start]:
            continue
        queue.append(start)
        seen[start] = 1
        left = right = start % width
        top = bottom = start // width
        count = 0
        while queue:
            index = queue.popleft()
            x, y = index % width, index // width
            left, right = min(left, x), max(right, x)
            top, bottom = min(top, y), max(bottom, y)
            count += 1
            for adjacent in _neighbors(index, width, len(mask)):
                if mask[adjacent] and not seen[adjacent]:
                    seen[adjacent] = 1
                    queue.append(adjacent)
        yield (left, top, right+1, bottom+1), count


def _border(mask, width, box):
    x0, y0, x1, y1 = box
    top = sum(mask[y0*width+x0:y0*width+x1])
    bottom = sum(mask[(y1-1)*width+x0:(y1-1)*width+x1])
    walls = sum(mask[y*width+x0] + mask[y*width+x1-1] for y in range(y0+1, y1-1))
    size = 2*(x1-x0+y1-y0)-4
    return top+bottom+walls, size


def _frames(mask, image, span, minimum_border):
    frames = []
    for box, count in _components(mask, image.width):
        x0, y0, x1, y1 = box
        width, height = x1-x0, y1-y0
        if min(width, height) < span:
            continue
        area = width*height
        ink, perimeter = _border(mask, image.width, box)
        if ink*10_000 < minimum_border*perimeter:
            continue
        if count*2 > area and count > ink:
            continue
        frames.append((box, ink, perimeter, count))
        if len(frames) > MAX_FRAMES:
            raise ValueError("Terlalu banyak frame pada layar.")
    return sorted(frames, key=lambda item: (item[0][1], item[0][0], item[0][3], item[0][2]))


def _nested(inner, outer):
    return outer[0] < inner[0] and outer[1] < inner[1] and inner[2] < outer[2] and inner[3] < outer[3]


def _area(box):
    return (box[2]-box[0])*(box[3]-box[1])


def _label(image, interior, font, light_ink, gap):
    x0, y0, x1, y1 = interior
    width, height = x1-x0, y1-y0
    crop = f"P5\n{width} {height}\n{image.maximum}\n".encode() + bytes(image.rectangle(interior))
    product = ocr_engine.recognize(crop, font, light_ink=light_ink, word_gap=gap, limit_bp=0)
    glyphs = []
    for row in product["lines"]:
        for glyph in row["glyphs"]:
            u0, v0, u1, v1 = glyph["box"]
            glyphs.append({"box": [x0+u0, y0+v0, x0+u1, y0+v1], "character": glyph["character"],
                           "status": glyph["status"]})
    return {"text": product["text"] if product["status"] == "read" else None,
            "status": product["status"], "glyphs": glyphs}


def inspect(image_data, font_data, *, light_ink=False, min_span=9, min_border_bp=9500, word_gap=4):
    if (type(light_ink) is not bool or type(min_span) is not int or not 3 <= min_span <= 1024
            or type(min_border_bp) is not int or not 1 <= min_border_bp <= 10_000
            or type(word_gap) is not int or not 1 <= word_gap <= 4096):
        raise ValueError("Parameter geometri layar tidak sah.")
    image = _raster.decode(image_data)
    font = ocr_engine.Font.decode(font_data)
    if len(image.pixels) > MAX_SCREEN_PIXELS:
        raise ValueError("Raster layar terlalu besar.")
    threshold = ocr_engine._otsu(image.pixels, image.maximum)
    regions = []
    if threshold is not None:
        mask = tuple((value > threshold) if light_ink else (value <= threshold) for value in image.pixels)
        regions = _frames(mask, image, min_span, min_border_bp)
    names = [f"e{index}" for index in range(1, len(regions)+1)]
    budget = 0
    output = []
    for index, (box, ink, perimeter, component) in enumerate(regions):
        inner = [candidate for candidate, (other, *_) in enumerate(regions) if _nested(other, box)]
        containing = [candidate for candidate, (other, *_) in enumerate(regions) if _nested(box, other)]
        parent = min(containing, key=lambda item: _area(regions[item][0])) if containing else None
        if inner:
            result = {"text": None, "status": "contains_regions", "glyphs": []}
        else:
            x0, y0, x1, y1 = box
            interior = (x0+1, y0+1, x1-1, y1-1)
            budget += _area(interior)
            if budget > MAX_INTERIOR_PIXELS:
                raise ValueError("Jumlah interior frame melampaui batas OCR.")
            result = _label(image, interior, font_data, light_ink, word_gap)
        kind = "container" if inner else "labeled_control_candidate" if result["status"] == "read" else "frame"
        output.append({"id": names[index], "parent": names[parent] if parent is not None else None, "box": list(box),
                       "kind": kind, "border_pixels": ink, "perimeter_pixels": perimeter,
                       "component_pixels": component, "label": result})
    return {"schema": "ace.perception-screen-regions.v1", "image_sha256": sha256(image_data).hexdigest(),
            "font_sha256": font.checksum, "width": image.width, "height": image.height, "threshold": threshold,
            "elements": output}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("font", type=Path)
    parser.add_argument("--light-ink", action="store_true")
    parser.add_argument("--min-span", type=int, default=9)
    parser.add_argument("--min-border-bp", type=int, default=9500)
    parser.add_argument("--word-gap", type=int, default=4)
    args = parser.parse_args(argv)
    try:
        report = inspect(_raster.read(args.image), _raster.read(args.font, ocr_engine.MAX_FONT_BYTES),
                         light_ink=args.light_ink, min_span=args.min_span,
                         min_border_bp=args.min_border_bp, word_gap=args.word_gap)
        sys.stdout.write(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))+"\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
