"""Gabungkan receipt transkrip bertimestamp dengan label bahasa per kata.

Isi ujaran diambil dari receipt audio yang sudah terikat ke WAV.
Penanda unik memberi label kata. Kata di antara dua penanda
berbahasa sama boleh diberi konteks terbatas sesuai kebijakan.
Pergantian antarrentang mempunyai cap waktu dan sumber.
"""
import argparse
from hashlib import sha256
from pathlib import Path
import sys

from . import _audio, _raster, _vision, audio_language_detector, audio_pipeline
from .audio_pipeline import _canonical, _integer


def _marker(word, owners):
    codes = {owners[token] for token in audio_language_detector._terms(word) if token in owners}
    return next(iter(codes)) if len(codes) == 1 else None


def _contextualize(words, owners, bridge_unknown):
    detected = [_marker(row["word"], owners) for row in words]
    complete = list(detected)
    left = None
    for index, code in enumerate(detected):
        if code is None:
            continue
        if left is not None:
            gap = index-left-1
            if 0 < gap <= bridge_unknown and detected[left] == code:
                complete[left+1:index] = [code]*gap
        left = index
    return [{**row, "language": language,
             "language_source": "marker" if evidence is not None else "neighbor_context" if language is not None else "unknown"}
            for row, evidence, language in zip(words, detected, complete, strict=True)]


def _runs(words, refs):
    groups = []
    for row in words:
        code = row["language"]
        if not groups or groups[-1]["language"] != code:
            groups.append({"language": code, "source_ref": refs.get(code), "start_us": row["start_us"],
                           "end_us": row["end_us"], "word_count": 0, "marker_count": 0})
        current = groups[-1]
        current["end_us"] = row["end_us"]
        current["word_count"] += 1
        current["marker_count"] += row["language_source"] == "marker"
    return groups


def transcribe(wav, transcript, profiles, *, bridge_unknown=0, **segment_policy):
    gap = _integer(bridge_unknown, 0, 14, "Panjang konteks")
    owners, excluded, refs, _ = audio_language_detector._profiles(profiles)
    observed = audio_pipeline.align(wav, transcript, **segment_policy)
    segments, switches = [], []
    for segment in observed["segments"]:
        words = _contextualize(segment["words"], owners, gap)
        groups = _runs(words, refs)
        for first, second in zip(groups, groups[1:]):
            if first["language"] is not None and second["language"] is not None:
                switches.append({"segment": segment["id"], "from": first["language"], "to": second["language"],
                                 "start_us": second["start_us"], "receipt_ref": segment["receipt_ref"],
                                 "left_profile_ref": first["source_ref"], "right_profile_ref": second["source_ref"]})
        segments.append({**segment, "words": words, "language_runs": groups,
                         "unlabelled_words": sum(row["language"] is None for row in words)})
    return {"schema": "ace.perception-code-switch.v1", "media_sha256": observed["audio_sha256"],
            "roster_sha256": observed["roster_sha256"], "transcript_sha256": observed["receipt_sha256"],
            "profiles_sha256": sha256(profiles).hexdigest(), "excluded_shared_markers": excluded,
            "max_context_words": gap, "status": observed["status"], "segments": segments, "switches": switches}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav", type=Path)
    parser.add_argument("transcript", type=Path)
    parser.add_argument("profiles", type=Path)
    parser.add_argument("--bridge-unknown", type=int, default=0)
    parser.add_argument("--silence-ms", type=int, default=100)
    args = parser.parse_args(argv)
    try:
        report = transcribe(_raster.read(args.wav, _audio.MAX_BYTES),
                            _raster.read(args.transcript, audio_pipeline.MAX_RECEIPT_BYTES),
                            _raster.read(args.profiles, _vision.MAX_SPEC_BYTES), bridge_unknown=args.bridge_unknown,
                            silence_ms=args.silence_ms)
        sys.stdout.buffer.write(_canonical(report)+b"\n")
    except (OSError, OverflowError, ValueError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report["status"] == "incomplete")


if __name__ == "__main__":
    raise SystemExit(main())
