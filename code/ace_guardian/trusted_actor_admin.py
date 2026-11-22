"""Rakit wewenang aktif dari grant dan revocation berurutan, berbatas waktu, dan berprovenance."""
from datetime import timedelta

from ._contracts import GuardianError, anchor, cli, digest, identifier, items, obj, schema
from .snapshot_scheduler import instant

def registry(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.trusted-actors.v1", ("at", "scopes", "events", "authority_refs"))
    now = instant(plan["at"])
    scopes = {identifier(key, "Scope") for key in items(plan["scopes"], 100, 1)}
    authorities = {digest(value) for value in items(plan["authority_refs"], 500, 1)}
    recent = {}
    declared = set()
    last = None
    for row in items(plan["events"], 3000):
        obj(row, ("id", "actor", "scope", "effect", "at", "expires", "ref"))
        key = identifier(row["id"], "Grant atau revocation")
        actor = identifier(row["actor"], "Aktor")
        scope = identifier(row["scope"], "Scope")
        stamp = instant(row["at"])
        ref = digest(row["ref"])
        if (key in declared or scope not in scopes or ref not in authorities or stamp > now
                or (last and stamp < last) or row["effect"] not in ("grant", "revoke")):
            raise GuardianError("Wewenang ganda, tak disetujui, atau urutan mundur.")
        declared.add(key)
        last = stamp
        if row["effect"] == "grant":
            expiry = instant(row["expires"])
            if not timedelta(0) < expiry - stamp <= timedelta(days=90):
                raise GuardianError("Wewenang harus berbatas waktu sampai 90 hari.")
            recent[(actor, scope)] = (expiry, row)
        elif row["expires"] is not None or (actor, scope) not in recent:
            raise GuardianError("Revocation perlu grant sebelumnya dan tidak memiliki expiry.")
        else:
            del recent[(actor, scope)]
    return {"as_of": plan["at"], "active": [
        {"actor": actor, "scope": scope, "expires": row["expires"], "source": row["ref"]}
        for (actor, scope), (expiry, row) in sorted(recent.items()) if now < expiry]}

if __name__ == "__main__":
    raise SystemExit(cli(registry, __doc__))
