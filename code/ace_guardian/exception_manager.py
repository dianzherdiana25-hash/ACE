"""Evaluasi pengecualian berbatas waktu untuk putusan review yang mempunyai persetujuan spesifik."""
from datetime import timedelta

from ._contracts import GuardianError, anchor, cli, digest, identifier, items, obj, schema, text
from .gate_receipt_ledger import verify_decision
from .snapshot_scheduler import instant

def exceptions(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.exceptions.v1", ("at", "decision", "grants", "approved"))
    now = instant(plan["at"])
    decision = verify_decision(plan["decision"])
    accepted = {digest(value) for value in items(plan["approved"], 500)}
    matches = []
    seen = set()
    for row in items(plan["grants"], 500):
        obj(row, ("id", "kind", "request_sha256", "policy_sha256", "starts", "expires", "approval_ref", "reason"))
        key = identifier(row["id"], "Pengecualian")
        kind = identifier(row["kind"], "Kelas pengecualian")
        start, end = instant(row["starts"]), instant(row["expires"])
        text(row["reason"], "Alasan persetujuan")
        if key in seen or not timedelta(0) < end - start <= timedelta(days=1):
            raise GuardianError("Pengecualian ganda atau masa berlaku melampaui satu hari.")
        seen.add(key)
        approval = digest(row["approval_ref"])
        request, policy = digest(row["request_sha256"]), digest(row["policy_sha256"])
        if (start <= now < end and approval in accepted and kind == decision["kind"]
                and request == decision["request_sha256"] and policy == decision["policy_sha256"]):
            matches.append(row)
    if decision["outcome"] != "review":
        return {"outcome": decision["outcome"], "applied": None}
    if len(matches) == 1:
        return {"outcome": "allow", "applied": matches[0]["id"], "receipt_ref": matches[0]["approval_ref"]}
    return {"outcome": "review", "applied": None, "reason": "ambiguous" if matches else "missing_approval"}

if __name__ == "__main__":
    raise SystemExit(cli(exceptions, __doc__))
