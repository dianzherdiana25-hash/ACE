"""Audit kemiripan teknis terhadap pustaka lokal dengan hash byte, struktur, dan warna."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._assets import asset
from ._contracts import (ContractError, canonical, checked, decode, entries,
                         identifier, integer, obj, read, schema, text)
from ._raster import MAX_BYTES, raster
from .media_compressor import scale_frame


def _signature(image):
    tiny = scale_frame(image, 9, 8)
    luma = [(2126 * red + 7152 * green + 722 * blue) // 10000
            for red, green, blue in zip(tiny.pixels[::3], tiny.pixels[1::3], tiny.pixels[2::3], strict=True)]
    structure = 0
    for y in range(8):
        for x in range(8):
            start = y * 9 + x
            structure = (structure << 1) | (luma[start] < luma[start + 1])
    means = tuple(sum(tiny.pixels[channel::3]) // 72 for channel in range(3))
    return structure, means


def check_originality(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.originality-plan.v1", ("candidate", "library", "max_hamming", "max_color_delta"))
    ref = obj(plan["candidate"], ("path", "sha256"))
    candidate = asset(root, ref["path"], ref["sha256"], MAX_BYTES)
    bits, rgb = _signature(raster(candidate))
    hamming_cap = integer(plan["max_hamming"], "Ambang Hamming", 0, 64)
    color_cap = integer(plan["max_color_delta"], "Ambang warna RGB", 0, 255)
    indexed = set()
    rows = []
    for row in entries(plan["library"], 100, 1):
        obj(row, ("id", "path", "sha256", "source_ref"))
        key = identifier(row["id"], "Aset perpustakaan")
        if key in indexed:
            raise ContractError("ID pustaka ganda.")
        source = text(row["source_ref"], "Pointer karya rujukan")
        raw = asset(root, row["path"], row["sha256"], MAX_BYTES)
        other, color = _signature(raster(raw))
        hamming = (bits ^ other).bit_count()
        color_delta = max(abs(a - b) for a, b in zip(rgb, color, strict=True))
        exact = row["sha256"] == ref["sha256"]
        relation = "exact_bytes" if exact else ("possible_near_duplicate" if
                                                hamming <= hamming_cap and color_delta <= color_cap else "distant")
        indexed.add(key)
        rows.append({"id": key, "source_ref": source, "sha256": sha256(raw).hexdigest(),
                     "relation": relation, "dhash_distance": hamming, "rgb_mean_distance": color_delta})
    order = {"exact_bytes": 0, "possible_near_duplicate": 1, "distant": 2}
    rows.sort(key=lambda row: (order[row["relation"]], row["dhash_distance"], row["rgb_mean_distance"], row["id"]))
    return {"schema": "ace.media.originality-receipt.v1", "plan_sha256": expected, "candidate_sha256": ref["sha256"],
            "scope": "technical_similarity_to_pinned_library", "compared": len(rows), "rows": rows,
            "status": "review" if any(row["relation"] != "distant" for row in rows) else "no_local_match"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = check_originality(decode(read(args.plan)), args.expect_sha256, args.asset_root)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report["status"] == "review")


if __name__ == "__main__":
    raise SystemExit(main())
