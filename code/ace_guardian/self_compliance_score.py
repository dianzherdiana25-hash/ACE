"""Ukur kepatuhan pekanan dengan satu denominator aksi walau sebagian bukti action receipt hilang."""
from collections import Counter
from datetime import timedelta
from fractions import Fraction

from ._contracts import GuardianError, anchor, cli, digest, identifier, items, obj, schema
from .gate_receipt_ledger import verify_ledger
from .snapshot_scheduler import instant, iso

def score(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.self-compliance.v1", ("week_start", "observed", "receipts"))
    start = instant(plan["week_start"])
    if start.weekday() or start.hour or start.minute or start.second:
        raise GuardianError("Awal periode adalah Senin 00:00 UTC.")
    end = start + timedelta(days=7)
    head, _, ledger = verify_ledger(plan["receipts"])
    result = Counter(dict.fromkeys(("compliant", "no_receipt", "bypassed", "unexecuted", "mismatched"), 0))
    checks = []
    seen = set()
    for row in items(plan["observed"], 5000):
        obj(row, ("id", "at", "request_sha256", "executed", "source"))
        key = identifier(row["id"], "Aksi")
        at = instant(row["at"])
        digest(row["source"])
        sha = digest(row["request_sha256"])
        if key in seen or type(row["executed"]) is not bool:
            raise GuardianError("Observasi aksi ganda atau bendera tidak sah.")
        seen.add(key)
        if not start <= at < end:
            continue
        entry = ledger.get(key)
        if entry is None:
            status = "no_receipt"
        else:
            receipt = entry["decision"]
            receipt_at = instant(entry["at"])
            if sha != receipt["request_sha256"] or not start <= receipt_at <= at:
                status = "mismatched"
            elif row["executed"] and receipt["outcome"] != "allow":
                status = "bypassed"
            elif not row["executed"] and receipt["outcome"] == "allow":
                status = "unexecuted"
            else:
                status = "compliant"
        result[status] += 1
        checks.append({"id": key, "status": status, "source": row["source"], "receipt": entry["sha256"] if entry else None})
    count = len(checks)
    return {"week": [iso(start), iso(end)], "sample_count": count, "counts": dict(result), "receipt_head": head,
            "score": str(Fraction(result["compliant"], count)) if count else None, "checks": checks}

if __name__ == "__main__":
    raise SystemExit(cli(score, __doc__))
