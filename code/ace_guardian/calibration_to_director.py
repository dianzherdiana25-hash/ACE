"""Bentuk saran abstain director dari ambang per domain yang masih berlaku dan dapat diverifikasi."""
from ._contracts import GuardianError, anchor, cli, digest, identifier, integer, items, obj, schema
from .snapshot_scheduler import instant

def advise(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.director-calibration.v1", ("now", "request", "thresholds", "approved_refs"))
    now = instant(plan["now"])
    request = obj(plan["request"], ("id", "domain", "confidence_bp", "request_ref"))
    key = identifier(request["id"], "Usulan")
    domain = identifier(request["domain"], "Domain")
    confidence = integer(request["confidence_bp"], "Confidence basis point", 0, 10_000)
    digest(request["request_ref"])
    verified = {digest(item) for item in items(plan["approved_refs"], 300)}
    entries = {}
    for row in items(plan["thresholds"], 300):
        obj(row, ("domain", "threshold_bp", "from", "until", "source"))
        name = identifier(row["domain"], "Domain")
        threshold = integer(row["threshold_bp"], "Ambang basis point", 0, 10_000)
        start, end = instant(row["from"]), instant(row["until"])
        ref = digest(row["source"])
        if name in entries or end <= start:
            raise GuardianError("Ambang domain ganda atau interval tidak sah.")
        entries[name] = (threshold, start, end, ref)
    threshold = entries.get(domain)
    reason, source = "no_current_evidence", None
    if threshold is not None:
        cutoff, first, last, reference = threshold
        if first <= now < last and reference in verified:
            reason = "below_threshold" if confidence < cutoff else "at_or_above_threshold"
            source = reference
    return {"proposal": key, "advice": "eligible_for_review" if reason == "at_or_above_threshold" else "abstain",
            "reason": reason, "calibration_ref": source, "request_ref": request["request_ref"]}

if __name__ == "__main__":
    raise SystemExit(cli(advise, __doc__))
