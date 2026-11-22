"""Hitung putusan per aturan dan jendela waktu, dengan pencocokan aksi ke receipt berantai."""
from collections import Counter, defaultdict
from fractions import Fraction

from ._contracts import GuardianError, anchor, cli, digest, identifier, items, obj, schema
from .gate_receipt_ledger import verify_ledger
from .snapshot_scheduler import instant

def report(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.compliance-report.v1", ("from", "until", "ledger", "actions"))
    start, end = instant(plan["from"]), instant(plan["until"])
    if start >= end:
        raise GuardianError("Jendela laporan harus maju.")
    head, _, ledger = verify_ledger(plan["ledger"])
    counts = defaultdict(Counter)
    missing, mismatch = [], []
    observed = set()
    matched_receipts = set()
    examined = 0
    for row in items(plan["actions"], 5000):
        obj(row, ("id", "request_sha256", "at"))
        key = identifier(row["id"], "Aksi")
        sha = digest(row["request_sha256"])
        at = instant(row["at"])
        if key in observed:
            raise GuardianError("Aksi ganda di kelompok kepatuhan.")
        observed.add(key)
        if not start <= at < end:
            continue
        examined += 1
        receipt = ledger.get(key)
        if receipt is None:
            missing.append(key)
            continue
        if not at <= instant(receipt["at"]) < end or receipt["decision"]["request_sha256"] != sha:
            mismatch.append(key)
            continue
        matched_receipts.add(key)
        decision = receipt["decision"]
        for rule in decision["matched_rules"] or ["default"]:
            counts[rule][decision["outcome"]] += 1
    orphan = sorted(set(key for key, row in ledger.items() if start <= instant(row["at"]) < end) - matched_receipts)
    return {"head": head, "expected_actions": examined, "matched_receipts": len(matched_receipts),
            "coverage": str(Fraction(len(matched_receipts), examined)) if examined else None,
            "per_rule": {key: dict(sorted(val.items())) for key, val in sorted(counts.items())},
            "missing": sorted(missing), "mismatch": sorted(mismatch), "unmatched_receipts": orphan}

if __name__ == "__main__":
    raise SystemExit(cli(report, __doc__))
