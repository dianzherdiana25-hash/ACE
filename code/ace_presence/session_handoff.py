"""Buat checkpoint serah terima terikat sesi, tujuan, masa berlaku, dan persetujuan lokal."""
from ._contracts import PresenceError, anchor, cli, digest, identifier, identity, obj, schema, source_bytes
from ._journal import instant, load_export

def issue(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.handoff-plan.v1", ("dialogue", "from", "to", "issued_at", "expires_at", "nonce"))
    source = obj(plan["dialogue"], ("path", "sha256"))
    checked = load_export(source_bytes(root, source["path"], source["sha256"], 4_000_000))
    origin, target = (identifier(plan[key], "Kanal") for key in ("from", "to"))
    now, expiry = (instant(plan[key]) for key in ("issued_at", "expires_at"))
    if origin == target or not 0 < (expiry - now).total_seconds() <= 86400:
        raise PresenceError("Tujuan atau masa berlaku handoff tidak sah.")
    if checked["events"] and instant(checked["events"][-1]["turn"]["at"]) > now:
        raise PresenceError("Handoff mendahului turn terakhir.")
    digest(plan["nonce"])
    result = {**plan, "schema": "ace.presence.handoff.v1", "session": checked["session"], "head_sha256": checked["head_sha256"]}
    return {"checkpoint": result, "sha256": identity(result)}

def receive(checkpoint, expected, target, now, consumed):
    anchor(checkpoint, expected)
    schema(checkpoint, "ace.presence.handoff.v1", (
        "dialogue", "from", "to", "issued_at", "expires_at", "nonce", "session", "head_sha256"))
    return (checkpoint["to"] == target and checkpoint["nonce"] not in consumed
            and instant(checkpoint["issued_at"]) <= instant(now) < instant(checkpoint["expires_at"]))

if __name__ == "__main__":
    raise SystemExit(cli(issue, __doc__, rooted=True))
