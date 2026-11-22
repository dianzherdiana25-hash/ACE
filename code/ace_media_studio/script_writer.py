"""Susun naskah video yang menautkan klaim narasi ke kartu sumber."""
import argparse
from hashlib import sha256
from pathlib import Path
import re
import sys

from ._contracts import (ContractError, canonical, checked, decode, entries, identifier,
                         integer, obj, read, schema, text)


WORDS = re.compile(r"[^\W_]+", re.UNICODE)
CONNECTORS = {
    "hook": "Mari kita lihat",
    "context": "Sebagai konteks:",
    "evidence": "Catatan sumber:",
    "closing": "Poin yang perlu diingat:",
}


def _key_words(raw):
    return {token.casefold() for token in WORDS.findall(raw) if len(token) >= 3}


def _cost(raw, words_per_minute):
    return (len(WORDS.findall(raw)) * 60_000 + words_per_minute - 1) // words_per_minute


def write_script(plan, expected):
    checked(plan, expected)
    schema(plan, "ace.media.script-plan.v1", ("topic", "audience", "length_ms", "words_per_minute", "cards"))
    topic = text(plan["topic"], "Topik", 100)
    audience = text(plan["audience"], "Audiens", 100)
    limit = integer(plan["length_ms"], "Durasi", 1000, 120_000)
    words_per_minute = integer(plan["words_per_minute"], "Kata per menit", 70, 240)
    keys = _key_words(topic)
    by_kind = {kind: [] for kind in CONNECTORS}
    seen = set()
    plan_cards = entries(plan["cards"], 50, 3)
    for card in plan_cards:
        obj(card, ("id", "kind", "body", "source_ref", "visual", "rank", "topics"))
        key = identifier(card["id"], "Kartu")
        if key in seen or card["kind"] not in by_kind:
            raise ContractError("ID kartu ganda atau peran narasi tidak sah.")
        seen.add(key)
        fact = text(card["body"], "Pernyataan sumber", 420)
        source = text(card["source_ref"], "Pointer sumber")
        visual = text(card["visual"], "Arahan visual")
        rank = integer(card["rank"], "Prioritas sumber", 0, 1000)
        tagged = {word for value in entries(card["topics"], 12, 1)
                  for word in _key_words(text(value, "Tag topik", 50))}
        coverage = len(keys & tagged)
        if coverage:
            by_kind[card["kind"]].append((-coverage, -rank, key, fact, source, visual))
    for cards in by_kind.values():
        cards.sort()

    selected = {}
    for kind in ("hook", "context", "closing"):
        if not by_kind[kind]:
            raise ContractError(f"Kartu relevan untuk {kind} belum tersedia.")
        selected[kind] = by_kind[kind][0]
    title = f"{CONNECTORS['hook']} {topic}."
    required = sum(_cost(f"{CONNECTORS[kind]} {selected[kind][3]}", words_per_minute)
                   for kind in ("context", "closing"))
    required += _cost(f"{title} {selected['hook'][3]}", words_per_minute)
    if required > limit:
        raise ContractError("Kartu narasi wajib melebihi durasi.")
    evidence = []
    for row in by_kind["evidence"]:
        cost = _cost(f"{CONNECTORS['evidence']} {row[3]}", words_per_minute)
        if required + cost <= limit:
            evidence.append(row)
            required += cost
    if not evidence:
        raise ContractError("Naskah membutuhkan kartu bukti relevan yang muat dalam durasi.")
    ordered = [("hook", selected["hook"]), ("context", selected["context"]),
               *[("evidence", row) for row in evidence], ("closing", selected["closing"])]
    start = 0
    beats = []
    for kind, (_, _, key, body, source, visual) in ordered:
        narration = f"{title if kind == 'hook' else CONNECTORS[kind]} {body}"
        duration = _cost(narration, words_per_minute)
        beats.append({"kind": kind, "card_id": key, "source_ref": source, "visual": visual,
                      "narration": narration, "source_excerpt_sha256": sha256(body.encode()).hexdigest(),
                      "start_ms": start, "end_ms": start + duration})
        start += duration
    used = {item["card_id"] for item in beats}
    return {"schema": "ace.media.script.v1", "plan_sha256": expected, "topic": topic,
            "audience": audience, "duration_ms": start, "duration_method": "estimated_from_words_per_minute",
            "unused_cards": sorted(seen - used), "beats": beats}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = write_script(decode(read(args.plan)), args.expect_sha256)
        sys.stdout.buffer.write(canonical(report) + b"\n")
    except (OSError, ValueError, TypeError, RecursionError) as error:
        parser.exit(2, f"Error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
