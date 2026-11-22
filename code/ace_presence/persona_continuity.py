"""Audit kesinambungan persona dari ekspor versi terverifikasi pada tahun-tahun yang diwajibkan."""
from ._contracts import PresenceError, anchor, cli, day, digest, identifier, integer, items, obj, schema, text

def audit(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.continuity-plan.v1", ("identity", "versions", "years", "fixed_values"))
    persona = identifier(plan["identity"], "Persona")
    requested = {integer(year, "Tahun audit", 1900, 9999) for year in items(plan["years"], 150, 1)}
    if not isinstance(plan["fixed_values"], dict) or not plan["fixed_values"]:
        raise PresenceError("Nilai inti persona diperlukan.")
    fixed = {identifier(key, "Nilai inti"): text(value, "Isi nilai") for key, value in plan["fixed_values"].items()}
    present = set()
    findings = []
    last, expected_prev = None, None
    seen = set()
    for row in items(plan["versions"], 300):
        obj(row, ("identity", "date", "sha256", "previous", "values", "source"))
        date = day(row["date"])
        sha = digest(row["sha256"])
        source = text(row["source"], "Sumber versi")
        if not isinstance(row["values"], dict) or row["previous"] != expected_prev or (last and date <= last) or sha in seen:
            raise PresenceError("Rantai persona tak terurut atau memuat nilai nonobjek.")
        seen.add(sha)
        if identifier(row["identity"], "Persona versi") != persona:
            findings.append({"reason": "identity_changed", "source": source, "date": row["date"]})
        for key, value in sorted(fixed.items()):
            if row["values"].get(key) != value:
                findings.append({"reason": "fixed_value_changed", "field": key, "source": source, "date": row["date"]})
        present.add(date.year)
        last, expected_prev = date, sha
    missing = sorted(requested - present)
    return {"continuous": not findings and not missing, "findings": findings,
            "missing_years": missing, "covered_years": sorted(requested & present), "head": expected_prev}

if __name__ == "__main__":
    raise SystemExit(cli(audit, __doc__))
