"""Jaga urutan receipt aksi sebagai append-only hash chain yang menolak replay berbeda isi."""
from ._contracts import GuardianError, anchor, cli, digest, identifier, identity, integer, items, obj, schema
from .snapshot_scheduler import instant

GENESIS = identity({"schema": "ace.guardian.gate-chain.v1"})
DECISION = ("action_id", "kind", "outcome", "reason", "matched_rules", "request_sha256", "policy_sha256")

def verify_decision(decision):
    obj(decision, DECISION)
    identifier(decision["action_id"], "Aksi")
    identifier(decision["kind"], "Kelas")
    identifier(decision["reason"], "Alasan")
    if decision["outcome"] not in ("allow", "review", "deny"):
        raise GuardianError("Putusan receipt tidak dikenal.")
    kinds = [identifier(value, "Aturan") for value in items(decision["matched_rules"], 1000)]
    if len(kinds) != len(set(kinds)):
        raise GuardianError("Aturan receipt berulang.")
    for field in ("request_sha256", "policy_sha256"):
        digest(decision[field])
    return decision

def verify_ledger(receipts):
    head = GENESIS
    keys = {}
    when = None
    for seq, receipt in enumerate(items(receipts, 5000), 1):
        obj(receipt, ("index", "at", "decision", "previous", "sha256"))
        body = {key: value for key, value in receipt.items() if key != "sha256"}
        stamp = instant(receipt["at"])
        decision = verify_decision(receipt["decision"])
        key = decision["action_id"]
        if (receipt["previous"] != head or integer(receipt["index"], "Urutan", seq, seq) != seq
                or identity(body) != digest(receipt["sha256"]) or (when and stamp < when) or key in keys):
            raise GuardianError("Rantai receipt tidak konsisten.")
        head, when, keys[key] = receipt["sha256"], stamp, receipt
    return head, when, keys

def append(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.gate-receipt.v1", ("prior", "decision", "at"))
    head, last, keys = verify_ledger(plan["prior"])
    row = verify_decision(plan["decision"])
    at = instant(plan["at"])
    key = row["action_id"]
    if key in keys:
        if keys[key]["decision"] != row:
            raise GuardianError("ID receipt dipakai untuk putusan yang berbeda.")
        return {"receipt": keys[key], "head_sha256": head, "replay": True}
    if (last and at < last) or len(keys) >= 5000:
        raise GuardianError("Waktu receipt mundur atau ledger sudah penuh.")
    body = {"index": len(keys) + 1, "at": plan["at"], "decision": row, "previous": head}
    head = identity(body)
    return {"receipt": {**body, "sha256": head}, "head_sha256": head, "replay": False}

if __name__ == "__main__":
    raise SystemExit(cli(append, __doc__))
