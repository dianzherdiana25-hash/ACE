"""Nilai praktik metodologis pada checklist per desain yang tertambat ke potongan dokumen."""
from ._contracts import ResearchError, anchor, cli, identifier, integer, items, obj, schema, source_bytes, text


CRITERIA = {
    "randomized": {"sequence": 2000, "concealment": 1800, "missing_data": 1800, "measurement": 2200, "prespecified": 2200},
    "observational": {"sampling": 1800, "confounding": 2300, "measurement": 2000, "missing_data": 1900, "sensitivity": 2000},
    "qualitative": {"sampling": 2100, "coding": 2400, "triangulation": 1900, "reflexivity": 1800, "saturation": 1800},
}


def assess_methods(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.method-plan.v1", ("design", "source", "criteria", "minimum_bp"))
    design = plan["design"]
    if design not in CRITERIA:
        raise ResearchError("Desain metodologi belum didukung.")
    weights = CRITERIA[design]
    minimum = integer(plan["minimum_bp"], "Ambang metodologi", 0, 10000)
    source = obj(plan["source"], ("path", "sha256"))
    lines = source_bytes(root, source["path"], source["sha256"]).decode("utf-8").splitlines()
    evidence = {}
    for row in items(plan["criteria"], len(weights)):
        name = identifier(row["id"], "Kriteria")
        if name in evidence or name not in weights:
            raise ResearchError("ID kriteria ganda atau tidak sesuai desain.")
        obj(row, ("id", "status", "line", "excerpt", "reason"))
        state = row["status"]
        why = text(row["reason"], "Alasan metodologis")
        if state not in ("met", "partial", "unmet"):
            raise ResearchError("Status metodologi tidak sah.")
        line = integer(row["line"], "Baris metodologi", 1, len(lines))
        cited = text(row["excerpt"], "Kutipan metodologi", 200)
        if cited not in lines[line - 1]:
            raise ResearchError("Kutipan metodologi berbeda dari baris sumber.")
        evidence[name] = {"id": name, "status": state, "line": line, "excerpt": cited, "reason": why,
                          "weight_bp": weights[name], "earned_bp": weights[name] * {"met": 2, "partial": 1, "unmet": 0}[state] // 2}
    criteria = [evidence.get(name, {"id": name, "status": "unassessed", "weight_bp": weight, "earned_bp": 0})
                for name, weight in weights.items()]
    score = sum(row["earned_bp"] for row in criteria)
    return {"schema": "ace.institute.method-grade.v1", "plan_sha256": expected, "source": source,
            "design": design, "criteria": criteria, "score_bp": score,
            "declared_rubric": True, "status": "meets_rubric" if score >= minimum and evidence.keys() == weights.keys() else "hold"}


if __name__ == "__main__":
    raise SystemExit(cli(assess_methods, __doc__, rooted=True))
