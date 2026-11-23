"""Usulan fakta sesi: validasi karantina, lalu tulis ke memori kognitif.

Kelas event ``session_fact_verified`` kini terdaftar di
ace_operational.memory_writeback (EVO 0059, PR #720 butir 15),
jadi kandidat yang lolos validasi ditulis lewat
record_verified_event() dan receipt-nya membawa ID record.
Validasi tetap fail-closed: satu fakta tidak sah membatalkan
seluruh rencana sebelum ada penulisan apa pun. Penulisan hidup
di modul ini (jalur CLI ace_presence), tidak lewat leap_wiring.
"""
from pathlib import Path

from ace_operational.memory_writeback import record_verified_event

from ._contracts import PresenceError, anchor, cli, digest, identifier, identity, items, obj, schema, source_bytes, text
from ._journal import load_export

EVENT_CLASS = "session_fact_verified"
MEMORY_DIRNAME = "cognitive_memory"

def prepare(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.presence.writeback-plan.v1", ("dialogue", "facts"))
    ref = obj(plan["dialogue"], ("path", "sha256"))
    doc = load_export(source_bytes(root, ref["path"], ref["sha256"], 4_000_000))
    turns = {row["turn"]["id"]: row for row in doc["events"]}
    prepared = []
    payloads = []
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
        raw = source_bytes(root, evidence["path"], evidence["sha256"])
        if not raw:
            raise PresenceError("Bukti eksternal kosong.")
        receipt = {"id": key, "quote": quote, "turn_sha256": turns[turn_id]["sha256"], "external": evidence}
        prepared.append({**receipt, "candidate_sha256": identity(receipt)})
        payloads.append(raw)
    memory_root = Path(root) / MEMORY_DIRNAME
    written = []
    for candidate, raw in zip(prepared, payloads):
        record_id = record_verified_event(
            memory_root,
            event=EVENT_CLASS,
            summary=candidate["quote"],
            evidence_bytes=raw,
            content_extra={
                "fact_id": candidate["id"],
                "candidate_sha256": candidate["candidate_sha256"],
                "turn_sha256": candidate["turn_sha256"],
                "dialogue_sha256": ref["sha256"],
            },
        )
        written.append({**candidate, "record_id": record_id})
    if any(row["record_id"] is None for row in written):
        return {"status": "blocked", "reason": "session_fact_write_failed", "dialogue": ref, "candidates": written}
    return {"status": "written", "event_class": EVENT_CLASS, "dialogue": ref, "candidates": written}

if __name__ == "__main__":
    raise SystemExit(cli(prepare, __doc__, rooted=True))
