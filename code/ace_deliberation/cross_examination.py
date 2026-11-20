"""Jaga tanya silang tetap mengarah ke klaim tertentu dan jawaban berjejak.

Sesi memproses pertanyaan dan jawaban menurut urutan rekaman. Hanya pengaju
klaim yang boleh menjawab. Penundaan tetap terlihat sebagai pertanyaan
terbuka, dan konsesi tersimpan terpisah dari jawaban berlandaskan bukti.
"""
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path


CATEGORIES = ("scope", "measurement", "counterexample", "provenance")
MAX_CLAIMS = 1_000
MAX_EVENTS = 8_000
MAX_BYTES = 8_000_000


class ExaminationError(ValueError):
    """Pertanyaan atau jawaban tidak dapat ditambatkan pada sesi."""


def _record(value, keys):
    if not isinstance(value, dict) or value.keys() != set(keys):
        raise ExaminationError("Field pemeriksaan tidak sesuai skema.")


def _text(value, label, limit=96):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise ExaminationError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ExaminationError(f"{label} bukan teks UTF-8 yang sah.") from exc
    return value.strip()


def _refs(values):
    if not isinstance(values, list) or len(values) > 100:
        raise ExaminationError("Rujukan bukti wajib larik berbatas.")
    refs = [_text(value, "rujukan bukti", 512) for value in values]
    if len(set(refs)) != len(refs):
        raise ExaminationError("Rujukan bukti ganda.")
    return sorted(refs)


@dataclass(frozen=True, slots=True)
class Claim:
    id: str
    claimant: str
    description: str
    source: str

    @classmethod
    def from_dict(cls, raw):
        _record(raw, ("id", "claimant", "description", "source_ref"))
        return cls(_text(raw["id"], "klaim"), _text(raw["claimant"], "pengaju"),
                   _text(raw["description"], "isi klaim", 5_000), _text(raw["source_ref"], "sumber", 512))

    def as_dict(self):
        return {"id": self.id, "claimant": self.claimant, "description": self.description, "source_ref": self.source}


class CrossExamination:
    def __init__(self, claims):
        if not isinstance(claims, list) or not 1 <= len(claims) <= MAX_CLAIMS:
            raise ExaminationError("Sesi memerlukan daftar klaim berbatas.")
        parsed = [Claim.from_dict(claim) for claim in claims]
        self._claims = {claim.id: claim for claim in parsed}
        self._sources = {claim.source for claim in parsed}
        if len(self._claims) != len(parsed) or len(self._sources) != len(parsed):
            raise ExaminationError("ID atau rujukan klaim ganda.")
        self._events = {}
        self._questions = {}
        self._responses = {}

    def submit(self, raw):
        if len(self._events) >= MAX_EVENTS:
            raise ExaminationError("Sesi melampaui batas event.")
        if not isinstance(raw, dict) or raw.get("kind") not in ("question", "response"):
            raise ExaminationError("Jenis event tanya silang tidak dikenal.")
        common = ("id", "kind", "actor", "text", "source_ref")
        fields = ("claim_id", "category") if raw["kind"] == "question" else (
            "question_id", "disposition", "evidence_refs")
        _record(raw, common + fields)
        event = {key: _text(raw[key], label, limit) for key, label, limit in (
            ("id", "ID event", 96), ("actor", "aktor", 96), ("text", "isi", 5_000),
            ("source_ref", "sumber", 512),
        )}
        event["kind"] = raw["kind"]
        if event["id"] in self._events or event["source_ref"] in self._sources:
            raise ExaminationError("ID atau rujukan event ganda.")
        if raw["kind"] == "question":
            self._validate_question(event, raw)
            self._questions[event["id"]] = event
            self._responses[event["id"]] = []
        else:
            self._validate_response(event, raw)
            self._responses[event["question_id"]].append(event["id"])
        self._events[event["id"]] = event
        self._sources.add(event["source_ref"])
        return event["id"]

    def _validate_question(self, event, raw):
        claim = _text(raw["claim_id"], "ID klaim")
        if claim not in self._claims:
            raise ExaminationError("Pertanyaan menunjuk klaim yang tidak ada.")
        if event["actor"] == self._claims[claim].claimant:
            raise ExaminationError("Pengaju tidak boleh menjadi penanya untuk klaimnya sendiri.")
        category = raw["category"]
        if category not in CATEGORIES:
            raise ExaminationError("Kategori pertanyaan tidak dikenal.")
        event.update(claim_id=claim, category=category)

    def _validate_response(self, event, raw):
        question_id = _text(raw["question_id"], "ID pertanyaan")
        if question_id not in self._questions:
            raise ExaminationError("Jawaban mendahului pertanyaannya.")
        claim = self._claims[self._questions[question_id]["claim_id"]]
        if event["actor"] != claim.claimant:
            raise ExaminationError("Jawaban wajib berasal dari pengaju klaim.")
        if self._question_status(question_id) in ("answered", "conceded"):
            raise ExaminationError("Pertanyaan sudah memiliki jawaban terminal.")
        disposition = raw["disposition"]
        if disposition not in ("answered", "conceded", "deferred"):
            raise ExaminationError("Status jawaban tidak dikenal.")
        refs = _refs(raw["evidence_refs"])
        if disposition == "answered" and not refs:
            raise ExaminationError("Jawaban substantif perlu rujukan bukti.")
        event.update(question_id=question_id, disposition=disposition, evidence_refs=refs)

    def _question_status(self, identifier):
        answers = self._responses[identifier]
        return self._events[answers[-1]]["disposition"] if answers else "awaiting"

    def report(self):
        questions = []
        counts = {identifier: Counter() for identifier in self._claims}
        for identifier, row in self._questions.items():
            evidence = sorted({ref for response in self._responses[identifier]
                               for ref in self._events[response]["evidence_refs"]})
            status = self._question_status(identifier)
            counts[row["claim_id"]][status] += 1
            questions.append({
                "question_id": identifier, "claim_id": row["claim_id"], "category": row["category"],
                "question_ref": row["source_ref"], "status": status,
                "response_refs": [self._events[response]["source_ref"] for response in self._responses[identifier]],
                "evidence_refs": evidence,
            })
        return {
            "schema": "ace.cross-examination.v1",
            "claims": [
                {**self._claims[key].as_dict(), "question_counts": {
                    state: counts[key][state] for state in ("awaiting", "deferred", "answered", "conceded")
                }}
                for key in sorted(self._claims)
            ],
            "questions": questions,
            "unresolved": [row["question_id"] for row in questions if row["status"] in ("awaiting", "deferred")],
            "concessions": [row["question_id"] for row in questions if row["status"] == "conceded"],
            "events": [{key: val.copy() if isinstance(val, list) else val for key, val in row.items()}
                       for row in self._events.values()],
        }


def examine(raw):
    _record(raw, ("claims", "events"))
    if not isinstance(raw["events"], list) or len(raw["events"]) > MAX_EVENTS:
        raise ExaminationError("Daftar event melampaui batas.")
    session = CrossExamination(raw["claims"])
    for event in raw["events"]:
        session.submit(event)
    return session.report()


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.case.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ExaminationError("Berkas tanya silang melampaui batas.")
        report = examine(json.loads(data))
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
