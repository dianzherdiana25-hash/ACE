"""Telaah resolusi biner yang belum jelas dengan panel dan rubrik beku.

Setiap anggota mendapat satu ballot. Abstain tidak memenuhi kuorum
substantif. Ballot ambigu menyumbang denominator dan dapat menahan
resolusi sesuai ambang yang tercantum di rubrik. Laporan membedakan
data terlambat, tidak hadir dan berkas yang menggunakan rubrik berbeda.
"""
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json

from ._advanced import InputError, integer, json_main, labels, probability, rows, shape, stamp, text, unique
from .brier_scorer import _rational


STANCES = ("yes", "no", "ambiguous", "abstain")
MAX_PANEL = 70


def rubric_digest(raw):
    payload = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class Rule:
    ref: str
    description: str
    quorum: int
    agreement: Fraction
    ambiguity: Fraction

    @classmethod
    def read(cls, raw, size):
        shape(raw, ("ref", "criteria", "quorum", "agreement", "ambiguity_ceiling"))
        rule = cls(text(raw["ref"], "rubrik"), text(raw["criteria"], "kriteria", 8000),
                   integer(raw["quorum"], 1, size), probability(raw["agreement"]),
                   probability(raw["ambiguity_ceiling"]))
        if rule.agreement <= Fraction(1, 2):
            raise InputError("Ambang persetujuan harus di atas setengah.")
        return rule


def _evaluate(ballots, rule):
    counts = dict.fromkeys(STANCES, 0)
    for ballot in ballots:
        counts[ballot["stance"]] += 1
    substantive = len(ballots) - counts["abstain"]
    ratios = {label: Fraction(counts[label], substantive) if substantive else None
              for label in STANCES if label != "abstain"}
    winner = max(("yes", "no"), key=counts.get)
    if substantive < rule.quorum:
        status = "quorum_missing"
    elif ratios["ambiguous"] > rule.ambiguity:
        status = "ambiguity_ceiling_exceeded"
    elif ratios[winner] < rule.agreement:
        status = "agreement_missing"
    else:
        status = "resolved"
    return {
        "status": status, "outcome": int(winner == "yes") if status == "resolved" else None,
        "valid_ballots": len(ballots), "substantive_ballots": substantive, "counts": counts,
        "shares": {label: _rational(value) if value is not None else None for label, value in ratios.items()},
    }


def resolve(raw):
    shape(raw, ("question_id", "question_ref", "opens_at", "closes_at", "panel", "rubric", "ballots"))
    question = text(raw["question_id"], "pertanyaan")
    question_ref = text(raw["question_ref"], "sumber pertanyaan")
    panel = sorted(labels(raw["panel"], 1, MAX_PANEL, "anggota"))
    rule = Rule.read(raw["rubric"], len(panel))
    digest = rubric_digest(raw["rubric"])
    references = {question_ref}
    unique(rule.ref, references)
    opened, closed = stamp(raw["opens_at"]), stamp(raw["closes_at"])
    if opened >= closed:
        raise InputError("Jendela resolusi harus mempunyai durasi positif.")
    accepted, excluded = [], []
    seen = set()
    for row in rows(raw["ballots"], 0, MAX_PANEL * 2):
        shape(row, ("reviewer", "ballot_ref", "rubric_hash", "stance", "submitted_at", "evidence_refs"))
        reviewer = unique(text(row["reviewer"], "anggota"), seen, "Anggota")
        ref = unique(text(row["ballot_ref"], "ballot"), references)
        stance = text(row["stance"], "pilihan")
        if stance not in STANCES:
            raise InputError("Pilihan ballot tidak dikenal.")
        given_hash = text(row["rubric_hash"], "hash rubrik")
        evidence = sorted(labels(row["evidence_refs"], int(stance != "abstain"), 20, "sumber bukti"))
        if ref in evidence:
            raise InputError("Ballot tidak dapat dijadikan bukti dirinya sendiri.")
        submitted = stamp(row["submitted_at"])
        excerpt = {"reviewer": reviewer, "ballot_ref": ref, "submitted_at": submitted.isoformat(),
                   "rubric_hash": given_hash, "stance": stance, "evidence_refs": evidence}
        if reviewer not in panel:
            reason = "not_on_panel"
        elif not opened <= submitted <= closed:
            reason = "outside_window"
        elif given_hash != digest:
            reason = "rubric_mismatch"
        else:
            accepted.append(excerpt)
            continue
        excluded.append({**excerpt, "reason": reason})
    accepted.sort(key=lambda row: row["reviewer"])
    excluded.sort(key=lambda row: row["reviewer"])
    tally = _evaluate(accepted, rule)
    valid_reviewers = {row["reviewer"] for row in accepted}
    sensitivity = []
    if tally["outcome"] is not None:
        for row in accepted:
            counterfactual = _evaluate([other for other in accepted if other is not row], rule)
            if counterfactual["outcome"] != tally["outcome"]:
                sensitivity.append({"reviewer": row["reviewer"], "ballot_ref": row["ballot_ref"],
                                    "status_without_ballot": counterfactual["status"]})
    return {
        "schema": "ace.resolution-panel.v1", "question_id": question, "question_ref": question_ref,
        "rubric": {"ref": rule.ref, "sha256": digest, "criteria": rule.description, "quorum": rule.quorum,
                   "agreement": _rational(rule.agreement), "ambiguity_ceiling": _rational(rule.ambiguity)},
        "opens_at": opened.isoformat(), "closes_at": closed.isoformat(),
        "accepted": accepted, "excluded": excluded,
        "panel_without_valid_ballot": sorted(set(panel) - valid_reviewers),
        "decisive_ballots": sensitivity,
        **tally,
    }


def main(argv=None):
    return json_main(argv, __doc__, resolve)


if __name__ == "__main__":
    raise SystemExit(main())
