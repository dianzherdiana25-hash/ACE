"""Ambil potongan per babak dan rakit teaser pendek dengan kartu penutup."""
import argparse
from pathlib import Path
import sys

from ._clip_edit import open_clip
from ._contracts import (ContractError, canonical, checked, decode, entries,
                         identifier, integer, obj, read, schema, text)
from ._story_video import card, frame_hash, write_movie
from .explainer_maker import DEFAULT_COLORS


def teaser(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.teaser-plan.v1", ("source", "acts", "frames_per_act", "end_card"))
    frames, fps, _ = open_clip(root, plan["source"])
    hold = integer(plan["frames_per_act"], "Tayang per babak", 1, 5 * fps)
    end = obj(plan["end_card"], ("title", "note", "source_ref", "frames"))
    tail = integer(end["frames"], "Durasi penutup", 1, 5 * fps)
    selected = []
    manifest = []
    seen = set()
    previous = 0
    for row in entries(plan["acts"], 8, 2):
        obj(row, ("id", "start", "end", "anchor", "source_ref"))
        key = identifier(row["id"], "Babak")
        if key in seen:
            raise ContractError("ID babak duplikat.")
        seen.add(key)
        first = integer(row["start"], "Frame pertama babak", previous, len(frames) - hold)
        last = integer(row["end"], "Frame akhir babak", first + hold, len(frames))
        anchor = integer(row["anchor"], "Anchor babak", first, last - 1)
        start = max(first, min(last - hold, anchor - hold // 2))
        pointer = text(row["source_ref"], "Pointer babak")
        manifest.append({"id": key, "source_ref": pointer, "source_frames": [start, start + hold],
                         "output_frames": [len(selected), len(selected) + hold]})
        selected.extend(frames[start:start + hold])
        previous = last
    w, h = frames[0].width, frames[0].height
    if (len(selected) + tail) > 450 or (len(selected) + tail) * w * h > 27_000_000:
        raise ContractError("Anggaran frame teaser terlampaui.")
    closing = card(w, h, text(end["title"], "Judul penutup"), text(end["note"], "Teks penutup"),
                   colors=DEFAULT_COLORS)
    data, report = write_movie([*selected, *[closing] * tail], w, h, fps)
    return data, {"schema": "ace.media.teaser-receipt.v1", "plan_sha256": expected, "source_sha256": plan["source"]["sha256"],
                  "audio_policy": "silent_teaser", "acts": manifest, "end_card": {"first_frame": len(selected),
                  "source_ref": text(end["source_ref"], "Pointer penutup"), "source_frame_sha256": frame_hash(closing)}, **report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        data, report = teaser(decode(read(args.plan)), args.expect_sha256, args.asset_root)
        with args.output.open("xb") as stream:
            stream.write(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
