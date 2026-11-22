"""Indeks insiden dari rantai peristiwa tanpa menghilangkan catatan kegagalan setelah pemulihan."""
from ._contracts import GuardianError, anchor, cli, identifier, identity, items, obj, schema, text
from .snapshot_scheduler import instant

PHASES = {None: {"failed"}, "failed": {"detected"}, "detected": {"recovering"}, "recovering": {"restored", "blocked"},
          "blocked": {"recovering"}, "restored": {"closed"}, "closed": set()}
GENESIS = identity({"schema": "ace.guardian.incident-chain.v1"})

def index(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.incident-index.v1", ("events",))
    state = {}
    latest = {}
    head = GENESIS
    last = None
    for sequence, row in enumerate(items(plan["events"], 5000), 1):
        obj(row, ("id", "component", "phase", "at", "source", "prior"))
        key = identifier(row["id"], "Insiden")
        unit = identifier(row["component"], "Komponen")
        at = instant(row["at"])
        source = text(row["source"], "Sumber insiden")
        prior = latest.get(key)
        if (row["prior"] != head or row["phase"] not in PHASES[prior] or (last and at < last)
                or (key in state and state[key]["component"] != unit)):
            raise GuardianError("Rantai insiden mundur, berubah komponen, atau transisinya tidak sah.")
        head = identity(row)
        latest[key], last = row["phase"], at
        entry = state.setdefault(key, {"id": key, "component": unit, "events": []})
        entry["events"].append({"phase": row["phase"], "at": row["at"], "source": source,
                                "seq": sequence, "sha256": head})
        entry["state"] = row["phase"]
    return {"incident_count": len(state), "head_sha256": head,
            "incidents": [state[key] for key in sorted(state)]}

if __name__ == "__main__":
    raise SystemExit(cli(index, __doc__))
