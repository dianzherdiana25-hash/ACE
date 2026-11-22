"""Ekstrak shot dan thumbnail representatif dari video lokal dengan ambang perubahan RGB."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._clip_edit import open_clip
from ._contracts import ContractError, canonical, checked, decode, integer, read, schema
from ._raster import png
from .media_compressor import scale_frame


def _distance(first, second):
    return sum(abs(a - b) for a, b in zip(first, second, strict=True))


def extract_storyboard(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.reverse-storyboard.v1", ("source", "cut_threshold", "min_shot_frames", "max_shots"))
    frames, fps, _ = open_clip(root, plan["source"])
    threshold = integer(plan["cut_threshold"], "Ambang perubahan rata-rata", 1, 255)
    minimum = integer(plan["min_shot_frames"], "Frame minimum per shot", 1, len(frames))
    limit = integer(plan["max_shots"], "Shot maksimum", 1, 50)
    small = [scale_frame(frame, 16, 12).pixels for frame in frames]
    cut = [_distance(first, second) for first, second in zip(small, small[1:])]
    boundaries = [0]
    for index, score in enumerate(cut, 1):
        if score >= threshold * len(small[0]) and index - boundaries[-1] >= minimum and len(frames) - index >= minimum:
            boundaries.append(index)
        if len(boundaries) > limit:
            raise ContractError("Potongan video melampaui jumlah shot yang diminta.")
    output = {}
    shots = []
    for number, (start, end) in enumerate(zip(boundaries, [*boundaries[1:], len(frames)], strict=True), 1):
        count = end - start
        averages = bytes(sum(row[channel] for row in small[start:end]) // count for channel in range(len(small[0])))
        representative = min(range(start, end), key=lambda i: (_distance(small[i], averages), abs(2 * i - start - end + 1), i))
        frame = frames[representative]
        width = min(frame.width, 180)
        height = max(1, frame.height * width // frame.width)
        data = png(scale_frame(frame, width, height))
        name = f"shot_{number:03}.png"
        output[name] = data
        shots.append({"index": number, "range_frames": [start, end], "range_ms": [1000 * start // fps, 1000 * end // fps],
                      "representative_frame": representative, "file": name, "thumbnail_sha256": sha256(data).hexdigest(),
                      "cut_delta_milli": cut[start - 1] * 1000 // len(small[0]) if start else None})
    return output, {"schema": "ace.media.reverse-storyboard-receipt.v1", "plan_sha256": expected,
                     "source_sha256": plan["source"]["sha256"], "frames": len(frames), "fps": fps,
                     "method": "consecutive_rgb_cut_and_mean_representative", "shots": shots}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, report = extract_storyboard(decode(read(args.plan)), args.expect_sha256, args.asset_root)
        args.output.mkdir()
        for name, data in files.items():
            (args.output / name).write_bytes(data)
        (args.output / "storyboard.json").write_bytes(canonical(report) + b"\n")
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
