"""Buka peninjauan putusan hanya lewat banding yang memiliki bukti baru.

Berkas banding membedakan putusan asal, bukti, dan hasil ulasan. Hash
yang sudah tercatat pada putusan tidak bisa diajukan lagi dengan nama
berkas baru. Ulasan menerima kewenangan dari roster yang dinyatakan
pemanggil dan mempertahankan putusan awal sebagai riwayat.
"""
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re

from .brier_scorer import _stamp


MAX_EVIDENCE = 300
MAX_BYTES = 6_000_000
_DIGEST = re.compile(r"[0-9a-f]{64}")


class AppealError(ValueError):
    """Banding atau ulasan menyimpang dari catatan kewenangan."""


def _shape(raw, required):
    if not isinstance(raw, dict) or raw.keys() != set(required):
        raise AppealError("Field banding menyimpang dari skema.")


def _text(raw, name, limit):
    if not isinstance(raw, str) or not raw.strip() or len(raw) > limit or "\0" in raw:
        raise AppealError(f"{name} tidak sah.")
    try:
        raw.encode("utf-8")
    except UnicodeError as exc:
        raise AppealError(f"{name} bukan teks UTF-8.") from exc
    return raw.strip()


def _refs(raw, label):
    if not isinstance(raw, list) or len(raw) > MAX_EVIDENCE:
        raise AppealError(f"{label} harus berupa larik berbatas.")
    refs = [_text(value, label, 512) for value in raw]
    if len(set(refs)) != len(refs):
        raise AppealError(f"{label} memuat rujukan ganda.")
    return sorted(refs)


def _timestamp(raw):
    try:
        return _stamp(raw)
    except ValueError as exc:
        raise AppealError("Cap waktu banding harus ISO 8601 berzona.") from exc


def _evidence(raw):
    _shape(raw, ("source_ref", "sha256", "available_at"))
    ref = _text(raw["source_ref"], "rujukan bukti", 512)
    digest = raw["sha256"]
    if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
        raise AppealError("Bukti harus menyertakan hash SHA-256.")
    return ref, digest, _timestamp(raw["available_at"])


def _evidence_set(raw, upper):
    if not isinstance(raw, list) or len(raw) > MAX_EVIDENCE:
        raise AppealError("Jumlah bukti di luar batas.")
    output = {}
    digests = set()
    for item in raw:
        reference, digest, appeared = _evidence(item)
        if reference in output or digest in digests or appeared > upper:
            raise AppealError("Bukti ganda atau belum tersedia pada saat dicatat.")
        output[reference] = {"source_ref": reference, "sha256": digest, "available_at": appeared.isoformat()}
        digests.add(digest)
    return output, digests


@dataclass(frozen=True, slots=True)
class Rule:
    filing_deadline: datetime
    review_deadline: datetime
    reviewers: tuple[str, ...]

    @classmethod
    def from_dict(cls, raw, decided):
        _shape(raw, ("filing_deadline", "review_deadline", "eligible_reviewers"))
        filing, review = _timestamp(raw["filing_deadline"]), _timestamp(raw["review_deadline"])
        reviewers = _refs(raw["eligible_reviewers"], "peninjau")
        if not reviewers or not decided < filing < review:
            raise AppealError("Jadwal atau roster peninjau belum sah.")
        return cls(filing, review, tuple(reviewers))


def process_appeal(raw):
    """Replay penetapan banding dan satu ulasan atas putusan tertentu."""
    fields = {"decision", "rule", "appeal", "review"}
    if isinstance(raw, dict) and "as_of" in raw:
        fields.add("as_of")
    _shape(raw, fields)
    as_of = _timestamp(raw["as_of"]) if "as_of" in raw else None
    decision = raw["decision"]
    _shape(decision, ("id", "decided_at", "actor", "source_ref", "outcome", "evidence"))
    decided = _timestamp(decision["decided_at"])
    rules = Rule.from_dict(raw["rule"], decided)
    if as_of is not None and as_of < decided:
        raise AppealError("Putusan belum tersedia pada as_of.")
    decision_actor = _text(decision["actor"], "pemutus", 128)
    outcome = decision["outcome"]
    if outcome not in ("adopt", "reject", "defer"):
        raise AppealError("Outcome putusan asal tidak dikenal.")
    previous, prior_hashes = _evidence_set(decision["evidence"], decided)
    original = {
        "id": _text(decision["id"], "ID putusan", 128), "source_ref": _text(decision["source_ref"], "sumber", 512),
        "actor": decision_actor, "decided_at": decided.isoformat(), "outcome": outcome,
        "evidence": [previous[key] for key in sorted(previous)],
    }
    report = {"schema": "ace.appeal-protocol.v1", "original_decision": original,
              "status": "not_filed", "appeal": None, "review": None, "reconsideration_requested": False}
    if raw["appeal"] is None:
        if raw["review"] is not None:
            raise AppealError("Ulasan banding belum mempunyai banding.")
        if as_of is not None and as_of > rules.filing_deadline:
            report["status"] = "filing_closed"
        return report

    appeal = raw["appeal"]
    _shape(appeal, ("id", "decision_id", "appellant", "filed_at", "grounds", "source_ref", "new_evidence"))
    if appeal["decision_id"] != original["id"]:
        raise AppealError("Rujukan banding menunjuk putusan yang lain.")
    filed = _timestamp(appeal["filed_at"])
    if not decided < filed <= rules.filing_deadline:
        raise AppealError("Banding di luar jendela pengajuan.")
    if as_of is not None and filed > as_of:
        raise AppealError("Banding belum tersedia pada as_of.")
    evidence, digests = _evidence_set(appeal["new_evidence"], filed)
    if not evidence or evidence.keys() & previous.keys() or digests & prior_hashes:
        raise AppealError("Banding harus membawa bukti yang belum tercatat.")
    appellant = _text(appeal["appellant"], "pemohon", 128)
    request = {
        "id": _text(appeal["id"], "ID banding", 128), "decision_id": original["id"],
        "appellant": appellant, "filed_at": filed.isoformat(), "grounds": _text(appeal["grounds"], "dasar", 8_000),
        "source_ref": _text(appeal["source_ref"], "sumber banding", 512),
        "new_evidence": [evidence[key] for key in sorted(evidence)],
    }
    if request["source_ref"] == original["source_ref"]:
        raise AppealError("Berkas banding dan putusan harus punya sumber terpisah.")
    report.update(status="awaiting_review", appeal=request)
    review = raw["review"]
    if review is None:
        if as_of is not None and as_of > rules.review_deadline:
            report["status"] = "review_expired"
        return report

    _shape(review, ("appeal_id", "reviewer", "reviewed_at", "outcome", "reasons", "basis", "source_ref"))
    reviewer = _text(review["reviewer"], "peninjau banding", 128)
    if reviewer not in rules.reviewers or reviewer in (appellant, decision_actor):
        raise AppealError("Peninjau tidak berwenang secara independen.")
    reviewed = _timestamp(review["reviewed_at"])
    if not filed <= reviewed <= rules.review_deadline:
        raise AppealError("Ulasan di luar jendela pemeriksaan.")
    if as_of is not None and reviewed > as_of:
        raise AppealError("Ulasan belum tersedia pada as_of.")
    disposition = review["outcome"]
    if review["appeal_id"] != request["id"] or disposition not in ("remand", "dismiss"):
        raise AppealError("Ulasan menunjuk banding atau outcome tak dikenal.")
    basis = _refs(review["basis"], "dasar ulasan")
    if not basis or set(basis) - evidence.keys():
        raise AppealError("Ulasan wajib menunjuk bukti baru dari banding.")
    ref = _text(review["source_ref"], "sumber ulasan", 512)
    if ref in (request["source_ref"], original["source_ref"]):
        raise AppealError("Ulasan memerlukan sumber tersendiri.")
    report.update(status="reviewed", reconsideration_requested=disposition == "remand", review={
        "appeal_id": request["id"], "reviewer": reviewer, "reviewed_at": reviewed.isoformat(),
        "outcome": disposition, "reasons": _text(review["reasons"], "alasan", 8_000),
        "basis": basis, "source_ref": ref,
    })
    return report


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise AppealError("Berkas banding melampaui batas.")
        print(json.dumps(process_appeal(json.loads(data)), ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
