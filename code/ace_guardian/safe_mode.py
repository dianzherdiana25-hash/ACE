"""Tahan tindakan saat anomali dan pulihkan mode hanya dengan stabilitas dan persetujuan bertambat."""
from ._contracts import GuardianError, anchor, cli, digest, integer, items, obj, schema
from .snapshot_scheduler import instant

def transition(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.safe-mode.v1", ("previous", "samples", "minimum_clean", "approval", "allowed_approvals"))
    prior = obj(plan["previous"], ("mode", "at"))
    if prior["mode"] not in ("normal", "safe"):
        raise GuardianError("Mode sebelumnya tidak dikenal.")
    last = instant(prior["at"])
    clean_required = integer(plan["minimum_clean"], "Sampel bersih", 1, 100)
    clean = 0
    faults = []
    for sample in items(plan["samples"], 1500):
        obj(sample, ("at", "status", "source"))
        when = instant(sample["at"])
        proof = digest(sample["source"])
        if when <= last or sample["status"] not in ("critical", "healthy", "unknown"):
            raise GuardianError("Sampel mode aman tidak berurutan atau status asing.")
        last = when
        if sample["status"] == "healthy":
            clean += 1
        else:
            clean = 0
            if sample["status"] == "critical":
                faults.append(proof)
    approvals = {digest(value) for value in items(plan["allowed_approvals"], 500)}
    approval = plan["approval"]
    allowed = approval is not None and digest(approval) in approvals
    if prior["mode"] == "normal":
        mode, reason = ("safe", "critical_signal") if faults else ("normal", "no_critical_signal")
    elif not faults and clean >= clean_required and allowed:
        mode, reason = "normal", "clean_and_approved"
    else:
        mode, reason = "safe", "latched"
    return {"mode": mode, "reason": reason, "clean_streak": clean, "critical_sources": faults, "approval_used":
            approval if reason == "clean_and_approved" else None}

if __name__ == "__main__":
    raise SystemExit(cli(transition, __doc__))
