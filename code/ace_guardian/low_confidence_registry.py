"""Pertahankan larangan klaim yakin sampai bukti pemulihan menyamai atau melampaui ambang."""
from ._contracts import GuardianError, anchor, cli, digest, identifier, integer, items, obj, schema, text
from .snapshot_scheduler import instant

def registry(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.low-confidence.v1", ("now", "domains", "measurements"))
    at = instant(plan["now"])
    declared = {}
    for row in items(plan["domains"], 200, 1):
        obj(row, ("domain", "max_ece_bp", "minimum_samples", "reason", "from"))
        key = identifier(row["domain"], "Domain")
        if key in declared:
            raise GuardianError("Domain kebijakan berulang.")
        declared[key] = (integer(row["max_ece_bp"], "ECE maksimum", 0, 10_000),
                         integer(row["minimum_samples"], "Sampel minimum", 1, 50_000),
                         instant(row["from"]), text(row["reason"], "Dasar aturan"))
    estimates = {}
    for row in items(plan["measurements"], 1000):
        obj(row, ("domain", "ece_bp", "samples", "at", "expires", "source"))
        key = identifier(row["domain"], "Domain")
        observed, expiry = instant(row["at"]), instant(row["expires"])
        estimate = integer(row["ece_bp"], "ECE basis point", 0, 10_000)
        count = integer(row["samples"], "Sampel tercatat", 0, 50_000)
        proof = digest(row["source"])
        if key not in declared or observed > at or observed >= expiry or (key in estimates and observed == estimates[key][0]):
            raise GuardianError("Waktu atau domain pengukuran tidak sah.")
        if key not in estimates or observed > estimates[key][0]:
            estimates[key] = (observed, expiry, estimate, count, proof)
    restrictions = []
    for key, (cap, minimum, since, because) in sorted(declared.items()):
        probe = estimates.get(key)
        status, source = "limited_no_current_evidence", None
        if probe is not None and since <= probe[0] <= at < probe[1]:
            source = probe[-1]
            status = "eligible_for_confidence_review" if probe[2] <= cap and probe[3] >= minimum else "limited_measurement"
        restrictions.append({"domain": key, "status": status, "basis": because, "measurement": source})
    return {"domains": restrictions}

if __name__ == "__main__":
    raise SystemExit(cli(registry, __doc__))
