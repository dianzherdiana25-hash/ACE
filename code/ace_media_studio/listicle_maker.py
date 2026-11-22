"""Render daftar hitung mundur dengan urutan eksplisit dan penanda waktunya."""
import argparse
from pathlib import Path
import sys

from ._contracts import (ContractError, canonical, checked, decode, entries, identifier,
                         integer, obj, read, schema, text)
from ._story_video import card, frame_hash, write_movie
from .explainer_maker import DEFAULT_COLORS
from .video_composer import video_size


def listicle(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.listicle-plan.v1", ("style", "entries", "width", "height", "fps"))
    if plan["style"] not in ("countdown", "ordered"):
        raise ContractError("Gaya daftar perlu countdown atau ordered.")
    w, h = video_size(plan["width"], plan["height"])
    fps = integer(plan["fps"], "FPS", 2, 12)
    items = {}
    seen = set()
    source = entries(plan["entries"], 20, 2)
    for row in source:
        obj(row, ("id", "rank", "title", "note", "source_ref", "seconds"))
        key = identifier(row["id"], "ID item")
        rank = integer(row["rank"], "Peringkat", 1, len(source))
        if rank in items or key in seen:
            raise ContractError("Peringkat atau ID item duplikat.")
        seen.add(key)
        items[rank] = {"id": key, "rank": rank, "title": text(row["title"], "Judul item", 40),
                       "note": text(row["note"], "Catatan item", 100), "source_ref": text(row["source_ref"], "Pointer item"),
                       "frames": integer(row["seconds"], "Durasi item", 1, 10) * fps}
    indices = sorted(items, reverse=plan["style"] == "countdown")
    timeline = []
    cursor = 0
    for index, rank in enumerate(indices):
        item = items[rank]
        start, cursor = cursor, cursor + item["frames"]
        entry = f"{rank}. {item['title']}"
        if cursor > 450 or cursor * w * h > 27_000_000:
            raise ContractError("Anggaran frame daftar terlampaui.")
        first = card(w, h, entry, item["note"], colors=DEFAULT_COLORS, progress=w * (index + 1) // len(items))
        timeline.append((first, {**item, "start_frame": start, "end_frame_exclusive": cursor,
                                 "source_frame_sha256": frame_hash(first)}))
    movie, report = write_movie((frame for frame, item in timeline for _ in range(item["frames"])), w, h, fps)
    return movie, {"schema": "ace.media.listicle.v1", "plan_sha256": expected, "style": plan["style"],
                   "rank_order": indices, "sections": [item for _, item in timeline], **report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        raw, report = listicle(decode(read(args.plan)), args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(raw)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
