"""Catat gejala forensik raster yang dapat diukur dan dibandingkan.

Seam kisi, pengulangan blok bertekstur, dan perbedaan terhadap sumber
tertambat diberi statistik. Raster tertentu dapat menimbulkan gejala
yang sama secara alami. Kesimpulan asal atau generasi tetap unknown
karena statistik ini tidak membuktikan proses pembuatannya.
"""
import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import sys

from . import _raster, _vision
from .audio_pipeline import _canonical, _integer
from .perceptual_memory import _digest


MAX_PIXELS = 1_200_000


def _q(value):
    return {"numerator": value.numerator, "denominator": value.denominator} if value is not None else None


def _seam(values, width, height, size, limit):
    by_axis = []
    for name, offsets, count, stride, step in (("x", width, height, width, 1), ("y", height, width, 1, width)):
        amounts = [0]*size
        samples = [0]*size
        for index in range(count):
            base = index*stride
            for offset in range(1, offsets):
                pos = base + offset*step
                amounts[offset%size] += abs(values[pos]-values[pos-step])
                samples[offset%size] += 1
        phases = [Fraction(s, n) if n else None for s, n in zip(amounts, samples, strict=True)]
        supported = [value for value in phases[1:] if value is not None]
        background = sum(supported, Fraction(0))/len(supported) if supported else None
        strength = phases[0]-background if background is not None and phases[0] is not None else None
        by_axis.append({"axis": name, "phase_means": [_q(value) for value in phases], "phase_samples": samples,
                        "boundary_minus_other_mean": _q(strength), "flagged": strength is not None and strength >= limit})
    return by_axis


def _duplicates(values, width, height, size, minimum_range, maximum_examples):
    blocks = Counter()
    at = {}
    considered = 0
    for y in range(0, height-size+1, size):
        for x in range(0, width-size+1, size):
            tile = b"".join(values[py*width+x:py*width+x+size] for py in range(y, y+size))
            if max(tile)-min(tile) < minimum_range:
                continue
            considered += 1
            key = sha256(tile).hexdigest()
            blocks[key] += 1
            least = at.setdefault(key, [])
            if len(least) < 3:
                least.append([x, y, x+size, y+size])
    repeat = sorted((-freq, digest) for digest, freq in blocks.items() if freq > 1)
    return {"textured_tiles": considered, "repeat_groups": len(repeat),
            "repeated_beyond_first": sum(-size-1 for size, _ in repeat),
            "examples": [{"tile_sha256": digest, "count": -size, "boxes": at[digest]}
                         for size, digest in repeat[:maximum_examples]]}


def inspect(image_data, *, block=8, seam_limit=12, minimum_tile_range=25, maximum_examples=20,
            reference=None, reference_sha256=None):
    image = _raster.decode(image_data)
    size = _integer(block, 2, 32, "Blok")
    limit = _integer(seam_limit, 1, 255, "Ambang batas seam")
    contrast = _integer(minimum_tile_range, 1, 255, "Rentang tekstur")
    cap = _integer(maximum_examples, 1, 100, "Jumlah contoh")
    if image.width*image.height > MAX_PIXELS:
        raise ValueError("Raster forensik terlalu besar.")
    values = _vision.normalized(image)
    reference_summary = None
    if reference is not None:
        key = sha256(reference).hexdigest()
        if key != _digest(reference_sha256):
            raise ValueError("Raster rujukan berbeda dari anchor.")
        prior = _raster.decode(reference)
        if (prior.width, prior.height) != (image.width, image.height):
            raise ValueError("Rujukan harus berukuran sama.")
        reference_pixels = _vision.normalized(prior)
        difference = [abs(a-b) for a, b in zip(values, reference_pixels, strict=True)]
        reference_summary = {"sha256": key, "changed_pixels": sum(item > 0 for item in difference),
                             "mean_absolute_difference": _q(Fraction(sum(difference), len(difference)))}
    elif reference_sha256 is not None:
        raise ValueError("Anchor rujukan perlu berkas rujukan.")
    seams = _seam(values, image.width, image.height, size, limit)
    repeats = _duplicates(values, image.width, image.height, size, contrast, cap)
    return {"schema": "ace.perception-media-forensics.v1", "image_sha256": sha256(image_data).hexdigest(),
            "size": [image.width, image.height], "provenance": "unknown", "block_size": size, "seam_limit": limit,
            "minimum_tile_range": contrast, "quantization_levels_8bit": len(set(values)),
            "saturated_pixels": sum(value in (0, 255) for value in values), "seams": seams,
            "repetition": repeats, "reference_comparison": reference_summary,
            "findings": [*({"kind": "grid_seam", "axis": row["axis"]} for row in seams if row["flagged"]),
                         *([{"kind": "repeated_textured_tiles"}] if repeats["repeat_groups"] else [])]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--block", type=int, default=8)
    parser.add_argument("--seam-limit", type=int, default=12)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--expect-reference-sha256")
    args = parser.parse_args(argv)
    try:
        product = inspect(_raster.read(args.image), block=args.block, seam_limit=args.seam_limit,
                          reference=_raster.read(args.reference) if args.reference else None,
                          reference_sha256=args.expect_reference_sha256)
        sys.stdout.buffer.write(_canonical(product) + b"\n")
    except (OSError, OverflowError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
