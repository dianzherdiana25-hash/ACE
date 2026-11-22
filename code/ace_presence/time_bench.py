"""Ukur respons mesin waktu melalui kasus berlabel lokal dengan persetujuan byte yang diperiksa ulang."""
from fractions import Fraction

from ._contracts import PresenceError, anchor, cli, decode, identifier, identity, items, obj, schema, source_bytes
from .calendar_engine import calendar
from .moment_memory import recall
from .quota_calendar import quotas
from .rhythm_learner import learn
from .temporal_store import timeline

METHODS = {
    "active_versions": (timeline, lambda out: {key: row["id"] for key, row in out["active"].items()}),
    "active_fact_ids": (timeline, lambda out: sorted(out["active"])),
    "calendar_event_ids": (calendar, lambda out: [row["id"] for row in out["events"]]),
    "moment_ids": (recall, lambda out: [row["id"] for row in out["matches"]]),
    "quota_remaining": (quotas, lambda out: {key: row["remaining"] for key, row in out["providers"].items()}),
    "rhythm_minutes": (learn, lambda out: [row["minutes"] for row in out["buckets"]]),
}

def bench(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.time-bench.v1", ("cases", "labels"))
    cases = obj(plan["cases"], ("path", "sha256"))
    gold = obj(plan["labels"], ("path", "sha256"))
    if cases["sha256"] == gold["sha256"]:
        raise PresenceError("Label waktu perlu berkas terpisah dari kasus.")
    seen = set()
    labels = decode(source_bytes(root, gold["path"], gold["sha256"]))
    if not isinstance(labels, dict):
        raise PresenceError("Label waktu perlu pemetaan per ID.")
    results = []
    for case in items(decode(source_bytes(root, cases["path"], cases["sha256"])), 200, 1):
        obj(case, ("id", "kind", "input"))
        key = identifier(case["id"], "Kasus")
        if key in seen or key not in labels or case["kind"] not in METHODS:
            raise PresenceError("Kasus waktu ganda, tanpa label, atau metode belum dikenal.")
        seen.add(key)
        operation, result = METHODS[case["kind"]]
        observed = result(operation(case["input"], identity(case["input"])))
        results.append({"id": key, "kind": case["kind"], "observed": observed,
                        "expected": labels[key], "correct": identity(observed) == identity(labels[key])})
    if labels.keys() != seen:
        raise PresenceError("Label tanpa kasus.")
    correct = sum(row["correct"] for row in results)
    return {"cases": cases, "labels": gold, "results": results, "correct": correct,
            "evaluated": len(results), "accuracy": str(Fraction(correct, len(results)))}

if __name__ == "__main__":
    raise SystemExit(cli(bench, __doc__, rooted=True))
