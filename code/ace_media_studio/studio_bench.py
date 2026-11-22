"""Ukur paket studio pada fixture tertutup dan simpan artefak decode untuk pemeriksaan ulang."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from ._audio import Audio, parse_wav, wav
from ._contracts import ContractError, canonical, checked, decode, identity, read, schema
from ._video import encode_frames, load_movie
from .animation_renderer import animate
from .audio_mixer import mix_tracks
from .character_keeper import portrait, verify
from .cover_maker import make_cover
from .music_generator import generate_music
from .voice_generator import synthesize


def _fit(audio, frames):
    return Audio(audio.rate, audio.channels, (audio.samples + (0,) * max(0, frames - audio.frames))[:frames])


def _track(name, role, gain):
    return {"id": name, "role": role, "start_ms": 0, "gain_milli": gain,
            "fade_in_ms": 0, "fade_out_ms": 0, "pan": 0}


def run_bench(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.studio-bench.v1", ("case", "animation", "cover", "voice", "music", "character"))
    if plan["case"] != "closed_fixture":
        raise ContractError("Bench ini hanya mengukur fixture tertutup.")
    movie, animation = animate(plan["animation"], identity(plan["animation"]))
    cover, cover_report = make_cover(plan["cover"], identity(plan["cover"]))
    speech_raw, speech_report = synthesize(plan["voice"], identity(plan["voice"]))
    music_raw, music_report = generate_music(plan["music"], identity(plan["music"]))
    speech = parse_wav(speech_raw)
    music = parse_wav(music_raw)
    fps = animation["fps"][0]
    count = animation["frames"]
    if speech.rate != music.rate or speech.rate % fps or count * 1000 % fps:
        raise ContractError("Cadence fixture harus selaras dengan frame dan sampel.")
    samples = speech.rate * count // fps
    if speech.frames > samples:
        raise ContractError("Narasi fixture tidak boleh dipotong.")
    mixed, mix = mix_tracks({"rate": speech.rate, "channels": 1, "duration_ms": count * 1000 // fps,
                             "headroom": 26000, "duck_threshold": 700, "duck_milli": 350,
                             "attack_ms": 15, "release_ms": 120},
                            [(_track("voice", "speech", 1000), _fit(speech, samples)),
                             (_track("background", "bed", 280), _fit(music, samples))])
    sound = wav(mixed)
    with TemporaryDirectory(prefix="ace-media-bench-input-") as temporary:
        frames, measured_fps, _ = load_movie(Path(temporary), movie)
    with TemporaryDirectory(prefix="ace-media-bench-output-") as temporary:
        root = Path(temporary)
        final, video = encode_frames(root, frames, animation["width"], animation["height"], measured_fps, sound)
        decoded, final_fps, final_audio = load_movie(root, final)
    character, variants = plan["character"], []
    for pose in ("front", "lean_left", "lean_right", "smile"):
        payload, _ = portrait(character, identity(character), pose)
        variants.append((pose, payload))
    character_report = verify(character, identity(character), variants)
    clips = [frame.receipt()["rgb_sha256"] for frame in decoded]
    region = cover_report["measurements"]["text_regions"]
    metrics = [
        ("video_decodes", len(decoded) == count and final_fps == fps, len(decoded)),
        ("animation_moves", len(set(clips)) > 1, len(set(clips))),
        ("audio_stream", video["audio"] == "aac", video["audio"]),
        ("audio_duration", final_audio is not None and final_audio.frames == count * 24000 // fps,
         final_audio.frames if final_audio else None),
        ("speech_detected", speech_report["peak"] >= 700 and mix["ducked_frames"] > 0, mix["ducked_frames"]),
        ("music_signal", music_report["peak"] >= 300, music_report["peak"]),
        ("pcm_headroom", 0 < mixed.receipt()["peak"] <= 26000, mixed.receipt()["peak"]),
        ("cover_contrast", all(row["pass"] for row in region) and bool(region),
         min((row["contrast_milli"] for row in region), default=None)),
        ("cover_decodes", cover_report["status"] == "pass", cover_report["status"]),
        ("character_variants", len({raw for _, raw in variants}) == len(variants), len(variants)),
    ]
    checks = [{"criterion": label, "pass": value, "measured": observed}
              for label, value, observed in metrics]
    passed = sum(row["pass"] for row in checks)
    score = passed * 10000 // len(checks)
    payload = {"short_animation.mp4": final, "audio_mix.wav": sound, "cover.png": cover}
    payload.update({f"character_{pose}.png": raw for pose, raw in variants})
    report = {"schema": "ace.media.studio-bench-report.v1", "plan_sha256": expected, "scope": "closed_fixture",
              "qa": {"passed": passed, "total": len(checks), "score_bp": score, "checks": checks},
              "character": character_report, "outputs": {key: {"sha256": sha256(data).hexdigest(), "bytes": len(data)}
                                                         for key, data in sorted(payload.items())},
              "backends": {"animation": animation["renderer"], "encode": video["codec"], "audio": video["audio"]},
              "thresholds": {"qa_bp": 8000, "character_bp": 9000},
              "status": "fixture_pass" if score >= 8000 and character_report["score_bp"] >= 9000 else "fixture_hold"}
    return payload, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        payload, report = run_bench(decode(read(args.plan)), args.expect_sha256)
        args.output.mkdir()
        for name, data in payload.items():
            (args.output / name).write_bytes(data)
        (args.output / "report.json").write_bytes(canonical(report) + b"\n")
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report["status"] != "fixture_pass")


if __name__ == "__main__":
    raise SystemExit(main())
