"""Kutip keputusan, tindak lanjut, dan topik rapat dari receipt transkrip.

Rencana memberi frasa penanda eksplisit. Hasil mengutip jendela
kata asli beserta nomor segmen, waktu, dan rujukan aturan.
Kutipan yang dipangkas, tumpang tindih, serta segmen hilang
terlihat supaya laporan tidak menambah isi yang absen.
"""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
import sys
import unicodedata

from . import _audio, _raster, _vision, audio_pipeline
from .audio_pipeline import _canonical, _integer
from .document_extractor import _token
from .perceptual_memory import WORDS


KINDS = {"decision", "action", "question", "topic"}
MAX_RULES = 128


def _terms(text):
    return WORDS.findall(unicodedata.normalize("NFC", text.casefold()))


def _rules(raw):
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_RULES:
        raise ValueError("Jumlah aturan rapat di luar batas.")
    lookup = defaultdict(list)
    seen = set()
    for row in raw:
        if not isinstance(row, dict) or set(row) != {"id", "kind", "phrase", "source_ref"}:
            raise ValueError("Bentuk aturan rapat tidak sah.")
        key, kind, ref = (_token(row[field], field) for field in ("id", "kind", "source_ref"))
        phrase = _terms(_token(row["phrase"], "Frasa"))
        if key in seen or kind not in KINDS or not 1 <= len(phrase) <= 8:
            raise ValueError("Aturan rapat ganda, salah kelas, atau frasa tidak sah.")
        seen.add(key)
        lookup[phrase[0]].append((phrase, key, kind, ref))
    for group in lookup.values():
        group.sort(key=lambda row: (-len(row[0]), row[1]))
    return lookup


def summarize(wav, transcript, plan, **policy):
    config = _vision.spec(plan, "ace.perception-meeting-rules.v1", ("rules", "context_words", "maximum_excerpts"))
    rules = _rules(config["rules"])
    context = _integer(config["context_words"], 0, 32, "Kata konteks")
    allowed = _integer(config["maximum_excerpts"], 1, 256, "Kutipan maksimum")
    bound = audio_pipeline.align(wav, transcript, **policy)
    excerpts = []
    gaps = []
    counts = Counter()
    missed = 0
    for segment in bound["segments"]:
        if segment["status"] != "read":
            gaps.append({"segment": segment["id"], "status": segment["status"], "receipt_ref": segment["receipt_ref"]})
            continue
        words = segment["words"]
        terms = [tuple(_terms(item["word"])) for item in words]
        for index, token in enumerate(terms):
            if len(token) != 1:
                continue
            for phrase, key, kind, proof in rules.get(token[0], ()):
                finish = index+len(phrase)
                if terms[index:finish] != [(item,) for item in phrase]:
                    continue
                counts[kind] += 1
                if len(excerpts) >= allowed:
                    missed += 1
                    break
                stop = min(len(words), finish+context)
                chosen = words[index:stop]
                excerpts.append({"kind": kind, "rule_id": key, "rule_ref": proof, "segment": segment["id"],
                                 "receipt_ref": segment["receipt_ref"], "start_us": chosen[0]["start_us"],
                                 "end_us": chosen[-1]["end_us"], "quote": " ".join(word["word"] for word in chosen),
                                 "word_interval": [index, stop]})
                break
    return {"schema": "ace.perception-meeting-extracts.v1", "audio_sha256": bound["audio_sha256"],
            "transcript_sha256": bound["receipt_sha256"], "rules_sha256": sha256(plan).hexdigest(),
            "counts": dict(sorted(counts.items())), "omitted_excerpts": missed, "transcript_gaps": gaps,
            "excerpts": excerpts}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav", type=Path)
    parser.add_argument("transcript", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--silence-ms", type=int, default=100)
    args = parser.parse_args(argv)
    try:
        result = summarize(_raster.read(args.wav, _audio.MAX_BYTES),
                           _raster.read(args.transcript, audio_pipeline.MAX_RECEIPT_BYTES),
                           _raster.read(args.plan, _vision.MAX_SPEC_BYTES), silence_ms=args.silence_ms)
        sys.stdout.buffer.write(_canonical(result)+b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
