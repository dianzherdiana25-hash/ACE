"""Bangun sampul musim dengan pita identitas tetap dan variasi episode yang bisa diperiksa."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._contracts import (ContractError, canonical, checked, decode, entries,
                         identifier, identity, integer, obj, read, schema, text)
from ._raster import png, raster
from ._story_video import box
from .cover_maker import make_cover


def make_series(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.series-cover.v1", ("series", "season", "source_ref", "style", "episodes"))
    name = identifier(plan["series"], "Seri")
    season = integer(plan["season"], "Musim", 1, 999)
    source = text(plan["source_ref"], "Pointer bible visual")
    style = obj(plan["style"], ("background", "accent", "foreground", "width", "height", "minimum_contrast_milli"))
    indexed = {}
    episodes = set()
    signatures = set()
    pictures = {}
    for item in entries(plan["episodes"], 30, 1):
        obj(item, ("episode", "id", "title", "source_ref"))
        episode = integer(item["episode"], "Episode", 1, 999)
        key = identifier(item["id"], "ID sampul")
        if episode in episodes or key in indexed:
            raise ContractError("Nomor episode atau ID sampul ganda.")
        episodes.add(episode)
        origin = text(item["source_ref"], "Pointer judul episode")
        base = {"schema": "ace.media.cover-plan.v1", "id": key, "source_ref": origin,
                "title": item["title"], **style}
        payload, qa = make_cover(base, identity(base))
        if qa["status"] != "pass":
            raise ContractError(f"Kontras sampul episode {episode} tidak lulus.")
        # Place a compact binary episode mark inside the accent band without touching title pixels.
        img = raster(payload)
        start = 5
        y = img.height - 4
        for bit in range(10):
            if episode & (1 << bit):
                img = box(img, start + bit * 4, y, 3, 2, (18, 21, 26))
        # Signature uses the bottom scanline below the episode mark.
        signal = img.pixels[(img.height - 1) * img.width * 3:]
        signature = sha256(signal).hexdigest()
        signatures.add(signature)
        result = png(img)
        indexed[key] = {"id": key, "episode": episode, "source_ref": origin, "title": item["title"],
                        "cover_sha256": sha256(result).hexdigest(), "series_band_sha256": signature,
                        "contrast_min_milli": min(region["contrast_milli"] for region in qa["measurements"]["text_regions"])}
        pictures[f"s{season:03}_e{episode:03}_{key}.png"] = result
    if len(signatures) != 1 or len({row["cover_sha256"] for row in indexed.values()}) != len(indexed):
        raise ContractError("Identitas seri berubah atau hasil sampul ganda.")
    report = {"schema": "ace.media.series-cover-receipt.v1", "plan_sha256": expected, "series": name,
              "season": season, "source_ref": source, "style_sha256": identity(style),
              "covers": sorted(indexed.values(), key=lambda row: row["episode"])}
    return pictures, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        results, report = make_series(decode(read(args.plan)), args.expect_sha256)
        args.output.mkdir()
        for name, raw in results.items():
            (args.output / name).write_bytes(raw)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
