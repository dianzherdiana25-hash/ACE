"""Karantina usulan fakta sesi sampai write-set operasional menerima kelas yang sesuai."""
from ._contracts import PresenceError, anchor, cli, digest, identifier, identity, items, obj, schema, source_bytes, text
from ._journal import load_export

def prepare(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.writeback-plan.v1", ("dialogue", "facts"))
    ref = obj(plan["dialogue"], ("path", "sha256"))
    doc = load_export(source_bytes(root, ref["path"], ref["sha256"], 4_000_000))
    turns = {row["turn"]["id"]: row for row in doc["events"]}
    prepared = []
    seen = set()
    for fact in items(plan["facts"], 500):
        obj(fact, ("id", "turn_id", "quote", "evidence"))
        key = identifier(fact["id"], "Fakta")
        turn_id = identifier(fact["turn_id"], "Turn")
        quote = text(fact["quote"], "Fakta sesi")
        if key in seen or turn_id not in turns or quote not in turns[turn_id]["turn"]["message"]:
            raise PresenceError("Fakta berulang atau petikan tidak ditemukan.")
        seen.add(key)
        evidence = obj(fact["evidence"], ("path", "sha256"))
        digest(evidence["sha256"])
        if evidence["sha256"] == ref["sha256"]:
            raise PresenceError("Fakta sesi perlu bukti di luar ekspor dialog.")
        if not source_bytes(root, evidence["path"], evidence["sha256"]):
            raise PresenceError("Bukti eksternal kosong.")
        receipt = {"id": key, "quote": quote, "turn_sha256": turns[turn_id]["sha256"], "external": evidence}
        prepared.append({**receipt, "candidate_sha256": identity(receipt)})
    return {"status": "blocked", "reason": "session_fact_event_class_not_registered", "dialogue": ref, "candidates": prepared}

if __name__ == "__main__":
    raise SystemExit(cli(prepare, __doc__, rooted=True))
