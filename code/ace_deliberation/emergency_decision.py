"""Rekam putusan darurat sementara dan periksa pengesahan sebelum kedaluwarsa.

Kelayakan membutuhkan tingkat urgensi, alasan tercatat, tindakan internal
reversibel, serta roster peninjau independen. Keputusan ini berupa data
untuk penelaahan. Jika tenggat lewat atau pengesahan tidak mungkin,
hasil meminta rollback sebagai status dan tidak menjalankan aksi.
"""
from datetime import timedelta
import hashlib
import json
from pathlib import Path

from .brier_scorer import _stamp


MAX_REVIEWERS = 100
MAX_SECONDS = 86_400
MAX_BYTES = 3_000_000


class EmergencyError(ValueError):
    """Masukan darurat tidak bisa diverifikasi sebagai catatan prosedural."""


def _shape(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise EmergencyError("Field darurat tidak sesuai skema.")


def _text(value, label, maximum=128):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\0" in value:
        raise EmergencyError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise EmergencyError(f"{label} bukan teks UTF-8 yang sah.") from exc
    return value.strip()


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise EmergencyError("Nilai kebijakan di luar batas.")
    return value


def _time(value):
    try:
        return _stamp(value)
    except ValueError as exc:
        raise EmergencyError("Cap waktu darurat wajib ISO 8601 berzona.") from exc


def _ids(values, maximum):
    if not isinstance(values, list) or not 1 <= len(values) <= maximum:
        raise EmergencyError("Rujukan harus berupa daftar nonkosong berbatas.")
    parsed = [_text(value, "rujukan", 512) for value in values]
    if len(set(parsed)) != len(parsed):
        raise EmergencyError("Rujukan ganda.")
    return sorted(parsed)


def review_emergency(raw):
    _shape(raw, ("proposal", "policy", "as_of", "reviews"))
    proposal = raw["proposal"]
    _shape(proposal, ("id", "proposed_by", "proposed_at", "severity", "evidence_refs", "undo_ref", "description",
                      "reversible", "external_effects"))
    actor = _text(proposal["proposed_by"], "pengaju")
    identifier = _text(proposal["id"], "ID putusan")
    refs = _ids(proposal["evidence_refs"], MAX_REVIEWERS)
    undo = _text(proposal["undo_ref"], "rencana rollback", 512)
    if undo in refs or type(proposal["reversible"]) is not bool or type(proposal["external_effects"]) is not bool:
        raise EmergencyError("Kustodi rollback atau batas tindakan tidak sah.")
    issued, now = _time(proposal["proposed_at"]), _time(raw["as_of"])
    if now < issued:
        raise EmergencyError("Putusan belum tercatat pada as_of.")
    severity = _integer(proposal["severity"], 0, 4)
    policy = raw["policy"]
    _shape(policy, ("min_severity", "review_window_seconds", "reviews_needed", "reviewers"))
    minimum = _integer(policy["min_severity"], 1, 4)
    maximum_age = _integer(policy["review_window_seconds"], 1, MAX_SECONDS)
    reviewers = _ids(policy["reviewers"], MAX_REVIEWERS)
    independent = set(reviewers) - {actor}
    required = _integer(policy["reviews_needed"], 1, MAX_REVIEWERS)
    try:
        deadline = issued + timedelta(seconds=maximum_age)
    except OverflowError as exc:
        raise EmergencyError("Tenggat melebihi rentang waktu.") from exc
    bound = {
        "decision_id": identifier, "actor": actor,
        "description": _text(proposal["description"], "deskripsi", 8_000),
        "evidence_refs": refs, "undo_ref": undo, "severity": severity,
        "proposed_at": issued.isoformat(), "review_until": deadline.isoformat(),
        "reversible": proposal["reversible"], "external_effects": proposal["external_effects"],
        "min_severity": minimum, "review_threshold": required, "reviewers": sorted(independent),
    }
    encoded = json.dumps(bound, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    baseline = {"schema": "ace.emergency-decision.v1", **bound,
                "proposal_sha256": digest, "as_of": now.isoformat()}
    records = raw["reviews"]
    if not isinstance(records, list) or len(records) > MAX_REVIEWERS:
        raise EmergencyError("Jumlah ulasan melebihi batas.")
    denied = []
    if severity < minimum:
        denied.append("insufficient_urgency")
    if not proposal["reversible"]:
        denied.append("not_reversible")
    if proposal["external_effects"]:
        denied.append("external_effects")
    if required > len(independent):
        denied.append("insufficient_independent_reviewers")
    if denied:
        if records:
            raise EmergencyError("Putusan yang ditolak tidak boleh mengandung pengesahan.")
        return {**baseline, "status": "refused", "rollback_due": False, "reasons": denied, "reviews": []}

    registered = {}
    seen_refs = set(refs) | {undo}
    for event in records:
        _shape(event, ("decision_id", "proposal_sha256", "reviewer", "at", "vote", "source_ref"))
        if event["proposal_sha256"] != digest:
            raise EmergencyError("Ulasan mengacu versi usulan yang berbeda.")
        reviewer = _text(event["reviewer"], "peninjau")
        ref = _text(event["source_ref"], "rujukan ulasan", 512)
        at = _time(event["at"])
        if (event["decision_id"] != identifier or reviewer not in independent or reviewer in registered
                or ref in seen_refs or not issued <= at <= now):
            raise EmergencyError("Ulasan ganda, tidak berwenang, atau di luar rekaman.")
        if event["vote"] not in ("ratify", "revoke", "abstain"):
            raise EmergencyError("Jenis suara pengesahan tidak dikenal.")
        seen_refs.add(ref)
        registered[reviewer] = ({
            "reviewer": reviewer, "vote": event["vote"], "at": at.isoformat(), "source_ref": ref,
            "counted": at <= deadline,
        }, at)

    review_rows = [row for row, at in sorted(registered.values(), key=lambda item: (item[1], item[0]["reviewer"]))]
    timely = [row for row in review_rows if row["counted"]]
    yes = sum(row["vote"] == "ratify" for row in timely)
    potential = yes + len(independent) - len(timely)
    if yes >= required:
        status, reason = "ratified", "approval_threshold_met"
    elif potential < required:
        status, reason = "revoked", "approval_threshold_unreachable"
    elif now > deadline:
        status, reason = "expired", "approval_deadline_elapsed"
    else:
        status, reason = "provisional", "awaiting_review"
    accepted_at = None
    if status == "ratified":
        accepted_at = [row["at"] for row in timely if row["vote"] == "ratify"][required - 1]
    return {**baseline, "status": status, "rollback_due": status in ("revoked", "expired"),
            "reasons": [reason], "yes_count": yes, "possible_yes": potential,
            "ratified_at": accepted_at, "reviews": review_rows}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise EmergencyError("Masukan darurat melampaui batas.")
        result = review_emergency(json.loads(data))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] in ("refused", "revoked", "expired"))


if __name__ == "__main__":
    raise SystemExit(main())
