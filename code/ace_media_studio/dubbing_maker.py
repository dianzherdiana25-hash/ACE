"""Pasang dua trek sulih suara bersumber pada timeline visual yang sama."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._assets import asset
from ._audio import Audio, MAX_WAV, align, parse_wav, wav
from ._clip_edit import open_clip
from ._contracts import (ContractError, canonical, checked, decode, entries,
                         identifier, integer, obj, read, schema, text)
from ._story_video import write_movie


LANGUAGES = ("id", "en")


def dub(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.dub-plan.v1", ("source", "segments"))
    frames, fps, _ = open_clip(root, plan["source"])
    if 24000 % fps or frames[0].width % 2 or frames[0].height % 2:
        raise ContractError("Cadence atau ukuran sumber tidak cocok untuk sulih suara.")
    per_frame = 24000 // fps
    samples = {lang: [0] * (len(frames) * per_frame) for lang in LANGUAGES}
    used = set()
    previous = 0
    timeline = []
    for row in entries(plan["segments"], 60, 1):
        obj(row, ("id", "start_frame", "end_frame", "voices"))
        cue = identifier(row["id"], "ID adegan dub")
        if cue in used:
            raise ContractError("ID adegan dub ganda.")
        used.add(cue)
        start = integer(row["start_frame"], "Frame awal", previous, len(frames) - 1)
        end = integer(row["end_frame"], "Frame akhir eksklusif", start + 1, len(frames))
        previous = end
        chunk = {"id": cue, "start_frame": start, "end_frame": end, "voices": {}}
        voices = obj(row["voices"], LANGUAGES)
        for lang in LANGUAGES:
            ref = obj(voices[lang], ("path", "sha256", "source_ref"))
            source = text(ref["source_ref"], "Pointer rekaman " + lang)
            data = asset(root, ref["path"], ref["sha256"], MAX_WAV)
            audio = align(parse_wav(data), 24000, 1)
            if not 0 < audio.frames <= (end - start) * per_frame:
                raise ContractError(f"Durasi suara {lang} pada {cue} melampaui slot atau kosong.")
            offset = start * per_frame
            samples[lang][offset:offset + audio.frames] = audio.samples
            chunk["voices"][lang] = {"source_ref": source, "source_wav_sha256": ref["sha256"],
                                      "frames_24khz": audio.frames}
        timeline.append(chunk)
    payload = {}
    reports = {}
    for lang in LANGUAGES:
        sound = wav(Audio(24000, 1, tuple(samples[lang])))
        data, info = write_movie(frames, frames[0].width, frames[0].height, fps, sound)
        payload[f"dub_{lang}.mp4"] = data
        reports[lang] = {**info, "wav_sha256": sha256(sound).hexdigest()}
    return payload, {"schema": "ace.media.dub-receipt.v1", "plan_sha256": expected,
                     "source_sha256": plan["source"]["sha256"], "timeline": timeline, "languages": reports}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        files, receipt = dub(decode(read(args.plan)), args.expect_sha256, args.asset_root)
        args.output.mkdir()
        for name, data in files.items():
            (args.output / name).write_bytes(data)
        sys.stdout.buffer.write(canonical(receipt) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
