"""Gunakan terjemahan tersumber dan tahan drift istilah, placeholder, angka, atau durasi."""
import argparse
from collections import Counter
import re
from pathlib import Path
import sys
import unicodedata

from ._contracts import (ContractError, canonical, checked, decode, entries, identifier,
                         integer, obj, read, schema, text)

PLACEHOLDER = re.compile(r"\{[a-zA-Z0-9_]+\}")
NUMBER = re.compile(r"(?<!\w)[+-]?\d+(?:[.,]\d+)*(?!\w)")
LANGUAGE = re.compile(r"[a-z]{2}(?:-[A-Z]{2})?")


def _language(value):
    if not isinstance(value, str) or not LANGUAGE.fullmatch(value):
        raise ContractError("Kode bahasa belum sah.")
    return value


def _words(raw):
    return unicodedata.normalize("NFC", raw).casefold()


def _includes(raw, term):
    return re.search(r"(?<!\w)" + re.escape(_words(term)) + r"(?!\w)", _words(raw)) is not None


def _table(raw):
    catalog = {}
    for entry in entries(raw, 1000):
        obj(entry, ("source", "target", "source_ref"))
        key = text(entry["source"], "Teks sumber", 600)
        if key in catalog:
            raise ContractError("Terjemahan untuk teks sumber ganda.")
        catalog[key] = (text(entry["target"], "Teks lokal", 600),
                        text(entry["source_ref"], "Pointer terjemahan"))
    return catalog


def localize(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.localization.v1", ("source_language", "target_language", "max_chars_per_sec",
                                              "glossary", "translations", "segments"))
    source = _language(plan["source_language"])
    target = _language(plan["target_language"])
    if source == target:
        raise ContractError("Bahasa sumber dan target harus berlainan.")
    limit = integer(plan["max_chars_per_sec"], "Karakter per detik", 4, 60)
    glossary = _table(plan["glossary"])
    translations = _table(plan["translations"])
    segments = []
    seen = set()
    previous = 0
    for row in entries(plan["segments"], 700, 1):
        obj(row, ("id", "start_ms", "end_ms", "text", "source_ref"))
        key = identifier(row["id"], "Segmen")
        if key in seen:
            raise ContractError("ID segmen ganda.")
        seen.add(key)
        start = integer(row["start_ms"], "Waktu awal", previous, 3_600_000)
        end = integer(row["end_ms"], "Waktu akhir", start + 1, 3_600_000)
        previous = end
        original = text(row["text"], "Teks segmen", 600)
        origin = text(row["source_ref"], "Pointer struktur segmen")
        target_text, translation_ref = translations.get(original, (None, None))
        reasons = []
        term_checks = []
        if target_text is None:
            reasons.append("missing_translation")
        else:
            for regex, label in ((PLACEHOLDER, "placeholder_drift"), (NUMBER, "number_drift")):
                if Counter(regex.findall(original)) != Counter(regex.findall(target_text)):
                    reasons.append(label)
            if len(target_text) * 1000 > limit * (end - start):
                reasons.append("reading_rate")
            for term, (rendering, pointer) in sorted(glossary.items()):
                if _includes(original, term):
                    passed = _includes(target_text, rendering)
                    term_checks.append({"source": term, "expected": rendering, "source_ref": pointer, "pass": passed})
            if any(not test["pass"] for test in term_checks):
                reasons.append("terminology_drift")
        segments.append({"id": key, "start_ms": start, "end_ms": end, "source_ref": origin, "original": original,
                         "localized": target_text if not reasons else None, "translation_source_ref": translation_ref,
                         "glossary": term_checks, "reasons": reasons})
    ready = sum(not segment["reasons"] for segment in segments)
    return {"schema": "ace.media.localized.v1", "plan_sha256": expected, "source_language": source,
            "target_language": target, "ready": ready, "holding": len(segments) - ready, "segments": segments,
            "status": "ready" if ready == len(segments) else "hold"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = localize(decode(read(args.plan)), args.expect_sha256)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report["status"] != "ready")


if __name__ == "__main__":
    raise SystemExit(main())
