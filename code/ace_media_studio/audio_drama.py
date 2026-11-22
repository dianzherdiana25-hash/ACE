"""Rakit episode drama multikarakter dengan cue, pemeriksaan efek, dan rantai keluaran."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._assets import asset
from ._audio import MAX_WAV, align, parse_wav, sample_rate, wav
from ._contracts import (ContractError, canonical, checked, decode, digest, entries,
                         identifier, identity, integer, obj, read, schema, text)
from .audio_mixer import mix_tracks
from .voice_generator import synthesize


def _track(key, kind, start, gain):
    return {"id": key, "role": kind, "start_ms": start, "gain_milli": gain,
            "pan": 0, "fade_in_ms": 0, "fade_out_ms": 0}


def produce_drama(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.drama-plan.v1", ("series", "episode", "predecessor", "rate", "cast", "sequence"))
    series = identifier(plan["series"], "Seri")
    episode = integer(plan["episode"], "Episode", 1, 1000)
    predecessor = plan["predecessor"]
    if episode == 1:
        if predecessor is not None:
            raise ContractError("Episode pertama tidak memiliki predecessor.")
    else:
        digest(predecessor)
    rate = sample_rate(plan["rate"])
    cast = {}
    for profile in entries(plan["cast"], 10, 1):
        obj(profile, ("id", "pitch_hz", "speed_milli", "peak"))
        character = identifier(profile["id"], "Karakter")
        if character in cast:
            raise ContractError("Karakter ganda.")
        cast[character] = {key: integer(profile[key], key, low, high) for key, low, high in (
            ("pitch_hz", 85, 260), ("speed_milli", 650, 1650), ("peak", 100, 28000))}
    clock = 0
    previous = None
    has_dialogue = False
    tracks = []
    cue = []
    ids = set()
    for offset, row in enumerate(entries(plan["sequence"], 36, 1)):
        common = ("id", "kind", "source_ref", "after_ms")
        kind = row.get("kind") if isinstance(row, dict) else None
        if kind == "line":
            obj(row, (*common, "character", "text"))
            character = identifier(row["character"], "Karakter")
            if character not in cast:
                raise ContractError("Karakter dialog belum terdaftar.")
            line = {"schema": "ace.media.voice-plan.v1", "text": row["text"], "language": "id",
                    "source_ref": row["source_ref"], "rate": rate, "seed": 1000 * episode + offset, **cast[character]}
            signal, proof = synthesize(line, identity(line))
            clip = parse_wav(signal)
            has_dialogue = True
            role = "speech"
        elif kind == "effect":
            obj(row, (*common, "path", "sha256", "license_ref", "overlap_ms"))
            signal = asset(root, row["path"], row["sha256"], MAX_WAV)
            clip = align(parse_wav(signal), rate, 1)
            proof = {"wav_sha256": row["sha256"], "license_ref": text(row["license_ref"], "Pointer izin efek")}
            character = None
            role = "effect"
        else:
            raise ContractError("Jenis cue drama tidak didukung.")
        key = identifier(row["id"], "Cue")
        if key in ids or not clip.frames:
            raise ContractError("Cue ganda atau audio kosong.")
        ids.add(key)
        duration = (clip.frames * 1000 + rate - 1) // rate
        overlap = integer(row["overlap_ms"], "Overlap efek", 0, min(2000, previous["duration_ms"] if previous else 0)) if kind == "effect" else 0
        start = (previous["end_ms"] - overlap) if overlap else clock
        end = start + duration
        clock = max(clock, end + integer(row["after_ms"], "Jeda", 0, 5000))
        if clock > 60_000:
            raise ContractError("Durasi drama melebihi satu menit.")
        tracks.append((_track(key, role, start, 800 if kind == "effect" else 1000), clip))
        cue.append({"id": key, "character": character, "kind": kind, "source_ref": text(row["source_ref"], "Pointer naskah"),
                    "start_ms": start, "duration_ms": duration, "end_ms": end, "wav_sha256": proof["wav_sha256"],
                    **({"license_ref": proof["license_ref"]} if "license_ref" in proof else {})})
        previous = cue[-1]
    if not has_dialogue:
        raise ContractError("Drama membutuhkan setidaknya satu dialog.")
    settings = {"rate": rate, "channels": 1, "duration_ms": clock, "headroom": 29000,
                "duck_threshold": 1000, "duck_milli": 1000, "attack_ms": 0, "release_ms": 0}
    audio, report = mix_tracks(settings, tracks)
    result = wav(audio)
    return result, {"schema": "ace.media.drama-receipt.v1", "plan_sha256": expected, "series": series,
                    "episode": episode, "declared_predecessor_sha256": predecessor, "cues": cue,
                    "episode_wav_sha256": sha256(result).hexdigest(), "audio": report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        payload, report = produce_drama(decode(read(args.plan)), args.expect_sha256, args.asset_root)
        with args.output.open("xb") as stream:
            stream.write(payload)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
