"""Rakit naskah podcast bersegmen dengan cue dan bukti asal setiap klip."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._assets import asset
from ._audio import Audio, MAX_WAV, align, parse_wav, sample_rate, wav
from ._contracts import (ContractError, canonical, checked, decode, entries, identifier,
                         identity, integer, obj, read, schema, text)
from .audio_mixer import mix_tracks
from .voice_generator import synthesize


def _track(cue_id, role, cursor, gain=1000):
    return {"id": cue_id, "role": role, "start_ms": cursor, "gain_milli": gain,
            "fade_in_ms": 0, "fade_out_ms": 0, "pan": 0}


def _cue(item, root, rate, voice, index):
    common = ("id", "kind", "title")
    kind = item.get("kind") if isinstance(item, dict) else None
    if kind == "pause":
        obj(item, (*common, "duration_ms"))
        duration = integer(item["duration_ms"], "Jeda", 1, 5000)
        return None, duration, {}
    if kind == "voice":
        obj(item, (*common, "text", "source_ref"))
        plan = {"schema": "ace.media.voice-plan.v1", "language": "id", "rate": rate,
                "text": item["text"], "source_ref": item["source_ref"], "pitch_hz": voice["pitch_hz"],
                "peak": voice["peak"], "speed_milli": voice["speed_milli"], "seed": voice["seed"] + index}
        data, receipt = synthesize(plan, identity(plan))
        evidence = {"source_ref": receipt["source_ref"], "text_sha256": receipt["source_text_sha256"],
                    "generated_wav_sha256": receipt["wav_sha256"]}
    elif kind == "clip":
        obj(item, (*common, "path", "sha256", "license_ref"))
        evidence = {"license_ref": text(item["license_ref"], "Izin klip"), "asset_sha256": item["sha256"]}
        data = asset(root, item["path"], item["sha256"], MAX_WAV)
    else:
        raise ContractError("Jenis segmen podcast tidak didukung.")
    audio = align(parse_wav(data), rate, 1)
    if not audio.frames:
        raise ContractError("Segmen podcast tidak mengandung sampel.")
    return audio, (audio.frames * 1000 + rate - 1) // rate, evidence


def produce(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.podcast-plan.v1", ("title", "rate", "voice", "segments", "bed"))
    title = text(plan["title"], "Judul podcast")
    rate = sample_rate(plan["rate"])
    voice = obj(plan["voice"], ("pitch_hz", "speed_milli", "peak", "seed"))
    integer(voice["seed"], "Seed", 0, 2**63 - 41)
    cues = []
    used = set()
    tracks = []
    cursor = 0
    for index, item in enumerate(entries(plan["segments"], 38, 1)):
        audio, duration, evidence = _cue(item, root, rate, voice, index)
        cue_id = identifier(item["id"], "ID segmen")
        if cue_id == "music_bed" or cue_id in used:
            raise ContractError("ID segmen podcast ganda atau dicadangkan.")
        used.add(cue_id)
        if audio is not None:
            tracks.append((_track(cue_id, "speech", cursor), audio))
        cues.append({"id": cue_id, "kind": item["kind"], "title": text(item["title"], "Judul segmen"),
                     "start_ms": cursor, "duration_ms": duration, **evidence})
        cursor += duration
        if cursor > 60_000:
            raise ContractError("Durasi episode melampaui satu menit.")
    if not tracks:
        raise ContractError("Episode perlu narasi atau klip.")
    bed_report = None
    if plan["bed"] is not None:
        bed = obj(plan["bed"], ("path", "sha256", "license_ref", "gain_milli"))
        bed_report = {"sha256": bed["sha256"], "license_ref": text(bed["license_ref"], "Izin musik")}
        pcm = align(parse_wav(asset(root, bed["path"], bed["sha256"], MAX_WAV)), rate, 1)
        frames = cursor * rate // 1000
        pcm = Audio(pcm.rate, pcm.channels, pcm.samples[:frames])
        tracks.append((_track("music_bed", "bed", 0, bed["gain_milli"]), pcm))
    settings = {"rate": rate, "channels": 1, "duration_ms": cursor, "headroom": 30000,
                "duck_threshold": 700, "duck_milli": 330, "attack_ms": 10, "release_ms": 150}
    output, report = mix_tracks(settings, tracks)
    data = wav(output)
    receipt = {"schema": "ace.media.podcast-receipt.v1", "plan_sha256": expected, "title": title,
               "episode_wav_sha256": sha256(data).hexdigest(), "chapters": cues,
               "bed": bed_report, "mix": report}
    return data, receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        audio, report = produce(decode(read(args.plan)), args.expect_sha256, args.asset_root)
        args.output.mkdir()
        (args.output / "episode.wav").write_bytes(audio)
        (args.output / "chapters.json").write_bytes(canonical(report) + b"\n")
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
