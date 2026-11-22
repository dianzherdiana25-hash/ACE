"""Sintesis efek foley deterministik dari deskripsi terkontrol dan batas amplitudo."""
import argparse
from hashlib import sha256
from math import exp, sin, tau
from pathlib import Path
from random import Random
import sys

from ._audio import Audio, sample_rate, wav
from ._contracts import ContractError, canonical, checked, decode, integer, read, schema, text


RECIPES = {
    "gerimis": ((270, 370), 76, 88),
    "ketuk kayu": ((130, 211), 54, 9),
    "lonceng kaca": ((640, 1187), 10, 24),
    "hembusan": ((92, 147), 86, 65),
}


def synthesize_effect(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.effect-plan.v1", ("description", "source_ref", "rate", "duration_ms", "peak", "seed"))
    description = " ".join(text(plan["description"], "Deskripsi efek", 90).casefold().split())
    if description not in RECIPES:
        raise ContractError("Deskripsi efek belum ditopang resep foley.")
    source = text(plan["source_ref"], "Pointer adegan")
    rate = sample_rate(plan["rate"])
    duration = integer(plan["duration_ms"], "Durasi efek", 50, 5000)
    limit = integer(plan["peak"], "Puncak", 300, 29_000)
    seed = integer(plan["seed"], "Seed efek", 0, 2**63 - 1)
    frequencies, noise, decay = RECIPES[description]
    random = Random(seed)
    output = []
    low = 0.0
    frames = duration * rate // 1000
    for index in range(frames):
        time = index / rate
        fraction = index / frames
        low = (28 * low + random.uniform(-1, 1)) / 29
        harmonic = (sin(tau * frequencies[0] * time) + 0.36 * sin(tau * frequencies[1] * time)) / 1.36
        mixed = ((100 - noise) * harmonic + noise * (3 * low if noise > 60 else low)) / 100
        contour = min(index / max(1, rate // 100), (frames - 1 - index) / max(1, rate // 25), 1)
        envelope = contour * exp(-100 * fraction / decay)
        output.append(round(mixed * envelope * 30000))
    measured = max(map(abs, output))
    if not measured:
        raise ContractError("Resep tidak menghasilkan sinyal.")
    audio = Audio(rate, 1, tuple(round(value * limit / measured) for value in output))
    data = wav(audio)
    return data, {"schema": "ace.media.effect-receipt.v1", "plan_sha256": expected, "description": description,
                  "source_ref": source, "carrier_hz": list(frequencies), "wav_sha256": sha256(data).hexdigest(),
                  **audio.receipt()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        data, report = synthesize_effect(decode(read(args.plan)), args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
