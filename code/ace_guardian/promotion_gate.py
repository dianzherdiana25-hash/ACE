"""Tahan promosi kecuali kedua scorecard memiliki bukti independen dan semua batas terlampaui."""
from ._contracts import GuardianError, anchor, cli, digest, fmt, identifier, items, number, obj, schema

def screen(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.promotion-plan.v1", ("metrics", "validations"))
    checks = []
    seen = set()
    for item in items(plan["metrics"], 200, 1):
        obj(item, ("id", "baseline", "candidate", "baseline_ref", "candidate_ref", "direction", "minimum_gain"))
        key = identifier(item["id"], "Metrik")
        if key in seen or item["direction"] not in ("higher", "lower"):
            raise GuardianError("Metrik ganda atau arah tidak dikenal.")
        seen.add(key)
        before, after, minimum = (number(item[field], field) for field in ("baseline", "candidate", "minimum_gain"))
        if minimum < 0:
            raise GuardianError("Kenaikan minimum perlu nonnegatif.")
        refs = [digest(item[field]) for field in ("baseline_ref", "candidate_ref")]
        gain = (after - before) * (1 if item["direction"] == "higher" else -1)
        reason = "same_evidence" if refs[0] == refs[1] else "below_threshold" if gain < minimum else "met"
        checks.append({"id": key, "gain": fmt(gain), "required": fmt(minimum), "status": reason, "refs": refs})
    sources = []
    validated = set()
    for validation in items(plan["validations"], 60, 1):
        obj(validation, ("id", "passed", "source"))
        key = identifier(validation["id"], "Verifier")
        if key in validated or type(validation["passed"]) is not bool:
            raise GuardianError("Verifier ganda atau status invalid.")
        validated.add(key)
        sources.append({"id": key, "source": digest(validation["source"]), "passed": validation["passed"]})
    return {"recommendation": "eligible" if all(row["status"] == "met" for row in checks) and
            all(row["passed"] for row in sources) else "hold", "metrics": sorted(checks, key=lambda row: row["id"]),
            "validations": sorted(sources, key=lambda row: row["id"]), "plan_sha256": expected}

if __name__ == "__main__":
    raise SystemExit(cli(screen, __doc__))
