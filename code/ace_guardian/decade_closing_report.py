"""Ringkas papan dokumen dekade dan pisahkan penerimaan tercatat dari cek fixture dan utang bukti."""
from collections import Counter

from ._contracts import GuardianError, anchor, cli, digest, identifier, integer, items, obj, schema
from .decade_verdict_board import STATES, evolve_label

def report(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.decade-summary.v1", ("program", "goal", "outstanding"))
    goal = integer(plan["goal"], "Ambang nomor lulus", 1, 100)
    registered = Counter()
    fixtures = Counter()
    debts = []
    seen = set()
    for row in items(plan["program"], 100, 1):
        obj(row, ("evo", "state", "scope", "source", "reason"))
        evo = evolve_label(row["evo"])
        if evo in seen or row["state"] not in STATES or row["scope"] not in (None, "fixture", "registered_measurement"):
            raise GuardianError("Nomor ganda atau status/scope asing.")
        seen.add(evo)
        recorded = row["scope"] is not None
        if recorded:
            source = obj(row["source"], ("evo", "path", "sha256"))
            if row["reason"] != "recorded" or source["evo"] != evo:
                raise GuardianError("Sumber verdict tidak konsisten.")
            digest(source["sha256"])
            counts = registered if row["scope"] == "registered_measurement" else fixtures
            counts[row["state"]] += 1
        if not recorded or row["scope"] != "registered_measurement" or row["state"] != "passed":
            debts.append(evo)
    outstanding = sorted({identifier(value, "Utang tersisa") for value in items(plan["outstanding"], 500)})
    return {"registered": dict(sorted(registered.items())), "fixture": dict(sorted(fixtures.items())),
            "goal": goal, "verified_goal_reached": registered["passed"] >= goal,
            "evo_without_registered_pass": sorted(debts), "outstanding": outstanding,
            "completion_evidence_available": registered["passed"] >= goal and not outstanding}

if __name__ == "__main__":
    raise SystemExit(cli(report, __doc__))
