"""Suntik kegagalan pada siklus fixture tertentu dan pastikan checkpoint terakhir dapat direplay."""
from copy import deepcopy

from ._contracts import GuardianError, anchor, cli, identity, integer, items, obj, schema
from .twin_runner import run

def drill(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.chaos-plan.v1", ("runner", "faults"))
    reference = plan["runner"]
    original = run(reference, identity(reference))
    n = len(original["cycles"])
    cases = []
    seen = set()
    for entry in items(plan["faults"], 100, 1):
        obj(entry, ("cycle", "mode"))
        cycle = integer(entry["cycle"], "Siklus kegagalan", 1, n)
        mode = entry["mode"]
        if mode not in ("before_commit", "after_commit") or (cycle, mode) in seen:
            raise GuardianError("Fault fixture ganda atau belum dikenal.")
        seen.add((cycle, mode))
        stop = cycle - (mode == "before_commit")
        adjusted = {**reference, "cycles": deepcopy(reference["cycles"][:stop])}
        last = run(adjusted, identity(adjusted))
        remaining = {**reference, "initial": last["state"], "cycles": deepcopy(reference["cycles"][stop:])}
        recovered = run(remaining, identity(remaining))
        cases.append({"fault_at": cycle, "mode": mode, "committed": stop, "checkpoint": last["head_sha256"],
                      "resumed_sha256": recovered["head_sha256"], "recovered": recovered["state"] == original["state"]})
    return {"baseline": original["head_sha256"], "cases": sorted(cases, key=lambda row: (row["fault_at"], row["mode"]))}

if __name__ == "__main__":
    raise SystemExit(cli(drill, __doc__))
