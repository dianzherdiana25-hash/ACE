"""Susun rencana retensi snapshot yang mendahulukan hold serta menjelaskan setiap pengusulan hapus."""
from datetime import timedelta

from ._contracts import GuardianError, anchor, cli, digest, identifier, integer, items, obj, schema
from .snapshot_scheduler import instant

def retain(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.snapshot-retention.v1", ("as_of", "keep_count", "max_age_days", "max_bytes", "snapshots"))
    now = instant(plan["as_of"])
    count = integer(plan["keep_count"], "Retensi minimum", 1, 100)
    age = timedelta(days=integer(plan["max_age_days"], "Usia", 1, 3650))
    max_bytes = integer(plan["max_bytes"], "Anggaran byte", 1, 10**15)
    snapshots = []
    seen = set()
    for row in items(plan["snapshots"], 5000):
        obj(row, ("id", "at", "bytes", "manifest", "hold"))
        key = identifier(row["id"], "Snapshot")
        stamp = instant(row["at"])
        size = integer(row["bytes"], "Byte snapshot", 1, 10**14)
        digest(row["manifest"])
        if key in seen or type(row["hold"]) is not bool or stamp > now:
            raise GuardianError("Snapshot ganda, waktu masa depan, atau hold tidak sah.")
        seen.add(key)
        snapshots.append((stamp, key, size, row))
    snapshots.sort(key=lambda item: (item[0], item[1]), reverse=True)
    required = {item[1] for item in snapshots[:count]} | {key for _, key, _, row in snapshots if row["hold"]}
    budget = sum(size for _, key, size, _ in snapshots if key in required)
    keeping, retiring = [], []
    for when, key, size, row in snapshots:
        if key in required:
            keeping.append({**row, "reason": "hold" if row["hold"] else "minimum_count"})
        elif now - when > age:
            retiring.append({**row, "reason": "expired"})
        elif budget + size > max_bytes:
            retiring.append({**row, "reason": "budget"})
        else:
            budget += size
            keeping.append({**row, "reason": "within_retention"})
    return {"retained": keeping, "retire_candidates": retiring, "retained_bytes": budget,
            "over_budget_protected": max(0, budget - max_bytes), "scope": "review_only"}

if __name__ == "__main__":
    raise SystemExit(cli(retain, __doc__))
