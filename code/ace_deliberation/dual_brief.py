"""Buat brief teknis dan awam dari satu catatan putusan yang terverifikasi.

Kalimat awam memakai penggantian istilah dari glosarium bersumber.
Penggantian berjalan satu kali agar istilah tidak berubah berantai.
Setiap angka literal dan pointer bukti dipertahankan. Hasil tetap
bersandar pada makna glosarium yang diberikan pemanggil.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from .decision_brief import MAX_INPUT_BYTES, _escape, make_brief, render_markdown


MAX_TERMS = 150
_NUMBERS = re.compile(r"[+-]?\d+(?:[.,]\d+)*%?")


class DualBriefError(ValueError):
    """Glosarium atau keputusan tidak dapat dirender secara konsisten."""


def _shape(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise DualBriefError("Field brief ganda tidak sesuai skema.")


def _label(value, name, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or not value.isprintable():
        raise DualBriefError(f"{name} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise DualBriefError(f"{name} bukan teks UTF-8.") from exc
    return value.strip()


def _glossary(rows):
    if not isinstance(rows, list) or len(rows) > MAX_TERMS:
        raise DualBriefError("Jumlah entri glosarium melampaui batas.")
    terms, sources = {}, set()
    for row in rows:
        _shape(row, ("term", "plain", "source_ref"))
        term = _label(row["term"], "istilah teknis", 100)
        plain = _label(row["plain"], "istilah awam", 500)
        source_ref = _label(row["source_ref"], "sumber glosarium", 512)
        if term.casefold() in terms or source_ref in sources or term.casefold() == plain.casefold():
            raise DualBriefError("Istilah atau rujukan glosarium ganda atau padanan tidak berubah.")
        if _NUMBERS.findall(term) != _NUMBERS.findall(plain):
            raise DualBriefError("Glosarium mengubah angka literal.")
        terms[term.casefold()] = {"term": term, "plain": plain, "source_ref": source_ref}
        sources.add(source_ref)
    return terms


def _rewrite(text, lookup, pattern, count):
    if pattern is None:
        return text

    def replacement(match):
        entry = lookup.get(match.group().casefold())
        if entry is None:
            # Unicode regex mengakui beberapa bentuk huruf yang casefold-nya berbeda.
            return match.group()
        count[entry["term"]] += 1
        return entry["plain"]

    plain = pattern.sub(replacement, text)
    if _NUMBERS.findall(text) != _NUMBERS.findall(plain):
        raise DualBriefError("Parafrasa mengubah angka literal setelah penempatan.")
    return plain


def create_dual(raw):
    _shape(raw, ("brief_input", "glossary"))
    tech = make_brief(raw["brief_input"])
    lexicon = _glossary(raw["glossary"])
    ordered = sorted((entry["term"] for entry in lexicon.values()), key=lambda term: (-len(term), term))
    pattern = re.compile(r"(?<!\w)(?:" + "|".join(map(re.escape, ordered)) + r")(?!\w)", re.I) if ordered else None
    hits = dict.fromkeys(ordered, 0)

    trace = []

    def restate(text, location):
        counts = Counter()
        plain = _rewrite(text, lexicon, pattern, counts)
        if counts:
            for term, amount in counts.items():
                hits[term] += amount
            trace.append({
                "location": location, "glossary_hits": dict(sorted(counts.items())),
                "numbers": _NUMBERS.findall(text),
                "technical_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "plain_sha256": hashlib.sha256(plain.encode("utf-8")).hexdigest(),
            })
        return plain

    def turn(item, area):
        return {**item, "statement": restate(item["statement"], f"{area}/{item['source']['turn_id']}"),
                "evidence_refs": item["evidence_refs"].copy(), "source": item["source"].copy()}

    plain = {
        "debate_id": tech["debate_id"], "debate_sha256": tech["debate_sha256"], "outcome": tech["outcome"],
        "question": restate(tech["question"], "question"),
        "reason_recorded": restate(tech["reason_recorded"], "reason_recorded"),
        "basis": [turn(item, "basis") for item in tech["basis"]],
        "dissent": [{**turn(item, "dissent"), "responses": [
            turn(reply, f"dissent/{item['source']['turn_id']}/response") for reply in item["responses"]
        ]} for item in tech["dissent"]],
        "precedent_status": tech["precedent_status"], "precedent": deepcopy(tech["precedent"]),
        "different_outcome_precedent": deepcopy(tech["different_outcome_precedent"]),
        "reference_index": deepcopy(tech["reference_index"]),
    }
    used = [{**lexicon[term.casefold()], "uses": hits[term]} for term in sorted(ordered) if hits[term]]
    return {"schema": "ace.dual-brief.v1", "technical": tech, "plain": plain,
            "rewrite_trace": trace, "glossary_used": used,
            "glossary_unused": sorted(term for term in ordered if not hits[term])}


def render_plain(report):
    plain = report["plain"]
    lines = [
        "# Brief putusan · versi awam", "",
        f"**Apa yang dibahas** — {_escape(plain['question'])}", "",
        f"**Putusan tercatat** — {plain['outcome']}", "",
        f"**Alasan yang dicatat** — {_escape(plain['reason_recorded'])}", "",
        "## Dasar putusan", "",
    ]
    for row in plain["basis"]:
        lines.append(f"- {_escape(row['statement'])} · giliran {_escape(row['source']['turn_id'])}")
    lines.extend(("", "## Sanggahan", ""))
    for row in plain["dissent"]:
        lines.append(f"- {_escape(row['statement'])} · giliran {_escape(row['source']['turn_id'])}")
        for reply in row["responses"]:
            lines.append(f"  - Tanggapan — {_escape(reply['statement'])} · giliran {_escape(reply['source']['turn_id'])}")
        if not row["responses"]:
            lines.append("  - Tanggapan belum tercatat.")
    lines.extend(("", "## Putusan terdahulu", ""))
    prior = plain["precedent"]
    if prior is None:
        lines.append("Kondisi arsip belum memberi preseden yang sesuai.")
    else:
        lines.append(f"- {_escape(prior['case_id'])} · {prior['decided_on']} — {_escape(prior['source_ref'])}")
    alternate = plain["different_outcome_precedent"]
    if alternate is not None:
        lines.append(f"- Putusan berbeda — {_escape(alternate['case_id'])} · {_escape(alternate['source_ref'])}")
    lines.extend(("", f"SHA-256 transcript — `{plain['debate_sha256']}`"))
    for ref in plain["reference_index"]:
        lines.append(f"- Rujukan — {_escape(ref['source_ref'])}")
    for item in report["glossary_used"]:
        lines.append(f"- Istilah {_escape(item['term'])} — {_escape(item['plain'])} · {_escape(item['source_ref'])}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--format", choices=("json", "technical", "plain"), default="json")
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            payload = handle.read(MAX_INPUT_BYTES + 1)
        if len(payload) > MAX_INPUT_BYTES:
            raise DualBriefError("Masukan brief melampaui batas.")
        result = create_dual(json.loads(payload))
        if args.format == "plain":
            print(render_plain(result), end="")
        elif args.format == "technical":
            print(render_markdown(result["technical"]), end="")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
