"""Tautkan putusan pada versi ramalan dan tandai saat dasarnya perlu diulas.

Setiap kait memiliki syarat probabilitas. Auditor membandingkan ramalan
yang benar-benar dirujuk pada tanggal putusan dengan ramalan terakhir
yang tersedia. File lama, versi masa depan, dan rujukan dangling tetap
terlihat. Keluaran menandai review dan tidak mengganti putusan.
"""
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
import json
from pathlib import Path

from .brier_scorer import _probability, _rational, _stamp


MAX_ROWS = 10_000
MAX_BYTES = 12_000_000


class LinkError(ValueError):
    """Versi ramalan, putusan, atau tautan tidak memenuhi skema."""


def _shape(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise LinkError("Field tautan keputusan tidak sesuai skema.")


def _text(value, label, maximum=160):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\0" in value:
        raise LinkError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise LinkError(f"{label} bukan teks UTF-8.") from exc
    return value.strip()


def _rows(raw, maximum, minimum=0):
    if not isinstance(raw, list) or not minimum <= len(raw) <= maximum:
        raise LinkError("Jumlah record tautan di luar batas.")
    return raw


@dataclass(frozen=True, slots=True)
class Version:
    question_id: str
    ref: str
    at: datetime
    expires: datetime
    p: Fraction

    @classmethod
    def from_dict(cls, raw):
        _shape(raw, ("question_id", "forecast_ref", "forecast_at", "expires_at", "probability"))
        began, expired = _stamp(raw["forecast_at"]), _stamp(raw["expires_at"])
        if expired <= began:
            raise LinkError("Masa berlaku ramalan kosong atau terbalik.")
        return cls(_text(raw["question_id"], "pertanyaan"),
                   _text(raw["forecast_ref"], "rujukan ramalan", 512),
                   began, expired, _probability(raw["probability"]))

    def export(self):
        return {"question_id": self.question_id, "forecast_ref": self.ref,
                "forecast_at": self.at.isoformat(), "expires_at": self.expires.isoformat(),
                "probability": _rational(self.p)}


def _condition(kind, p, threshold):
    return p >= threshold if kind == "at_least" else p <= threshold


def _latest_at(history, at):
    if history is None:
        return None
    stamps, versions = history
    position = bisect_right(stamps, at)
    return versions[position - 1] if position else None


def _link(raw, versions, timelines, decided, now):
    _shape(raw, ("forecast_ref", "comparison", "threshold"))
    ref = _text(raw["forecast_ref"], "rujukan ketergantungan", 512)
    kind = raw["comparison"]
    if kind not in ("at_least", "at_most"):
        raise LinkError("Pembanding ambang harus at_least atau at_most.")
    threshold = _probability(raw["threshold"])
    cited = versions.get(ref)
    history = timelines.get(cited.question_id) if cited is not None else None
    current = _latest_at(history, now)
    latest_at_decision = _latest_at(history, decided)
    if cited is None:
        reason = "dangling_reference"
    elif cited.at > decided:
        reason = "forecast_after_decision"
    elif decided >= cited.expires:
        reason = "expired_at_decision"
    elif not _condition(kind, cited.p, threshold):
        reason = "unsupported_at_decision"
    elif latest_at_decision is not None and latest_at_decision.ref != cited.ref:
        reason = "superseded_at_decision"
    elif current is None or now >= current.expires:
        reason = "forecast_expired"
    elif not _condition(kind, current.p, threshold):
        reason = "threshold_crossed"
    elif cited.ref != current.ref:
        reason = "updated_same_side"
    else:
        reason = "current"
    return {
        "cited_ref": ref, "comparison": kind, "threshold": _rational(threshold),
        "cited_forecast": cited.export() if cited is not None else None,
        "latest_at_decision": latest_at_decision.export() if latest_at_decision is not None else None,
        "current_forecast": current.export() if current is not None else None,
        "status": reason, "needs_review": reason not in ("current", "updated_same_side"),
    }


def assess_links(raw):
    _shape(raw, ("as_of", "forecasts", "decisions"))
    now = _stamp(raw["as_of"])
    versions = {}
    by_question = defaultdict(list)
    times = set()
    for item in _rows(raw["forecasts"], MAX_ROWS):
        version = Version.from_dict(item)
        key = version.question_id, version.at
        if version.ref in versions or key in times or version.at > now:
            raise LinkError("Versi ramalan ganda atau melampaui as_of.")
        versions[version.ref] = version
        times.add(key)
        by_question[version.question_id].append(version)
    timelines = {}
    for question, rows in by_question.items():
        ordered = sorted(rows, key=lambda item: item.at)
        timelines[question] = ([item.at for item in ordered], ordered)

    assessments = {}
    reverse_lookup = defaultdict(set)
    source_refs = set()
    for decision in _rows(raw["decisions"], MAX_ROWS):
        _shape(decision, ("id", "source_ref", "decided_at", "dependencies"))
        identifier = _text(decision["id"], "ID keputusan")
        ref = _text(decision["source_ref"], "sumber keputusan", 512)
        at = _stamp(decision["decided_at"])
        if identifier in assessments or ref in source_refs or ref in versions or at > now:
            raise LinkError("ID/sumber keputusan ganda atau keputusan dari masa depan.")
        records = [_link(row, versions, timelines, at, now) for row in _rows(decision["dependencies"], 100, 1)]
        if len({row["cited_ref"] for row in records}) != len(records):
            raise LinkError("Satu versi ramalan dirujuk dua kali dalam putusan yang sama.")
        for row in records:
            if row["cited_forecast"] is not None:
                reverse_lookup[row["cited_forecast"]["question_id"]].add(identifier)
        assessments[identifier] = {
            "id": identifier, "source_ref": ref, "decided_at": at.isoformat(),
            "status": "review_required" if any(row["needs_review"] for row in records) else "supported",
            "links": sorted(records, key=lambda row: row["cited_ref"]),
        }
        source_refs.add(ref)
    return {"schema": "ace.decision-linker.v1", "as_of": now.isoformat(),
            "decisions": [assessments[key] for key in sorted(assessments)],
            "affected_by_forecast": {key: sorted(ids) for key, ids in sorted(reverse_lookup.items())}}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise LinkError("Masukan tautan melampaui batas.")
        result = assess_links(json.loads(data))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(any(row["status"] == "review_required" for row in result["decisions"]))


if __name__ == "__main__":
    raise SystemExit(main())
