"""Deskripsikan adegan sebagai wilayah yang ditentukan oleh bukti piksel.

Ambang tinta dan komponen terkoneksi menghasilkan wilayah kandidat.
Statistik fill, centroid dan sebaran intensitas menggambarkan tiap
wilayah. Relasi geometris memakai boks dengan tepi eksklusif.
Kosakata keluaran terbatas pada properti yang dapat dihitung ulang.
"""
import argparse
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
import sys

from . import _raster, _vision
from .audio_pipeline import _canonical, _integer
from .ocr_engine import _otsu
from .screen_understanding import _components


MAX_SCENE_PIXELS = 800_000
MAX_REGIONS = 96
MAX_FEATURE_PIXELS = 2_000_000


def _features(image, mask, box, known_count):
    x0, y0, x1, y1 = box
    width, height = x1-x0, y1-y0
    gray = []
    sx = sy = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            position = y*image.width+x
            if mask[position]:
                gray.append(image.pixels[position])
                sx += x
                sy += y
    # Boks bersarang dapat meliputi komponen lain, sehingga jumlah boks
    # dan jumlah komponen dipublikasikan sebagai dua observasi berbeda.
    area = width*height
    density = len(gray)*10000//area
    form = "elongated_horizontal" if width >= height*2 else "elongated_vertical" if height >= width*2 else (
        "compact" if density >= 8000 else "irregular")
    return {"box": list(box), "component_pixels": known_count, "box_ink_pixels": len(gray),
            "centroid_box_ink": {"x": [sx, len(gray)], "y": [sy, len(gray)]},
            "fill_bp": density, "shape_hint": form, "intensity": {"min": min(gray), "max": max(gray),
            "mean": [sum(gray), len(gray)]}}


def _intersection(a, b):
    overlap_x = min(a[2], b[2]) - max(a[0], b[0])
    overlap_y = min(a[3], b[3]) - max(a[1], b[1])
    return max(overlap_x, 0)*max(overlap_y, 0)


def _inside(left, right):
    return left != right and all((right[0] <= left[0], right[1] <= left[1],
                                  right[2] >= left[2], right[3] >= left[3]))


def _relate(first, second):
    a, b = first["box"], second["box"]
    if _inside(a, b):
        return [{"subject": first["id"], "relation": "inside_box", "object": second["id"]}]
    if _inside(b, a):
        return [{"subject": second["id"], "relation": "inside_box", "object": first["id"]}]
    overlap = _intersection(a, b)
    if overlap:
        return [{"subject": first["id"], "relation": "overlapping_box", "object": second["id"],
                 "overlap_pixels": overlap}]
    pairs = []
    for axis, lower, label in ((0, 2, "left_of"), (1, 3, "above")):
        if a[lower] <= b[axis]:
            pairs.append({"subject": first["id"], "relation": label, "object": second["id"]})
        elif b[lower] <= a[axis]:
            pairs.append({"subject": second["id"], "relation": label, "object": first["id"]})
    return pairs


def describe(image_data, *, light_ink=False, threshold=None, minimum_pixels=3, maximum_regions=32):
    image = _raster.decode(image_data)
    if image.width*image.height > MAX_SCENE_PIXELS:
        raise ValueError("Adegan terlalu besar.")
    if type(light_ink) is not bool:
        raise ValueError("Polaritas perlu boolean.")
    minimum = _integer(minimum_pixels, 1, MAX_SCENE_PIXELS, "Piksel minimum")
    maximum = _integer(maximum_regions, 1, MAX_REGIONS, "Jumlah wilayah maksimum")
    level = _otsu(image.pixels, image.maximum) if threshold is None else _integer(threshold, 0, image.maximum, "Ambang")
    mask = [] if level is None else [(value > level) if light_ink else (value <= level) for value in image.pixels]
    kept = []
    small = 0
    large = 0
    for box, count in _components(mask, image.width):
        if count < minimum:
            small += 1
            continue
        large += 1
        kept.append((box, count))
        if len(kept) > maximum:
            kept.sort(key=lambda value: (-value[1], value[0][1], value[0][0], value[0]))
            kept.pop()
    kept.sort(key=lambda value: (value[0][1], value[0][0], value[0]))
    if sum((box[2]-box[0])*(box[3]-box[1]) for box, _ in kept) > MAX_FEATURE_PIXELS:
        raise ValueError("Wilayah pengukuran melampaui batas.")
    regions = [{"id": f"region-{i}", **_features(image, mask, bbox, count)}
               for i, (bbox, count) in enumerate(kept, 1)]
    comparisons = [relation for i, first in enumerate(regions)
                   for second in regions[i+1:] for relation in _relate(first, second)]
    counted = defaultdict(int)
    for row in regions:
        counted[row["shape_hint"]] += 1
    return {"schema": "ace.perception-scene-regions.v1", "image_sha256": sha256(image_data).hexdigest(),
            "size": [image.width, image.height], "threshold": level, "light_ink": light_ink,
            "regions":regions, "relations": comparisons, "visible_shape_counts": dict(sorted(counted.items())),
            "omitted_small": small, "omitted_limit": large-len(regions)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--light-ink", action="store_true")
    parser.add_argument("--threshold", type=int)
    parser.add_argument("--minimum-pixels", type=int, default=3)
    parser.add_argument("--maximum-regions", type=int, default=32)
    args = parser.parse_args(argv)
    try:
        report = describe(_raster.read(args.image), light_ink=args.light_ink, threshold=args.threshold,
                          minimum_pixels=args.minimum_pixels, maximum_regions=args.maximum_regions)
        sys.stdout.buffer.write(_canonical(report) + b"\n")
    except (OSError, OverflowError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
