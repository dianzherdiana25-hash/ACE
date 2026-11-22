"""Rakit daftar kembaran dari jejak append-only dan validasi transisi eksperimen."""
from ._contracts import GuardianError, anchor, cli, digest, identifier, identity, items, obj, schema, text

ALLOWED = {None: {"created"}, "created": {"running", "archived"}, "running": {"tested", "failed"},
           "tested": {"archived"}, "failed": {"archived"}, "archived": set()}

def index(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.twin-registry-plan.v1", ("events",))
    head = identity({"kind": "ace.guardian.twin-registry.v1"})
    twins = {}
    for row in items(plan["events"], 2500):
        obj(row, ("twin", "event", "snapshot", "source", "previous"))
        key = identifier(row["twin"], "Kembaran")
        prior = twins.get(key)
        old = prior["state"] if prior else None
        event = row["event"]
        snapshot = digest(row["snapshot"])
        text(row["source"], "Bukti peristiwa")
        if row["previous"] != head or event not in ALLOWED[old] or (prior and prior["snapshot"] != snapshot):
            raise GuardianError("Transisi, induk, atau snapshot kembaran berbeda dari registrasi.")
        head = identity(row)
        twins[key] = {"state": event, "snapshot": snapshot, "source": row["source"], "head": head}
    return {"twins": dict(sorted(twins.items())), "head_sha256": head}

if __name__ == "__main__":
    raise SystemExit(cli(index, __doc__))
