"""Simpan kasus ramalan beserta pelajaran dan rujukan yang bisa ditelaah.

Pencarian bersifat eksak pada tag dan pemisahan train/held-out. Tanggal
akses membatasi kasus dan pelajarannya ke informasi yang sudah tersedia.
Identitas peristiwa menjaga satu kasus tidak disalin lintas partisi.
"""
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json

from ._advanced import InputError, integer, json_main, labels, rows, shape, stamp, text, unique
from .brier_scorer import _outcome


MAX_CASES = 10_000
PARTITIONS = ("training", "held_out")
ORIGINS = ("historical", "synthetic")


def _digest(values):
    buf = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(buf).hexdigest()


@dataclass(frozen=True, slots=True)
class Case:
    key: str
    event_id: str
    title: str
    question_ref: str
    resolution_ref: str
    available: datetime
    outcome: int
    tags: tuple
    partition: str
    origin: str
    lesson: str | None
    lesson_ref: str | None
    lesson_at: datetime | None

    @classmethod
    def read(cls, raw):
        shape(raw, ("case_id", "event_id", "title", "question_ref", "resolution_ref",
                    "available_at", "outcome", "tags", "partition", "origin", "lesson"))
        partition = text(raw["partition"], "partisi")
        origin = text(raw["origin"], "jenis asal")
        if partition not in PARTITIONS or origin not in ORIGINS:
            raise InputError("Partisi atau asal kasus tak dikenal.")
        available = stamp(raw["available_at"])
        lesson_raw = raw["lesson"]
        lesson = lesson_ref = lesson_at = None
        if lesson_raw is not None:
            shape(lesson_raw, ("text", "ref", "available_at"))
            lesson = text(lesson_raw["text"], "pelajaran", 2000)
            lesson_ref = text(lesson_raw["ref"], "sumber pelajaran")
            lesson_at = stamp(lesson_raw["available_at"])
            if lesson_at < available:
                raise InputError("Pelajaran resolusi mendahului kasus.")
        return cls(text(raw["case_id"], "ID kasus"), text(raw["event_id"], "ID peristiwa"),
                   text(raw["title"], "judul", 300), text(raw["question_ref"], "sumber pertanyaan"),
                   text(raw["resolution_ref"], "sumber resolusi"), available, _outcome(raw["outcome"]),
                   tuple(sorted(labels(raw["tags"], 1, 30, "tag"))), partition, origin,
                   lesson, lesson_ref, lesson_at)

    def export(self, *, as_of):
        lesson = None
        if self.lesson_at is not None and self.lesson_at <= as_of:
            lesson = {"text": self.lesson, "ref": self.lesson_ref, "available_at": self.lesson_at.isoformat()}
        return {
            "case_id": self.key, "event_id": self.event_id, "title": self.title,
            "question_ref": self.question_ref, "resolution_ref": self.resolution_ref,
            "available_at": self.available.isoformat(), "outcome": self.outcome, "tags": list(self.tags),
            "partition": self.partition, "origin": self.origin, "lesson": lesson,
        }


def lookup(raw):
    shape(raw, ("library_ref", "cases", "query"))
    library_ref = text(raw["library_ref"], "sumber pustaka")
    query = raw["query"]
    shape(query, ("tags", "partition", "origin", "as_of", "limit"))
    tags = sorted(labels(query["tags"], 0, 30, "tag pencarian"))
    tag_set = set(tags)
    partition = text(query["partition"], "partisi pencarian")
    origin = text(query["origin"], "jenis asal pencarian")
    if partition not in PARTITIONS or origin not in (*ORIGINS, "any"):
        raise InputError("Partisi atau asal pencarian tak dikenal.")
    cutoff = stamp(query["as_of"])
    limit = integer(query["limit"], 1, 1000)

    by_case, by_event = {}, {}
    refs = {library_ref}
    duplicates = Counter()
    for record in rows(raw["cases"], 0, MAX_CASES):
        case = Case.read(record)
        previous = by_case.get(case.key)
        if previous is not None:
            if previous != case:
                raise InputError(f"Versi kasus {case.key} bertentangan.")
            duplicates[case.key] += 1
            continue
        if case.event_id in by_event:
            raise InputError(f"Peristiwa {case.event_id} dipakai lebih dari satu kasus.")
        for ref in (case.question_ref, case.resolution_ref, case.lesson_ref):
            if ref is not None:
                unique(ref, refs)
        by_case[case.key] = case
        by_event[case.event_id] = case.key
    available = [case for case in by_case.values() if case.partition == partition and case.available <= cutoff
                 and (origin == "any" or case.origin == origin)]
    matches = [case for case in available if tag_set.issubset(case.tags)]
    # Urutan stabil dengan waktu terbaru dulu dan ID naik pada timestamp seri.
    matches.sort(key=lambda case: case.key)
    matches.sort(key=lambda case: case.available, reverse=True)
    snapshot = [case.export(as_of=cutoff) for case in sorted(available, key=lambda item: item.key)]
    return {
        "schema": "ace.forecast-case-library.v1", "library_ref": library_ref,
        "query": {"tags": tags, "partition": partition, "origin": origin, "as_of": cutoff.isoformat(), "limit": limit},
        "available_count": len(available), "snapshot_sha256": _digest(snapshot),
        "duplicate_records": [{"case_id": case.key, "extra_copies": duplicates[case.key]}
                              for case in sorted(available, key=lambda item: item.key) if duplicates[case.key]],
        "matched_count": len(matches), "truncated_count": max(0, len(matches) - limit),
        "results": [case.export(as_of=cutoff) for case in matches[:limit]],
    }


def main(argv=None):
    return json_main(argv, __doc__, lookup)


if __name__ == "__main__":
    raise SystemExit(main())
