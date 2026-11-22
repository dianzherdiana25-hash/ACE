"""Hitung waktu deteksi dan pulih dari peristiwa insiden, dengan unresolved sebagai cakupan."""
from collections import defaultdict
from fractions import Fraction
from statistics import median

from ._contracts import anchor, cli, identifier, identity, items, schema
from .incident_journal import index
from .snapshot_scheduler import instant

def summarize(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.recovery-times.v1", ("journal", "required"))
    requested = {identifier(item, "Komponen") for item in items(plan["required"], 100, 1)}
    indexed = index(plan["journal"], identity(plan["journal"]))
    groups = defaultdict(list)
    orphaned = []
    for item in indexed["incidents"]:
        component = item["component"]
        if component not in requested:
            continue
        phases = {}
        for row in item["events"]:
            phases.setdefault(row["phase"], row)
        if "restored" not in phases:
            orphaned.append({"id": item["id"], "component": component, "state": item["state"],
                             "failure_source": phases["failed"]["source"]})
            continue
        stamps = {name: instant(phases[name]["at"]) for name in ("failed", "detected", "restored")}
        diff = lambda first, last: int((stamps[last] - stamps[first]).total_seconds())
        groups[component].append({"id": item["id"], "to_detect_seconds": diff("failed", "detected"),
                                  "to_restore_seconds": diff("failed", "restored"),
                                  "refs": [phases[name]["source"] for name in stamps]})
    components = {}
    for key in sorted(requested):
        values = groups[key]
        restored = [Fraction(row["to_restore_seconds"]) for row in values]
        components[key] = {"restored": len(values), "median_restore_seconds": str(median(restored)) if restored else None,
                           "incidents": values}
    return {"components": components, "unresolved": orphaned, "journal_head": indexed["head_sha256"]}

if __name__ == "__main__":
    raise SystemExit(cli(summarize, __doc__))
