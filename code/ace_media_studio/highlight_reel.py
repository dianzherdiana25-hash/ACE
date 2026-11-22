"""Cari jendela paling aktif secara visual dan rakit ulang sorotan dengan urutan sumber."""
import argparse
from pathlib import Path
import sys

from ._clip_edit import cut_audio, open_clip
from ._contracts import ContractError, canonical, checked, decode, integer, read, schema
from ._story_video import write_movie
from .media_compressor import scale_frame


def _motion(frames):
    downsampled = [scale_frame(frame, 16, 12).pixels for frame in frames]
    return [sum(abs(a - b) for a, b in zip(first, second, strict=True))
            for first, second in zip(downsampled, downsampled[1:])]


def highlight(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.highlight-plan.v1", ("source", "window_frames", "clips", "separation_frames"))
    frames, fps, audio = open_clip(root, plan["source"])
    window = integer(plan["window_frames"], "Frame per sorotan", 2, len(frames))
    clips = integer(plan["clips"], "Jumlah sorotan", 1, 12)
    distance = integer(plan["separation_frames"], "Jarak antar sorotan", 0, len(frames))
    activity = _motion(frames)
    sums = [0]
    for value in activity:
        sums.append(sums[-1] + value)
    ranked = sorted(((sums[start + window - 1] - sums[start], start, start + window)
                     for start in range(len(frames) - window + 1)), key=lambda row: (-row[0], row[1]))
    chosen = []
    for score, start, end in ranked:
        if all(hi + distance <= start or end + distance <= lo for _, lo, hi in chosen):
            chosen.append((score, start, end))
        if len(chosen) == clips:
            break
    if len(chosen) != clips or not any(score for score, _, _ in chosen):
        raise ContractError("Jendela sorotan belum tersedia dengan anggaran dan aktivitas itu.")
    chosen.sort(key=lambda row: row[1])
    ranges = [(start, end) for _, start, end in chosen]
    output, report = write_movie((frame for start, end in ranges for frame in frames[start:end]),
                                 frames[0].width, frames[0].height, fps, cut_audio(audio, fps, ranges))
    selections = [{"source_frames": [start, end], "activity": score,
                   "output_frames": [index * window, (index + 1) * window]}
                  for index, (score, start, end) in enumerate(chosen)]
    return output, {"schema": "ace.media.highlight-receipt.v1", "plan_sha256": expected,
                    "source_sha256": plan["source"]["sha256"], "method": "absolute_rgb_change_16x12",
                    "selections": selections, **report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        raw, report = highlight(decode(read(args.plan)), args.expect_sha256, args.asset_root)
        with args.output.open("xb") as stream:
            stream.write(raw)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
