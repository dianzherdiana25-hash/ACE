"""Tambatkan transkrip dwibahasa ke aktivitas suara WAV, dengan hold saat cue ambigu."""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from ._assets import asset
from ._audio import MAX_WAV, mono, parse_wav
from ._contracts import (ContractError, canonical, checked, decode, entries, identifier,
                         integer, obj, read, schema, text)


def speech_regions(audio, threshold, maximum_gap, minimum):
    signal = mono(audio)
    step = signal.rate // 100
    active = []
    for start in range(0, signal.frames, step):
        frame = signal.samples[start:start + step]
        if sum(map(abs, frame)) >= threshold * len(frame):
            active.append((start * 1000 // signal.rate, (start + len(frame)) * 1000 // signal.rate))
    spans = []
    for start, end in active:
        if spans and start - spans[-1][1] <= maximum_gap:
            spans[-1][1] = end
        else:
            spans.append([start, end])
    return [span for span in spans if span[1] - span[0] >= minimum]


def _stamp(raw):
    seconds, ms = divmod(raw, 1000)
    minutes, sec = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    return f"{hours:02d}:{minute:02d}:{sec:02d}.{ms:03d}"


def _vtt(cues, language):
    fields = ["WEBVTT", ""]
    for cue in cues:
        sample = cue["text"][language].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        fields.extend([cue["id"], f"{_stamp(cue['start_ms'])} --> {_stamp(cue['end_ms'])}", sample, ""])
    return ("\n".join(fields) + "\n").encode("utf-8")


def make_subtitles(plan, expected, root):
    checked(plan, expected)
    schema(plan, "ace.media.subtitle-plan.v1", ("audio", "threshold", "gap_ms",
                                               "minimum_ms", "max_chars_per_sec", "phrases"))
    link = obj(plan["audio"], ("path", "sha256"))
    audio = parse_wav(asset(root, link["path"], link["sha256"], MAX_WAV))
    if not audio.frames or audio.frames > audio.rate * 300:
        raise ContractError("Audio subtitle harus berdurasi nol sampai lima menit, dengan sampel.")
    threshold = integer(plan["threshold"], "Ambang sinyal", 1, 32767)
    gap = integer(plan["gap_ms"], "Gabung jeda", 0, 3000)
    minimum = integer(plan["minimum_ms"], "Durasi ujaran minimum", 10, 5000)
    speed = integer(plan["max_chars_per_sec"], "Keterbacaan", 6, 60)
    regions = speech_regions(audio, threshold, gap, minimum)
    seen = set()
    phrases = []
    for item in entries(plan["phrases"], 300, 1):
        obj(item, ("id", "id_text", "en_text", "source_ref"))
        key = identifier(item["id"], "Frasa")
        if key in seen:
            raise ContractError("ID frasa ganda.")
        seen.add(key)
        phrases.append({"id": key, "source_ref": text(item["source_ref"], "Pointer transkrip"),
                        "text": {"id": text(item["id_text"], "Subtitle Indonesia", 210),
                                 "en": text(item["en_text"], "Subtitle Inggris", 210)}})
    reasons = []
    cues = []
    if len(regions) != len(phrases):
        reasons.append({"rule": "speech_phrase_count", "speech_regions": len(regions), "phrases": len(phrases)})
    else:
        for region, phrase in zip(regions, phrases, strict=True):
            start, end = region
            for language, value in phrase["text"].items():
                if len(value) * 1000 > speed * (end - start):
                    reasons.append({"rule": "reading_rate", "id": phrase["id"], "language": language})
            cues.append({**phrase, "start_ms": start, "end_ms": end})
    outputs = {lang: _vtt(cues, lang) for lang in ("id", "en")} if not reasons else {}
    receipt = {"schema": "ace.media.subtitle-receipt.v1", "plan_sha256": expected, "audio_sha256": link["sha256"],
               "alignment": "ordered_verified_transcript_and_pcm_activity", "speech_regions": regions,
               "status": "ready" if outputs else "hold", "blocking": reasons, "cues": cues,
               "output_sha256": {lang: sha256(raw).hexdigest() for lang, raw in outputs.items()}}
    return outputs, receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("asset_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        tracks, receipt = make_subtitles(decode(read(args.plan)), args.expect_sha256, args.asset_root)
        if tracks:
            args.output.mkdir()
            for language, content in tracks.items():
                (args.output / f"{language}.vtt").write_bytes(content)
        sys.stdout.buffer.write(canonical(receipt) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(not tracks)


if __name__ == "__main__":
    raise SystemExit(main())
