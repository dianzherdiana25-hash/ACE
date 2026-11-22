"""Tempatkan motif musik pendek pada cue adegan dan sisakan jeda eksak."""
import argparse
from hashlib import sha256
from math import sin, tau
from pathlib import Path
import sys

from ._audio import Audio, sample_rate, wav
from ._contracts import (ContractError, canonical, checked, decode, entries, identifier,
                         integer, obj, read, schema, text)


INTERVALS = {"warm": (0, 4, 7, 12), "tense": (0, 1, 6, 8), "resolve": (7, 4, 2, 0)}


def _motif(intervals, key, frames, rate, strength):
    offsets = [index * frames // len(intervals) for index in range(len(intervals) + 1)]
    output = []
    for index, note in enumerate(intervals):
        frequency = 440 * 2 ** ((key + note - 69) / 12)
        width = offsets[index + 1] - offsets[index]
        attack = max(1, rate // 80)
        decay = max(1, rate // 25)
        for i in range(width):
            scale = min(i / attack, (width - 1 - i) / decay, 1)
            phase = tau * frequency * i / rate
            output.append(round(strength * scale * (0.85 * sin(phase) + 0.15 * sin(2 * phase))))
    return output


def score_scenes(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.scene-score.v1", ("rate", "duration_ms", "cues"))
    rate = sample_rate(plan["rate"])
    duration = integer(plan["duration_ms"], "Durasi", 80, 30000)
    frames = duration * rate // 1000
    output = [0] * frames
    timeline = []
    previous = 0
    used = set()
    for cue in entries(plan["cues"], 20, 1):
        obj(cue, ("id", "source_ref", "start_ms", "end_ms", "tonic", "mood", "peak"))
        key = identifier(cue["id"], "Motif")
        if key in used or cue["mood"] not in INTERVALS:
            raise ContractError("ID motif ganda atau suasana tidak terdaftar.")
        used.add(key)
        start = integer(cue["start_ms"], "Mulai cue", previous, duration - 80)
        end = integer(cue["end_ms"], "Akhir cue", start + 80, duration)
        first, last = start * rate // 1000, end * rate // 1000
        tonic = integer(cue["tonic"], "Nada pusat", 36, 72)
        intervals = INTERVALS[cue["mood"]]
        span = _motif(intervals, tonic, last - first, rate, integer(cue["peak"], "Gain motif", 500, 20_000))
        output[first:last] = span
        timeline.append({"id": key, "source_ref": text(cue["source_ref"], "Pointer adegan"),
                         "mood": cue["mood"], "midi_notes": [tonic + offset for offset in intervals],
                         "samples": [first, last], "measured_peak": max(map(abs, span))})
        previous = end
    audio = Audio(rate, 1, tuple(output))
    data = wav(audio)
    return data, {"schema": "ace.media.scene-score-receipt.v1", "plan_sha256": expected, "cues": timeline,
                  "audio": audio.receipt(), "wav_sha256": sha256(data).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        data, report = score_scenes(decode(read(args.plan)), args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
