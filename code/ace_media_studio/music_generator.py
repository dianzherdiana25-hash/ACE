"""Buat musik latar sederhana dari partitur terstruktur dan ukur setiap bar."""
import argparse
from hashlib import sha256
from math import exp, sin, tau
from pathlib import Path
from random import Random
import sys

from ._audio import Audio, clamp, sample_rate, wav
from ._contracts import (ContractError, canonical, checked, decode, entries, identifier,
                         integer, obj, read, schema, text)


TUNINGS = {"major": (0, 2, 4, 5, 7, 9, 11), "minor": (0, 2, 3, 5, 7, 8, 10)}
PULSES = {"quarter": (0, 2, 4, 6), "half": (0, 4), "alternating": (0, 3, 4, 7)}


def _shape(note, frame, total, rate):
    phase = tau * (440 * 2 ** ((note - 69) / 12)) * frame / rate
    envelope = min(1, frame / max(1, rate // 100), (total - frame) / max(1, rate // 15))
    return envelope * (0.77 * sin(phase) + 0.18 * sin(2 * phase) + 0.05 * sin(3 * phase))


def _note(output, begin, end, rate, pitch, gain):
    for index in range(begin, end):
        output[index] += round(gain * _shape(pitch, index - begin, end - begin, rate))


def _pulse(output, begin, end, rate, gain, generator):
    span = min(end - begin, rate // 14)
    phase = 0.0
    for index in range(span):
        phase += tau * (48 + 36 * exp(-5 * index / max(1, span))) / rate
        carrier = 0.88 * sin(phase) + 0.12 * generator.uniform(-1, 1)
        output[begin + index] += round(carrier * gain * exp(-6 * index / max(1, span)))


def generate_music(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.music-plan.v1", ("id", "source_ref", "rate", "bpm", "tonic", "mode",
                                             "progression", "bars", "rhythm", "seed", "headroom"))
    title = identifier(plan["id"], "Karya")
    source = text(plan["source_ref"], "Pointer partitur")
    rate = sample_rate(plan["rate"])
    bpm = integer(plan["bpm"], "Tempo", 55, 200)
    root = integer(plan["tonic"], "Nada MIDI dasar", 36, 65)
    bars = integer(plan["bars"], "Bar", 1, 20)
    peak_limit = integer(plan["headroom"], "Headroom", 300, 30_000)
    if plan["mode"] not in TUNINGS or plan["rhythm"] not in PULSES:
        raise ContractError("Mode atau pola ritme tidak didukung.")
    scale = TUNINGS[plan["mode"]]
    parts = []
    for row in entries(plan["progression"], 20, 1):
        obj(row, ("degree", "transpose", "accent"))
        parts.append((integer(row["degree"], "Derajat akor", 1, 7) - 1,
                      integer(row["transpose"], "Transposisi", -12, 12),
                      integer(row["accent"], "Aksen gain", 200, 1000)))
    if bars % len(parts):
        raise ContractError("Progresi perlu membagi panjang bar secara utuh.")
    seed = integer(plan["seed"], "Seed", 0, 2**63 - 1)
    random = Random(seed)
    edges = [(beat * 30 * rate + bpm // 2) // bpm for beat in range(bars * 8 + 1)]
    if edges[-1] > rate * 60:
        raise ContractError("Musik melampaui satu menit.")
    mix = [0] * edges[-1]
    events = []
    for bar in range(bars):
        degree, transposed, accent = parts[bar % len(parts)]
        offset = bar * 8
        chord = [root + transposed + scale[index % 7] + 12 * (index // 7)
                 for index in (degree, degree + 2, degree + 4)]
        _note(mix, edges[offset], edges[offset + 8], rate, chord[0] - 12, 6 * accent)
        for index in range(8):
            pitch = chord[(index + bar) % 3] + (12 if index >= 4 else 0)
            _note(mix, edges[offset + index], edges[offset + index + 1], rate, pitch, 4 * accent)
        for pulse in PULSES[plan["rhythm"]]:
            _pulse(mix, edges[offset + pulse], edges[offset + pulse + 1], rate, 5 * accent, random)
        events.append({"bar": bar + 1, "start_frame": edges[offset], "end_frame_exclusive": edges[offset + 8],
                       "notes_midi": chord, "beat_offsets": list(PULSES[plan["rhythm"]])})
    peak = max(map(abs, mix))
    denominator = max(peak_limit, peak)
    audio = Audio(rate, 1, tuple(clamp(sample * peak_limit // denominator) for sample in mix))
    data = wav(audio)
    return data, {"schema": "ace.media.music-receipt.v1", "plan_sha256": expected, "id": title, "bpm": bpm,
                  "source_ref": source, "bars": events, "wav_sha256": sha256(data).hexdigest(),
                  "peak_before": peak, "recipe": "seeded_harmonic_arp_and_pulse", **audio.receipt()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        data, report = generate_music(decode(read(args.plan)), args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
