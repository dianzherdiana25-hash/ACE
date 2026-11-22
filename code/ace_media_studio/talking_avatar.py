"""Gerakkan avatar geometris orisinal sesuai fonem dari sintesis narasi sendiri."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._audio import Audio, parse_wav, wav
from ._contracts import ContractError, canonical, checked, decode, identity, integer, read, schema
from ._raster import raster
from ._story_video import box, frame_hash, write_movie
from .character_keeper import portrait
from .voice_generator import synthesize


SHAPES = {"rest": (5, 1), "wide": (9, 3), "open": (7, 6), "round": (4, 5), "closed": (7, 1)}


def _viseme(unit):
    if unit == "_":
        return "rest"
    if unit in ("a", "e", "ə"):
        return "open"
    if unit in ("u", "o", "w"):
        return "round"
    if unit in ("i", "y"):
        return "wide"
    if unit in ("m", "p", "b", "f", "v"):
        return "closed"
    return "rest"


def talk(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.avatar-plan.v1", ("voice", "bible", "fps"))
    fps = integer(plan["fps"], "FPS", 4, 30)
    voice = plan["voice"]
    waveform, speech = synthesize(voice, identity(voice))
    audio = parse_wav(waveform)
    if audio.rate % fps:
        raise ContractError("Frame rate avatar perlu membagi sample rate narasi.")
    raw, character = portrait(plan["bible"], identity(plan["bible"]), "front")
    base = raster(raw)
    clean = box(base, 18, 29, 13, 8, base.at(24, 29))
    stride = audio.rate // fps
    count = (audio.frames + stride - 1) // stride
    if count > 450:
        raise ContractError("Narasi avatar melebihi anggaran frame.")
    padded = wav(Audio(audio.rate, 1, audio.samples + (0,) * (count * stride - audio.frames)))
    timeline = []

    def images():
        index = 0
        units = speech["phonemes"]
        for frame in range(count):
            position = frame * stride + stride // 2
            while index < len(units) and units[index]["last_frame_exclusive"] <= position:
                index += 1
            phoneme = units[index]["phoneme"] if index < len(units) else "_"
            form = _viseme(phoneme)
            w, h = SHAPES[form]
            image = box(clean, 24 - w // 2, 32 - h // 2, w, h, base.at(20, 24))
            timeline.append({"frame": frame, "sample": position, "phoneme": phoneme, "viseme": form,
                             "source_frame_sha256": frame_hash(image)})
            yield image

    output, report = write_movie(images(), base.width, base.height, fps, padded)
    return output, {"schema": "ace.media.avatar-receipt.v1", "plan_sha256": expected,
                    "speech_wav_sha256": speech["wav_sha256"], "voice_audio_sha256": sha256(padded).hexdigest(),
                    "portrait_sha256": character["image_sha256"], "timebase_sample_rate": audio.rate,
                    "timing": "synthetic_phoneme_midpoint", "timeline": timeline, **report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        data, report = talk(decode(read(args.plan)), args.expect_sha256)
        with args.output.open("xb") as stream:
            stream.write(data)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
