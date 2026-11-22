"""Rekam prediksi dan hasil kemudian dalam ledger yang mengunci probabilitas sebelum resolusi."""
from ._contracts import GuardianError, anchor, cli, digest, identifier, identity, integer, items, obj, schema
from .snapshot_scheduler import instant

GENESIS = identity({"schema": "ace.guardian.confidence-chain.v1"})

def ledger(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.confidence-ledger.v1", ("events",))
    pending = {}
    completed = {}
    head = GENESIS
    last = None
    for row in items(plan["events"], 6000):
        obj(row, ("id", "kind", "domain", "at", "value", "source", "previous"))
        key = identifier(row["id"], "Prediksi")
        domain = identifier(row["domain"], "Domain")
        source = digest(row["source"])
        at = instant(row["at"])
        if row["previous"] != head or (last and at < last) or key in completed:
            raise GuardianError("Jejak kalibrasi berulang atau tidak urut.")
        head, last = identity(row), at
        if row["kind"] == "forecast" and key not in pending:
            confidence = integer(row["value"], "Probabilitas basis point", 0, 10_000)
            pending[key] = {"id": key, "domain": domain, "at": row["at"], "confidence_bp": confidence, "forecast_ref": source}
        elif row["kind"] == "resolve" and key in pending and domain == pending[key]["domain"] and type(row["value"]) is bool:
            predicted = pending.pop(key)
            if instant(predicted["at"]) >= at or predicted["forecast_ref"] == source:
                raise GuardianError("Resolusi harus lebih baru dengan bukti terpisah.")
            completed[key] = {**predicted, "observed": row["value"], "resolved_at": row["at"], "resolved_ref": source}
        else:
            raise GuardianError("Transisi kalibrasi tidak diizinkan.")
    return {"head_sha256": head, "pending": [pending[key] for key in sorted(pending)],
            "completed": [completed[key] for key in sorted(completed)]}

if __name__ == "__main__":
    raise SystemExit(cli(ledger, __doc__))
