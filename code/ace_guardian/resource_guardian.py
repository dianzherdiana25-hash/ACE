"""Periksa gabungan CPU, RAM, dan jumlah kembaran lewat sweep interval tanpa menjalankan proses."""
from collections import defaultdict

from ._contracts import GuardianError, anchor, cli, identifier, integer, items, obj, schema
from .snapshot_scheduler import instant, iso

def guard(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.resources.v1", ("limits", "intervals"))
    dimensions = ("cpu_units", "memory_mib", "twins")
    capacity = obj(plan["limits"], dimensions)
    limits = [integer(capacity[field], f"Batas {field}", 1, 1_000_000) for field in dimensions]
    changes = defaultdict(list)
    keys = set()
    for row in items(plan["intervals"], 2000):
        obj(row, ("id", "start", "end", "cpu_units", "memory_mib"))
        key = identifier(row["id"], "Kembaran")
        start, end = instant(row["start"]), instant(row["end"])
        amount = [integer(row[field], field, 0, 1_000_000) for field in dimensions[:2]] + [1]
        if key in keys or start >= end:
            raise GuardianError("Interval kembaran tidak maju atau ID ganda.")
        keys.add(key)
        changes[start].append((key, 1, amount))
        changes[end].append((key, -1, amount))
    active = set()
    total, peak = [0, 0, 0], [0, 0, 0]
    violations = []
    ordered = sorted(changes)
    for index, when in enumerate(ordered):
        for key, direction, amounts in changes[when]:
            if direction > 0:
                active.add(key)
            else:
                active.remove(key)
            total = [value + direction * amount for value, amount in zip(total, amounts)]
        peak = [max(old, current) for old, current in zip(peak, total)]
        excess = {key: value - limit for key, value, limit in zip(dimensions, total, limits) if value > limit}
        if excess:
            violations.append({"start": iso(when), "end": iso(ordered[index + 1]), "excess": excess, "active": sorted(active)})
    return {"allowed": not violations, "peaks": dict(zip(dimensions, peak)), "violations": violations}

if __name__ == "__main__":
    raise SystemExit(cli(guard, __doc__))
