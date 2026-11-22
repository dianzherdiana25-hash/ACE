"""Bandingkan dua hasil kembaran yang berawal sama dengan delta per field dan jejak siklus."""
from ._contracts import GuardianError, anchor, cli, digest, identifier, identity, integer, items, obj, schema
from .twin_runner import MAX_VALUE

def _verify(result):
    schema(result, "ace.guardian.twin-result.v1", ("initial_sha256", "state", "head_sha256", "cycles"))
    head = digest(result["initial_sha256"])
    for offset, row in enumerate(items(result["cycles"], 100), 1):
        obj(row, ("cycle", "before_sha256", "state_sha256", "actions_sha256"))
        integer(row["cycle"], "Siklus", offset, offset)
        digest(row["actions_sha256"])
        if row["before_sha256"] != head:
            raise GuardianError("Rantai state kembaran terputus.")
        head = digest(row["state_sha256"])
    if not isinstance(result["state"], dict) or head != result["head_sha256"] or head != identity(result["state"]):
        raise GuardianError("State akhir tidak cocok dengan head kembaran.")
    for key, value in result["state"].items():
        identifier(key, "Field")
        integer(value, "Nilai akhir", -MAX_VALUE, MAX_VALUE)
    return result

def compare(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.twin-diff.v1", ("baseline", "candidate"))
    first, second = (_verify(plan[key]) for key in ("baseline", "candidate"))
    if first["initial_sha256"] != second["initial_sha256"] or first["state"].keys() != second["state"].keys():
        raise GuardianError("Kedua lengan perlu baseline yang sama.")
    details = []
    for key, old in sorted(first["state"].items()):
        new = second["state"][key]
        details.append({"field": key, "baseline": old, "candidate": new, "delta": new - old})
    first_split = next((index for index, pair in enumerate(zip(first["cycles"], second["cycles"]), 1)
                        if pair[0]["state_sha256"] != pair[1]["state_sha256"]), None)
    if first_split is None and len(first["cycles"]) != len(second["cycles"]):
        first_split = min(len(first["cycles"]), len(second["cycles"])) + 1
    return {"deltas": details, "first_difference_cycle": first_split, "baseline": first["head_sha256"],
            "candidate": second["head_sha256"]}

if __name__ == "__main__":
    raise SystemExit(cli(compare, __doc__))
