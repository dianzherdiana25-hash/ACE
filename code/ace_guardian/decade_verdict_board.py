"""Susun papan nomor EVO dari artefak tercatat, dengan tidak-dinilai untuk bukti yang belum ada."""
import re

from ._contracts import GuardianError, anchor, cli, decode, digest, items, obj, schema
from ._snapshots import fingerprint, read_fixture

NUMBER = re.compile(r"[0-9]{4}")
STATES = {"passed", "failed", "null", "blocked", "not_assessed"}

def evolve_label(value):
    if not isinstance(value, str) or not NUMBER.fullmatch(value) or not 1 <= int(value) <= 9999:
        raise GuardianError("Nomor EVO perlu empat digit 0001–9999.")
    return value

def board(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.guardian.decade-board.v1", ("expect", "records"))
    numbers = {evolve_label(value) for value in items(plan["expect"], 100, 1)}
    records = {}
    for row in items(plan["records"], 100):
        obj(row, ("evo", "path", "sha256"))
        key = evolve_label(row["evo"])
        sha = digest(row["sha256"])
        if key in records or key not in numbers:
            raise GuardianError("Record papan ganda atau di luar dekade.")
        observed = {"evo": key, "state": "not_assessed", "scope": None, "source": {**row}, "reason": "unverified_source"}
        try:
            raw = read_fixture(root, row["path"])
            if fingerprint(raw)["sha256"] != sha:
                raise GuardianError("Artefak verdict berubah.")
            document = schema(decode(raw), "ace.guardian.verdict.v1", ("evo", "scope", "state"))
            if document["evo"] != key or document["scope"] not in ("fixture", "registered_measurement") or document["state"] not in STATES:
                raise GuardianError("Isi artefak verdict tidak cocok.")
            observed.update(state=document["state"], scope=document["scope"], reason="recorded")
        except (OSError, ValueError, KeyError, TypeError, RecursionError):
            pass
        records[key] = observed
    return {"program": [records.get(key, {"evo": key, "state": "not_assessed", "scope": None,
                                        "source": None, "reason": "missing_source"}) for key in sorted(numbers)]}

if __name__ == "__main__":
    raise SystemExit(cli(board, __doc__, rooted=True))
