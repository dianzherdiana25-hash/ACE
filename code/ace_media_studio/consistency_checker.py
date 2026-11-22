"""Bandingkan palet dan landmark referensi dengan batch media melalui metrik terpisah."""
import argparse
from collections import Counter
from hashlib import sha256
from pathlib import Path
import sys

from ._assets import asset
from ._contracts import (ContractError, canonical, checked, decode, entries,
                         identifier, integer, obj, read, schema)
from ._raster import MAX_BYTES, raster


def _palette(image):
    return Counter((r // 32, g // 32, b // 32)
                   for r, g, b in zip(image.pixels[::3], image.pixels[1::3], image.pixels[2::3], strict=True))


def _overlap(first, current, expected_size, actual_size):
    bins = set(first) | set(current)
    common = sum(min(first[key] * actual_size, current[key] * expected_size) for key in bins)
    return common * 10000 // (expected_size * actual_size)


def _point(image, x, y):
    return image.at(x * (image.width - 1) // 10000, y * (image.height - 1) // 10000)


def compare(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.consistency-plan.v1", ("reference", "variants", "landmarks",
                                                  "palette_min_bp", "landmark_min_bp"))
    ref = obj(plan["reference"], ("path", "sha256"))
    reference = raster(asset(root, ref["path"], ref["sha256"], MAX_BYTES))
    palette = _palette(reference)
    bounds = []
    seen = set()
    palette_min = integer(plan["palette_min_bp"], "Ambang palet", 0, 10000)
    landmark_min = integer(plan["landmark_min_bp"], "Ambang landmark", 1, 10000)
    for rule in entries(plan["landmarks"], 40, 1):
        obj(rule, ("id", "x_bp", "y_bp", "tolerance"))
        key = identifier(rule["id"], "Landmark")
        if key in seen:
            raise ContractError("Landmark pembanding ganda.")
        seen.add(key)
        x = integer(rule["x_bp"], "Koordinat X", 0, 10000)
        y = integer(rule["y_bp"], "Koordinat Y", 0, 10000)
        bounds.append((key, x, y, _point(reference, x, y), integer(rule["tolerance"], "Toleransi", 0, 100)))
    batch = []
    seen.clear()
    for row in entries(plan["variants"], 40, 1):
        obj(row, ("id", "path", "sha256"))
        key = identifier(row["id"], "Varian")
        if key in seen:
            raise ContractError("Varian pembanding ganda.")
        seen.add(key)
        raw = asset(root, row["path"], row["sha256"], MAX_BYTES)
        image = raster(raw)
        styles = _overlap(palette, _palette(image), reference.width * reference.height, image.width * image.height)
        checks = []
        for label, x, y, color, tolerance in bounds:
            measured = _point(image, x, y)
            delta = max(abs(a - b) for a, b in zip(color, measured, strict=True))
            checks.append({"id": label, "difference": delta, "pass": delta <= tolerance})
        landmarks = sum(check["pass"] for check in checks) * 10000 // len(checks)
        batch.append({"id": key, "sha256": sha256(raw).hexdigest(), "palette_overlap_bp": styles,
                      "landmark_match_bp": landmarks, "landmarks": checks,
                      "pass": styles >= palette_min and landmarks >= landmark_min})
    return {"schema": "ace.media.consistency-report.v1", "plan_sha256": expected, "reference_sha256": ref["sha256"],
            "variants": batch, "pass": all(variant["pass"] for variant in batch)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("root", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = compare(decode(read(args.plan)), args.expect_sha256, args.root)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(not report["pass"])


if __name__ == "__main__":
    raise SystemExit(main())
