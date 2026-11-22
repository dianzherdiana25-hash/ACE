"""Rangkum checkpoint organ dari sumber yang disediakan dengan gap waktu dan failure streak."""
from collections import defaultdict
from datetime import timedelta
from fractions import Fraction

from ._contracts import GuardianError, anchor, cli, identifier, integer, items, obj, schema, text
from .snapshot_scheduler import instant

def health(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.organ-health.v1", ("as_of", "max_age_seconds", "organs", "observations"))
    now = instant(plan["as_of"])
    stale = timedelta(seconds=integer(plan["max_age_seconds"], "Usia kesehatan", 1, 86_400))
    providers = {identifier(key, "Organ") for key in items(plan["organs"], 200, 1)}
    timeline = defaultdict(list)
    seen = set()
    for row in items(plan["observations"], 5000):
        obj(row, ("organ", "at", "ok", "source", "latency_ms"))
        key = identifier(row["organ"], "Organ")
        when = instant(row["at"])
        ms = integer(row["latency_ms"], "Durasi health check", 0, 600_000)
        if key not in providers or type(row["ok"]) is not bool or when > now or (key, when) in seen:
            raise GuardianError("Record health di luar katalog, ganda, atau waktu tak sah.")
        seen.add((key, when))
        timeline[key].append((when, row["ok"], ms, text(row["source"], "Bukti health")))
    output = {}
    for key in sorted(providers):
        rows = sorted(timeline[key])
        if not rows:
            output[key] = {"status": "unobserved", "samples": 0}
            continue
        last, good, _, reference = rows[-1]
        failures = 0
        for row in reversed(rows):
            if row[1]:
                break
            failures += 1
        status = "stale" if now - last > stale else "healthy" if good else "degraded"
        output[key] = {"status": status, "samples": len(rows), "failure_streak": failures,
                       "success_rate": str(Fraction(sum(row[1] for row in rows), len(rows))),
                       "latest_source": reference}
    return {"organs": output, "as_of": plan["as_of"]}

if __name__ == "__main__":
    raise SystemExit(cli(health, __doc__))
