"""Saring rilis dari anotasi yang ditambatkan, dengan hold atas wilayah yang belum ditinjau."""
import argparse
from pathlib import Path
import re
import sys
import unicodedata

from ._contracts import (ContractError, canonical, checked, decode, digest, entries,
                         identifier, integer, obj, read, schema, text)


def _fold(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _match(text_value, phrase):
    return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text_value))


def audit(policy, expected, annotations, annotation_anchor):
    checked(policy, expected)
    checked(annotations, annotation_anchor)
    schema(policy, "ace.media.brand-policy.v1", ("required_channels", "blocked_categories", "phrase_rules"))
    schema(annotations, "ace.media.brand-annotations.v1", ("asset_sha256", "duration_ms", "items"))
    asset = digest(annotations["asset_sha256"])
    duration = integer(annotations["duration_ms"], "Durasi aset", 1, 3_600_000)
    channels = {identifier(item, "Kanal") for item in entries(policy["required_channels"], 10, 1)}
    blocked = {identifier(item, "Kategori") for item in entries(policy["blocked_categories"], 40)}
    rules = {}
    for rule in entries(policy["phrase_rules"], 70):
        obj(rule, ("id", "phrase", "category"))
        key = identifier(rule["id"], "Aturan frasa")
        value = _fold(text(rule["phrase"], "Teks yang diperiksa", 100))
        category = identifier(rule["category"], "Kategori")
        if key in rules or category not in blocked:
            raise ContractError("Aturan ganda atau kategori frasa tidak terdaftar.")
        rules[key] = (value, category)
    findings = []
    coverage = {}
    seen = set()
    for item in entries(annotations["items"], 400, 1):
        obj(item, ("id", "channel", "start_ms", "end_ms", "text", "categories", "source_ref"))
        key = identifier(item["id"], "Anotasi")
        if key in seen:
            raise ContractError("ID anotasi ganda.")
        seen.add(key)
        channel = identifier(item["channel"], "Kanal")
        first = integer(item["start_ms"], "Awal anotasi", 0, duration - 1)
        last = integer(item["end_ms"], "Akhir anotasi", first + 1, duration)
        pointer = text(item["source_ref"], "Pointer anotasi")
        sample = _fold(text(item["text"], "Isi anotasi", 900))
        categories = {identifier(value, "Kategori") for value in entries(item["categories"], 40)}
        for category in sorted(categories & blocked):
            findings.append({"rule": "category", "category": category, "annotation": key, "source_ref": pointer})
        for rule_id, (phrase, category) in sorted(rules.items()):
            if _match(sample, phrase):
                findings.append({"rule": rule_id, "category": category, "annotation": key, "source_ref": pointer})
        coverage.setdefault(channel, []).append((first, last))
    gaps = []
    for channel in sorted(channels):
        cursor = 0
        for start, end in sorted(coverage.get(channel, [])):
            if start > cursor:
                gaps.append({"channel": channel, "range_ms": [cursor, start]})
            cursor = max(cursor, end)
        if cursor < duration:
            gaps.append({"channel": channel, "range_ms": [cursor, duration]})
    return {"schema": "ace.media.brand-audit.v1", "policy_sha256": expected,
            "annotations_sha256": annotation_anchor, "asset_sha256": asset,
            "scope": "annotated_tracks", "findings": findings, "coverage_gaps": gaps,
            "status": "hold" if findings or gaps else "eligible_on_annotated_tracks"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy", type=Path)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    parser.add_argument("--annotation-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = audit(decode(read(args.policy)), args.expect_sha256,
                       decode(read(args.annotations)), args.annotation_sha256)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return int(report["status"] == "hold")


if __name__ == "__main__":
    raise SystemExit(main())
