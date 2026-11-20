"""Ambil preseden yang benar-benar tersedia untuk membatasi analogi putusan.

Indeks dibangun dari arsip yang diberikan pemanggil. Pencarian memakai irisan
tag dan istilah dengan tie-break tanggal dan ID. Kasus dengan outcome lain
tetap terlihat. Setiap hasil menampilkan rujukan arsip dan kondisi yang
belum terpenuhi di kasus baru.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from fractions import Fraction
import json
from pathlib import Path
import re
import unicodedata


MAX_CASES = 8_000
MAX_BYTES = 20_000_000
OUTCOMES = frozenset({"adopt", "reject", "defer"})
_TOKEN = re.compile(r"[^\W_]+", flags=re.UNICODE)
_COMMON = frozenset({"di", "ke", "dan", "atau", "untuk", "dari", "yang", "oleh", "ini",
                     "itu", "the", "a", "an", "is", "of", "to", "and", "or", "in"})


class PrecedentError(ValueError):
    """Arsip atau permintaan belum layak ditelusuri."""


def _fields(raw, required):
    if not isinstance(raw, dict) or raw.keys() != set(required):
        raise PrecedentError("Field preseden tidak sesuai skema.")


def _text(value, label, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\0" in value:
        raise PrecedentError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise PrecedentError(f"{label} bukan teks UTF-8 yang sah.") from exc
    return value.strip()


def _normalized(value):
    return unicodedata.normalize("NFKC", value).casefold()


def _terms(text):
    return frozenset(word for word in _TOKEN.findall(_normalized(text))
                     if len(word) >= 2 and word not in _COMMON)


def _string_set(value, label, *, normalize=True):
    if not isinstance(value, list) or len(value) > 100:
        raise PrecedentError(f"{label} harus larik berbatas.")
    values = [_text(item, label, 512) for item in value]
    if normalize:
        values = [_normalized(item) for item in values]
    if len(set(values)) != len(values):
        raise PrecedentError(f"{label} ganda.")
    return frozenset(values)


def _date(value):
    if not isinstance(value, str):
        raise PrecedentError("Tanggal wajib YYYY-MM-DD.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise PrecedentError("Tanggal tidak sah.") from exc
    if parsed.isoformat() != value:
        raise PrecedentError("Tanggal wajib YYYY-MM-DD.")
    return parsed


def _outcome(value, *, required):
    if not required and value is None:
        return None
    if not isinstance(value, str) or value not in OUTCOMES:
        raise PrecedentError("Outcome preseden tidak dikenal.")
    return value


@dataclass(frozen=True, slots=True)
class Case:
    case_id: str
    decided_on: date
    issue: str
    tags: frozenset[str]
    terms: frozenset[str]
    conditions: frozenset[str]
    outcome: str
    source_ref: str
    evidence_refs: frozenset[str]

    @classmethod
    def from_dict(cls, row):
        _fields(row, ("case_id", "decided_on", "issue", "tags", "conditions",
                      "outcome", "source_ref", "evidence_refs"))
        issue = _text(row["issue"], "isu", 4_000)
        tags = _string_set(row["tags"], "tag")
        refs = _string_set(row["evidence_refs"], "bukti", normalize=False)
        if not refs:
            raise PrecedentError("Preseden wajib menyertakan rujukan bukti.")
        return cls(_text(row["case_id"], "case_id", 96), _date(row["decided_on"]), issue,
                   tags, _terms(issue), _string_set(row["conditions"], "kondisi"),
                   _outcome(row["outcome"], required=True), _text(row["source_ref"], "sumber", 512), refs)


@dataclass(frozen=True, slots=True)
class Query:
    as_of: date
    tags: frozenset[str]
    terms: frozenset[str]
    conditions: frozenset[str]
    proposed_outcome: str | None
    limit: int

    @classmethod
    def from_dict(cls, row):
        _fields(row, ("as_of", "issue", "tags", "conditions", "proposed_outcome", "limit"))
        tags = _string_set(row["tags"], "tag permintaan")
        terms = _terms(_text(row["issue"], "isu permintaan", 4_000))
        if not tags and not terms:
            raise PrecedentError("Pencarian perlu tag atau istilah bermakna.")
        if type(row["limit"]) is not int or not 1 <= row["limit"] <= 50:
            raise PrecedentError("limit harus bilangan bulat 1–50.")
        return cls(_date(row["as_of"]), tags, terms, _string_set(row["conditions"], "kondisi permintaan"),
                   _outcome(row["proposed_outcome"], required=False), row["limit"])


def _similarity(left, right):
    total = len(left | right)
    return Fraction(len(left & right), total) if total else Fraction(0)


def _result(case, query, score):
    unresolved = sorted(case.conditions - query.conditions)
    if query.proposed_outcome is None:
        relation = "unset"
    elif case.outcome == query.proposed_outcome:
        relation = "same_outcome"
    else:
        relation = "different_outcome"
    return {"case_id": case.case_id, "decided_on": case.decided_on.isoformat(),
            "issue": case.issue, "outcome": case.outcome, "relation": relation,
            "source_ref": case.source_ref, "evidence_refs": sorted(case.evidence_refs),
            "matched_tags": sorted(case.tags & query.tags), "matched_terms": sorted(case.terms & query.terms),
            "conditions_missing": unresolved, "applicable_conditions": not unresolved,
            "match_score": {"numerator": score.numerator, "denominator": score.denominator}}


class PrecedentMemory:
    """Lakukan pencarian reproduksibel tanpa mengisi kekosongan arsip dengan kasus baru."""

    def __init__(self, records):
        if not isinstance(records, list) or len(records) > MAX_CASES:
            raise PrecedentError("Arsip bukan larik kasus berbatas.")
        parsed = tuple(Case.from_dict(record) for record in records)
        if len({case.case_id for case in parsed}) != len(parsed):
            raise PrecedentError("ID kasus ganda.")
        self._cases = {case.case_id: case for case in parsed}
        self._by_tag = defaultdict(set)
        self._by_term = defaultdict(set)
        for case in parsed:
            for tag in case.tags:
                self._by_tag[tag].add(case.case_id)
            for term in case.terms:
                self._by_term[term].add(case.case_id)

    def search(self, request):
        query = Query.from_dict(request)
        candidates = set()
        for tag in query.tags:
            candidates.update(self._by_tag.get(tag, ()))
        for term in query.terms:
            candidates.update(self._by_term.get(term, ()))
        ranked = []
        for identifier in candidates:
            case = self._cases[identifier]
            if case.decided_on >= query.as_of:
                continue
            score = 2 * _similarity(case.tags, query.tags) + _similarity(case.terms, query.terms)
            if score:
                ranked.append((score, case))
        ranked.sort(key=lambda pair: (-pair[0], -pair[1].decided_on.toordinal(), pair[1].case_id))
        winners = [_result(case, query, score) for score, case in ranked[:query.limit]]
        opposite = next(((score, case) for score, case in ranked
                         if query.proposed_outcome is not None and case.outcome != query.proposed_outcome),
                        None)
        return {
            "schema": "ace.precedent-memory.v1", "as_of": query.as_of.isoformat(),
            "matches_seen": len(ranked), "matches": winners,
            "best_different_outcome": _result(opposite[1], query, opposite[0]) if opposite else None,
        }


def _read(path):
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise PrecedentError("Berkas melampaui batas masukan.")
    return json.loads(data)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("query", type=Path)
    args = parser.parse_args(argv)
    try:
        result = PrecedentMemory(_read(args.archive)).search(_read(args.query))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
