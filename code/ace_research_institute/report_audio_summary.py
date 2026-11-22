"""Render ringkasan audio lokal dengan cue bukti dan narasi formant berbahasa Indonesia."""
import argparse
from array import array
from hashlib import sha256
from io import BytesIO
from math import sin, tau
from pathlib import Path
import random
import sys
import wave

from ._contracts import ResearchError, anchor, canonical, decode, identity, integer, obj, read, schema
from .executive_summarizer import summarize


VOWELS = {"a": (730, 1150, 2400), "i": (280, 2250, 2950), "u": (320, 900, 2250),
          "e": (480, 1950, 2600), "o": (460, 840, 2420)}
DIGITS = ("nol", "satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan", "sembilan")
UNIT_WORDS = {"fraction": "bagian", "s": "detik", "m": "meter", "g": "gram", "count": "unit",
              "lux": "luks", "celsius": "derajat celsius", "points": "poin"}
RATE = 8000


def _spoken_number(value):
    return " ".join(DIGITS[int(char)] if char.isascii() and char.isdigit() else {".": "koma", "-": "minus"}[char]
                    for char in value)


def _say(text_value, pitch, seed):
    rng = random.Random(seed)
    generated = []
    for char in text_value.lower():
        count = 800 if char in VOWELS else 430
        if char == " ":
            generated.extend([0] * 380)
            continue
        if char == ".":
            generated.extend([0] * 1600)
            continue
        formants = VOWELS.get(char, (380, 1380, 2250))
        harmonics = [(index * pitch, sum(1 / (1 + ((index * pitch - pole) / band)**2)
                                        for pole, band in zip(formants, (100, 162, 255), strict=True)) / index)
                     for index in range(1, 18)]
        for index in range(count):
            frame = index / RATE
            edge = min(1, index / 45, (count - 1 - index) / 65)
            if char in VOWELS or char in "mnlrwy":
                pressure = sum(weight * sin(tau * frequency * frame) for frequency, weight in harmonics)
            else:
                pressure = (rng.random() * 2 - 1) * 0.24 * (1 - index / count)
            generated.append(max(-22000, min(22000, round(11000 * edge * pressure))))
    return generated


def make_audio(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.audio-summary-plan.v1", ("report", "max_highlights", "pitch"))
    pointer = obj(plan["report"], ("path", "sha256"))
    maximum = integer(plan["max_highlights"], "Temuan narasi maksimum", 1, 8)
    pitch = integer(plan["pitch"], "Pitch sintetis", 95, 175)
    summary_plan = {"schema": "ace.institute.executive-summary-plan.v1", "report": pointer,
                    "max_points": maximum, "max_held": 1}
    facts = summarize(summary_plan, identity(summary_plan), root)
    rows = [{"line": "Ringkasan hasil riset.", "refs": [pointer], "kind": "intro"}]
    for item in facts["highlights"]:
        amount = item["amount"]
        unit = UNIT_WORDS.get(amount["unit"])
        value = amount["value"]
        if unit is None or any(char not in "0123456789.-" for char in value):
            raise ResearchError("Nilai atau satuan belum dapat dibacakan dengan kontrak audio.")
        rows.append({"line": f"Nilai terukur {_spoken_number(value)} {unit}.", "refs": item["evidence"], "kind": "measured"})
    for item in facts["named_gaps"]:
        rows.append({"line": "Masih ada temuan yang belum memiliki dukungan cukup.",
                     "refs": [item["source_ref"]], "kind": "evidence_gap"})
    pcm = array("h")
    for index, row in enumerate(rows, 1):
        start = len(pcm)
        pcm.extend(_say(row["line"], pitch, index))
        pcm.extend([0] * 1200)
        row["samples"] = [start, len(pcm)]
    if len(pcm) > RATE * 95:
        raise ResearchError("Durasi ringkasan melebihi anggaran.")
    with BytesIO() as destination:
        with wave.open(destination, "wb") as recording:
            recording.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
            if sys.byteorder != "little":
                pcm.byteswap()
            recording.writeframes(pcm.tobytes())
        data = destination.getvalue()
    return data, {"schema": "ace.institute.audio-summary.v1", "plan_sha256": expected, "report": pointer,
                  "scope": "rule_based_formants", "sample_rate": RATE, "frames": len(pcm), "timeline": rows,
                  "audio_sha256": sha256(data).hexdigest(), "summary_sha256": identity(facts)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        data, report = make_audio(decode(read(args.plan)), args.expect_sha256, args.root)
        with args.output.open("xb") as stream:
            stream.write(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, ArithmeticError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
