"""Jadikan artikel lokal sebagai video penjelasan berbasis kutipan terpilih dan baris sumber."""
import argparse
from hashlib import sha256
from pathlib import Path
import re
import sys

from ._contracts import (ContractError, canonical, checked, decode, digest,
                         entries, integer, read, schema, text)
from ._story_video import card, frame_hash, write_movie
from .video_composer import video_size


DEFAULT_COLORS = ((23, 33, 53), (224, 229, 240), (110, 221, 231))
WORD = re.compile(r"[^\W_]+", re.UNICODE)


def _paragraphs(raw):
    if len(raw) > 400_000:
        raise ContractError("Artikel tidak muat pada anggaran input.")
    parts = []
    first = 0
    listing = []
    for number, original in enumerate(raw.decode("utf-8").splitlines(), 1):
        line = original.strip()
        if line and not line.startswith("#"):
            if not listing:
                first = number
            listing.append(line)
        elif listing:
            parts.append((first, number - 1, " ".join(listing)))
            listing = []
    if listing:
        parts.append((first, number, " ".join(listing)))
    return parts


def _sentences(parts, desired):
    results = []
    for start, end, paragraph in parts:
        for fragment in re.split(r"(?<=[.!?])\s+", paragraph):
            terms = {term.casefold() for term in WORD.findall(fragment)}
            score = len(terms & desired)
            if score and 3 <= len(terms) <= 23 and len(fragment) <= 120:
                results.append((-score, start, end, fragment))
    return sorted(results)


def explain(raw, plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.explainer-plan.v1", ("article_sha256", "article_ref", "title", "keywords",
                                                 "max_cards", "width", "height", "fps", "frames_per_card"))
    anchor = digest(plan["article_sha256"])
    if sha256(raw).hexdigest() != anchor:
        raise ContractError("Artikel berbeda dari anchor sumber.")
    title = text(plan["title"], "Judul", 40)
    pointer = text(plan["article_ref"], "Pointer artikel")
    keywords = {value.casefold() for item in entries(plan["keywords"], 10, 1)
                for value in WORD.findall(text(item, "Istilah topik", 50))}
    maximum = integer(plan["max_cards"], "Jumlah kartu", 1, 8)
    fps = integer(plan["fps"], "FPS", 2, 12)
    hold = integer(plan["frames_per_card"], "Lama tayang kartu", fps, fps * 8)
    w, h = video_size(plan["width"], plan["height"])
    candidates = _sentences(_paragraphs(raw), keywords)
    selected = {}
    staged = []
    for _, first, last, quote in candidates:
        if quote in selected:
            continue
        try:
            frame = card(w, h, title, quote, colors=DEFAULT_COLORS)
        except ContractError:
            continue
        selected[quote] = (first, last, frame)
        if len(selected) >= maximum:
            break
    if not selected or len(selected) * hold > 450 or len(selected) * hold * w * h > 27_000_000:
        raise ContractError("Kartu kutipan yang muat belum tersedia atau melampaui anggaran.")
    ordered = sorted(selected.items(), key=lambda item: item[1][:2])
    for number, (quote, (first, last, frame)) in enumerate(ordered):
        staged.append((frame, {"source_ref": pointer, "lines": [first, last], "quote": quote,
                               "source_frame_sha256": frame_hash(frame), "first_frame": number * hold,
                               "end_frame_exclusive": (number + 1) * hold}))
    video, report = write_movie((frame for frame, _ in staged for _ in range(hold)), w, h, fps)
    return video, {"schema": "ace.media.explainer-receipt.v1", "plan_sha256": expected,
                   "article_sha256": anchor, "cards": [row for _, row in staged], **report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("article", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        data, report = explain(read(args.article, 400_000), decode(read(args.plan)), args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
