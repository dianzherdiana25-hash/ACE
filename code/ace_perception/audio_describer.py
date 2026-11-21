"""Rakit narasi aksesibilitas pada interval hening yang dideklarasikan.

Keterangan foto harus punya rujukan media. Klip narasi opsional
mengikat hash kata yang akan diucapkan. Jadwal first-fit menjaga
jeda antar cue dan tidak melewati jendela hening. Artefak WAV
hanya disusun jika seluruh narasi memiliki bukti klip lengkap.
"""
import argparse
from array import array
from hashlib import sha256
from pathlib import Path
import sys

from . import _audio, _perception_io, _raster, _vision
from .audio_denoiser import _pcm16
from .audio_pipeline import _canonical, _integer
from .document_extractor import _token
from .perceptual_memory import _digest


MAX_CUES = 128
MAX_CLIP_BYTES = 600_000


def _windows(raw, timeline):
    if not isinstance(raw, list) or len(raw) > MAX_CUES:
        raise ValueError("Jumlah jendela narasi di luar batas.")
    result = []
    previous = 0
    for row in raw:
        if not isinstance(row, dict) or set(row) != {"start_us", "end_us", "source_ref"}:
            raise ValueError("Bentuk jendela narasi tidak sah.")
        a = _integer(row["start_us"], previous, timeline, "Awal jendela")
        b = _integer(row["end_us"], a+1, timeline, "Akhir jendela")
        result.append((a, b, _token(row["source_ref"], "Rujukan jendela")))
        previous = b
    return result


def _clip(root, raw, description, rate):
    if raw is None:
        return None, None
    if not isinstance(raw, dict) or set(raw) != {"path", "sha256", "bytes", "quote_sha256", "source_ref"}:
        raise ValueError("Bentuk klip narasi tidak sah.")
    if _digest(raw["quote_sha256"]) != sha256(description.encode()).hexdigest():
        raise ValueError("Klip tidak tertambat ke kata narasi.")
    size = _integer(raw["bytes"], 1, MAX_CLIP_BYTES, "Byte klip")
    key = _digest(raw["sha256"])
    payload = _perception_io.read_relative(root, raw["path"], size, key)
    audio = _audio.decode(payload)
    if len(payload) != size or audio.sample_rate != rate or audio.channels != 1:
        raise ValueError("Format atau ukuran klip narasi berbeda.")
    return audio.mono, {"sha256": key, "source_ref": _token(raw["source_ref"], "Rujukan rekaman narasi")}


def build(root, plan):
    raw = _vision.spec(plan, "ace.perception-audio-description-plan.v1",
                       ("visual_sha256", "duration_us", "sample_rate", "silence", "cues",
                        "minimum_gap_us", "maximum_delay_us", "characters_per_second"))
    checksum = _digest(raw["visual_sha256"])
    rate = _integer(raw["sample_rate"], _audio.MIN_RATE, _audio.MAX_RATE, "Laju narasi")
    timeline = _integer(raw["duration_us"], 1, _audio.MAX_SAMPLES*1_000_000//rate, "Durasi")
    space = _integer(raw["minimum_gap_us"], 0, 10_000_000, "Jeda narasi")
    delay = _integer(raw["maximum_delay_us"], 0, 15_000_000, "Tunda narasi")
    speed = _integer(raw["characters_per_second"], 1, 50, "Karakter per detik")
    windows = _windows(raw["silence"], timeline)
    cues = raw["cues"]
    if not isinstance(cues, list) or not 1 <= len(cues) <= MAX_CUES:
        raise ValueError("Jumlah cue narasi di luar batas.")
    planned = []
    seen = set()
    for cue in cues:
        if not isinstance(cue, dict) or set(cue) != {"id", "visual_time_us", "source_ref", "description", "clip"}:
            raise ValueError("Bentuk cue narasi tidak sah.")
        key = _token(cue["id"], "ID narasi")
        if key in seen:
            raise ValueError("ID narasi ganda.")
        seen.add(key)
        at = _integer(cue["visual_time_us"], 0, timeline, "Waktu adegan")
        description = _token(cue["description"], "Kutipan narasi")
        clip, proof = _clip(root, cue["clip"], description, rate)
        expected = ((len(clip)*1_000_000+rate-1)//rate if clip is not None else (
                    len(description)*1_000_000+speed-1)//speed)
        planned.append((at, key, _token(cue["source_ref"], "Rujukan adegan"), description, expected, clip, proof))

    placements = []
    report = []
    cursor = 0
    for at, key, pointer, description, expected, clip, proof in sorted(planned):
        placed = None
        for left, right, ref in windows:
            beginning = max(left, at, cursor)
            sample_start = (beginning*rate+999_999)//1_000_000
            exact = (sample_start*1_000_000+rate-1)//rate
            if exact <= at+delay and exact+expected <= right:
                placed = (exact, exact+expected, ref)
                cursor = exact+expected+space
                if clip is not None:
                    placements.append((sample_start, clip))
                break
        report.append({"id": key, "visual_time_us": at, "description": description, "source_ref": pointer,
                       "expected_duration_us": expected, "clip": proof, "status": "scheduled" if placed else "no_silence_slot",
                       "slot": {"start_us": placed[0], "end_us": placed[1], "source_ref": placed[2]} if placed else None})
    artifact = None
    if len(placements) == len(report):
        waveform = array("h", [0])*(timeline*rate//1_000_000)
        for start, phrase in placements:
            waveform[start:start+len(phrase)] = phrase
        artifact = _pcm16(waveform, rate)
    return artifact, {"schema": "ace.perception-audio-description.v1", "visual_sha256": checksum,
                      "plan_sha256": sha256(plan).hexdigest(), "duration_us": timeline,
                      "sample_rate": rate, "output_sha256": sha256(artifact).hexdigest() if artifact else None,
                      "status": "audio_rendered" if artifact else "plan_only", "cues": report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        artifact, result = build(args.root, _raster.read(args.plan, _vision.MAX_SPEC_BYTES))
        if args.output is not None and artifact is not None:
            with args.output.open("xb") as stream:
                stream.write(artifact)
        sys.stdout.buffer.write(_canonical(result)+b"\n")
    except (OSError, OverflowError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(any(row["status"] != "scheduled" for row in result["cues"]))


if __name__ == "__main__":
    raise SystemExit(main())
