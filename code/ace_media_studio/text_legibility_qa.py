"""Periksa kontras teks pada beberapa frame video yang benar-benar didekode."""
import argparse
from pathlib import Path
from statistics import median_low
import sys

from ._clip_edit import open_clip
from ._contracts import (ContractError, canonical, checked, decode, entries,
                         identifier, integer, obj, read, schema, text)
from .image_qa import _bounds, _luma


def _patch(image, box):
    x, y, width, height = _bounds(box, image)
    return median_low(_luma(image.at(col, row)) for row in range(y, y + height) for col in range(x, x + width))


def audit_text(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.legibility-plan.v1", ("source", "regions", "min_height_px", "min_contrast_milli", "max_sample_gap"))
    frames, fps, _ = open_clip(root, plan["source"])
    minimum_ratio = integer(plan["min_contrast_milli"], "Kontras minimum", 1000, 21000)
    height = integer(plan["min_height_px"], "Tinggi huruf minimum", 1, frames[0].height)
    spacing = integer(plan["max_sample_gap"], "Jarak maksimum sampel", 1, 120)
    audit = []
    seen = set()
    work = 0
    for item in entries(plan["regions"], 50, 1):
        obj(item, ("id", "source_ref", "first_frame", "end_frame", "glyph_height", "ink", "background", "samples"))
        key = identifier(item["id"], "Wilayah teks")
        if key in seen:
            raise ContractError("Wilayah teks ganda.")
        seen.add(key)
        begin = integer(item["first_frame"], "Awal isi", 0, len(frames) - 1)
        end = integer(item["end_frame"], "Akhir isi eksklusif", begin + 1, len(frames))
        glyph = integer(item["glyph_height"], "Tinggi huruf teranotasi", 1, frames[0].height)
        ink = _bounds(item["ink"], frames[0])
        background = _bounds(item["background"], frames[0])
        indices = [integer(value, "Frame sampel", begin, end - 1) for value in entries(item["samples"], 100, 1)]
        if indices != sorted(set(indices)):
            raise ContractError("Sampel wilayah perlu unik dan terurut.")
        work += (ink[2] * ink[3] + background[2] * background[3]) * len(indices)
        if work > 4_000_000:
            raise ContractError("Anggaran piksel audit teks terlampaui.")
        observations = []
        for index in indices:
            values = sorted((_patch(frames[index], list(ink)), _patch(frames[index], list(background))))
            contrast = (values[1] + 500) * 1000 // (values[0] + 500)
            observations.append({"frame": index, "time_ms": index * 1000 // fps, "contrast_milli": contrast,
                                 "pass": contrast >= minimum_ratio})
        gaps = [[a, b] for a, b in zip([begin, *indices], [*indices, end - 1], strict=True) if b - a > spacing]
        fail = (["sample_gap"] if gaps else []) + (["glyph_height"] if glyph < height else [])
        if any(not row["pass"] for row in observations):
            fail.append("contrast")
        audit.append({"id": key, "source_ref": text(item["source_ref"], "Pointer anotasi"), "glyph_height": glyph,
                      "samples": observations, "missed_ranges": gaps, "blocked_by": fail})
    return {"schema": "ace.media.legibility-receipt.v1", "plan_sha256": expected,
            "video_sha256": plan["source"]["sha256"], "scope": "annotated_text_regions",
            "regions": audit, "status": "hold" if any(row["blocked_by"] for row in audit) else "pass"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        receipt = audit_text(decode(read(args.plan)), args.expect_sha256, args.asset_root)
        sys.stdout.buffer.write(canonical(receipt) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(receipt["status"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
