"""Animasi nilai bertanda dengan skala tetap, baseline nol, dan asal per keyframe."""
import argparse
from pathlib import Path
import sys

from ._contracts import (ContractError, canonical, checked, decode, entries,
                         identifier, integer, obj, read, schema, text)
from ._lettering import GLYPHS, stamp
from ._raster import blank
from ._story_video import box, frame_hash, write_movie
from .video_composer import video_size


def _row(keyframes, current, source_index):
    first, second = keyframes[source_index:source_index + 2]
    span = second["frame"] - first["frame"]
    elapsed = current - first["frame"]
    return [a * span + (b - a) * elapsed for a, b in zip(first["values"], second["values"], strict=True)], span


def animate_data(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.data-motion.v1", ("width", "height", "fps", "frames", "series", "keyframes"))
    w, h = video_size(plan["width"], plan["height"])
    fps = integer(plan["fps"], "FPS", 2, 24)
    count = integer(plan["frames"], "Jumlah frame", 2, 200)
    if w < 120 or h < 64 or w * h * count > 27_000_000:
        raise ContractError("Dimensi atau anggaran animasi angka tidak sah.")
    series = [identifier(value, "Seri") for value in entries(plan["series"], 12, 1)]
    if len(set(series)) != len(series):
        raise ContractError("ID seri duplikat.")
    slot = (w - 20) // len(series)
    if slot < 4 or any(len(key) * 6 - 1 > slot - 1 or any(char not in GLYPHS for char in key.upper()) for key in series):
        raise ContractError("Label seri terlalu panjang atau karakter label belum didukung.")
    previous = -1
    maximum = 0
    keyframes = []
    for record in entries(plan["keyframes"], 64, 2):
        obj(record, ("frame", "values", "source_ref"))
        index = integer(record["frame"], "Nomor keyframe", previous + 1, count - 1)
        obj(record["values"], series)
        values = [integer(record["values"][name], "Nilai seri", -10**9, 10**9) for name in series]
        maximum = max(maximum, *map(abs, values))
        keyframes.append({"frame": index, "values": values, "source_ref": text(record["source_ref"], "Pointer data")})
        previous = index
    if keyframes[0]["frame"] != 0 or keyframes[-1]["frame"] != count - 1:
        raise ContractError("Keyframe awal dan akhir wajib ada.")
    paper = blank(w, h, (22, 28, 42))
    baseline = (h - 16) // 2
    paper = box(paper, 6, baseline, w - 12, 1, (220, 226, 230))
    for index, name in enumerate(series):
        paper, _ = stamp(paper, name.upper(), 10 + index * slot, h - 10, 1, (220, 226, 230))
    span = min(baseline - 4, h - 17 - baseline)
    measurements = []

    def images():
        source_index = 0
        for index in range(count):
            if index > keyframes[source_index + 1]["frame"]:
                source_index += 1
            numerators, denominator = _row(keyframes, index, source_index)
            result = paper
            lengths = []
            for series_index, value in enumerate(numerators):
                size = abs(value) * span // (max(1, maximum) * denominator)
                start = baseline - size if value >= 0 else baseline + 1
                ink = (81, 189, 227) if value >= 0 else (236, 139, 81)
                result = box(result, 10 + series_index * slot, start, max(2, slot - 4), size, ink)
                lengths.append(size if value >= 0 else -size)
            measurements.append({"frame": index, "keyframes": [keyframes[source_index]["frame"],
                                  keyframes[source_index + 1]["frame"]], "interpolated_numerators": numerators,
                                  "denominator": denominator, "bar_lengths": lengths, "source_frame_sha256": frame_hash(result)})
            yield result

    output, report = write_movie(images(), w, h, fps)
    return output, {"schema": "ace.media.data-motion-receipt.v1", "plan_sha256": expected, "series": series,
                    "keyframes": keyframes, "fixed_absolute_max": maximum, "zero_baseline_y": baseline,
                    "measurement": measurements, **report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        raw, report = animate_data(decode(read(args.plan)), args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(raw)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
