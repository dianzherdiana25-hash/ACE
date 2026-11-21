"""Klasifikasikan bahasa per segmen dari receipt transkrip yang tertambat.

Daftar kata penanda harus bersumber dan disediakan pengguna. Penanda
yang dipakai beberapa bahasa dikeluarkan. Dukungan lintas bahasa
membuka label campur, sedangkan seri dan data tipis ditahan. Metode
mengukur isi transkrip offline tanpa memanggil decoder bahasa.
"""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
import re
import sys
import unicodedata

from . import _audio, _raster, _vision, audio_pipeline
from .audio_pipeline import _canonical, _integer
from .document_extractor import _token


LANGUAGE = re.compile(r"[a-z]{2,3}(?:-[a-z]{2,8})?")
WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
MAX_LANGUAGES = 20
MAX_TOKENS = 4000


def _terms(value):
    return WORD.findall(unicodedata.normalize("NFC", value.casefold()))


def _profiles(data):
    source = _vision.spec(data, "ace.perception-language-profile.v1",
                          ("profiles", "minimum_hits", "minimum_margin", "mixed_minimum_hits"))
    raw = source["profiles"]
    if not isinstance(raw, list) or not 2 <= len(raw) <= MAX_LANGUAGES:
        raise ValueError("Perlu sedikitnya dua profil bahasa.")
    terms = defaultdict(set)
    profile_refs = {}
    pointers = set()
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"code", "source_ref", "terms"}:
            raise ValueError("Profil bahasa tidak sah.")
        code = _token(item["code"], "Kode bahasa")
        ref = _token(item["source_ref"], "Rujukan daftar bahasa")
        words = item["terms"]
        if code in profile_refs or ref in pointers or not LANGUAGE.fullmatch(code):
            raise ValueError("Kode bahasa/rujukan ganda atau tidak sah.")
        if not isinstance(words, list) or not 1 <= len(words) <= MAX_TOKENS:
            raise ValueError("Daftar penanda bahasa melampaui batas.")
        local = set()
        for raw_term in words:
            original = _token(raw_term, "Penanda bahasa")
            tokens = _terms(original)
            normalized = unicodedata.normalize("NFC", original.casefold())
            if tokens != [normalized] or normalized in local:
                raise ValueError("Penanda perlu satu token unik.")
            local.add(normalized)
            terms[normalized].add(code)
        profile_refs[code] = ref
        pointers.add(ref)
    owners = {term: next(iter(codes)) for term, codes in terms.items() if len(codes) == 1}
    excluded = len(terms)-len(owners)
    return owners, excluded, profile_refs, (
        _integer(source["minimum_hits"], 1, MAX_TOKENS, "Hit minimum"),
        _integer(source["minimum_margin"], 1, MAX_TOKENS, "Margin minimum"),
        _integer(source["mixed_minimum_hits"], 1, MAX_TOKENS, "Hit campuran"),
    )


def _classify(segment, owners, sources, policy):
    first, margin, mix = policy
    hits = defaultdict(set)
    tokens = [term for item in segment["words"] for term in _terms(item["word"])]
    for token in tokens:
        if token in owners:
            hits[owners[token]].add(token)
    ranking = sorted(((len(items), code) for code, items in hits.items()), key=lambda item: (-item[0], item[1]))
    possible = [code for count, code in ranking if count >= mix]
    language = None
    if segment["status"] != "read":
        status = "no_transcript"
    elif not ranking or ranking[0][0] < first:
        status = "insufficient_evidence"
    elif len(possible) >= 2:
        status = "mixed"
    elif len(ranking) >= 2 and ranking[0][0]-ranking[1][0] < margin:
        status = "undecided"
    else:
        status, language = "classified", ranking[0][1]
    evidence = [{"code": code, "distinct_hits": count, "profile_ref": sources[code]}
                for count, code in ranking]
    return {"id": segment["id"], "start_sample": segment["start_sample"], "end_sample": segment["end_sample"],
            "start_us": segment["start_us"], "end_us": segment["end_us"], "transcript_status": segment["status"],
            "transcript_ref": segment["receipt_ref"], "status": status, "language": language,
            "mixed_languages": possible if status == "mixed" else [], "tokens_examined": len(tokens), "evidence": evidence}


def detect(wav, transcript, profiles, **segment_policy):
    owners, excluded, sources, policy = _profiles(profiles)
    bound = audio_pipeline.align(wav, transcript, **segment_policy)
    rows = [_classify(row, owners, sources, policy) for row in bound["segments"]]
    return {"schema": "ace.perception-audio-language.v1", "audio_sha256": bound["audio_sha256"],
            "roster_sha256": bound["roster_sha256"], "transcript_sha256": bound["receipt_sha256"],
            "profiles_sha256": sha256(profiles).hexdigest(), "shared_terms_excluded": excluded,
            "counts": dict(sorted(Counter(row["status"] for row in rows).items())), "segments": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav", type=Path)
    parser.add_argument("transcript", type=Path)
    parser.add_argument("profiles", type=Path)
    parser.add_argument("--silence-ms", type=int, default=100)
    parser.add_argument("--frame-ms", type=int, default=20)
    parser.add_argument("--rms", type=int, default=300)
    parser.add_argument("--minimum-ms", type=int, default=40)
    args = parser.parse_args(argv)
    try:
        report = detect(_raster.read(args.wav, _audio.MAX_BYTES),
                        _raster.read(args.transcript, audio_pipeline.MAX_RECEIPT_BYTES),
                        _raster.read(args.profiles, _vision.MAX_SPEC_BYTES),
                        silence_ms=args.silence_ms, frame_ms=args.frame_ms, rms=args.rms, minimum_ms=args.minimum_ms)
        sys.stdout.buffer.write(_canonical(report) + b"\n")
    except (OSError, OverflowError, RecursionError, ValueError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
