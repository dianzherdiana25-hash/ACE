"""Usulkan koreksi fakta hanya jika byte klaim sesi dan sumber pembanding keduanya bertambat."""
from ._contracts import PresenceError, anchor, cli, decode, identifier, items, obj, schema, source_bytes, text
from ._journal import load_export

def corrections(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.corrections-plan.v1", ("dialogue", "authority", "claims"))
    dia = obj(plan["dialogue"], ("path", "sha256"))
    auth = obj(plan["authority"], ("path", "sha256"))
    turns = load_export(source_bytes(root, dia["path"], dia["sha256"], 4_000_000))
    evidence = decode(source_bytes(root, auth["path"], auth["sha256"]))
    facts = {}
    for row in items(evidence, 500):
        obj(row, ("key", "value"))
        key = identifier(row["key"], "Fakta")
        if key in facts:
            raise PresenceError("Sumber memuat dua nilai untuk kunci fakta.")
        facts[key] = text(row["value"], "Nilai sumber")
    values = {row["turn"]["id"]: row for row in turns["events"]}
    result = []
    for claim in items(plan["claims"], 500):
        obj(claim, ("turn_id", "key", "value"))
        turn_id = identifier(claim["turn_id"], "Turn")
        key = identifier(claim["key"], "Kunci")
        value = text(claim["value"], "Kutipan")
        event = values.get(turn_id)
        if event is None or value not in event["turn"]["message"]:
            raise PresenceError("Kutipan klaim tidak ditemukan dalam turn.")
        corrected = facts.get(key)
        status = "unknown" if corrected is None else "confirmed" if corrected == value else "review_correction"
        result.append({"key": key, "turn_id": turn_id, "turn_sha256": event["sha256"], "reported": value,
                       "expected": corrected, "status": status})
    return {"authority": auth, "dialogue": dia, "claims": result}

if __name__ == "__main__":
    raise SystemExit(cli(corrections, __doc__, rooted=True))
