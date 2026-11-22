"""Nilai bukti dari desain, batas metode, dan kesepakatan kelompok sumber."""
from collections import Counter
from decimal import Decimal
from statistics import median

from ._contracts import ResearchError, anchor, cli, fmt, identifier, identity, integer, items, obj, schema, text
from ._evidence import dimension, quantity, reviewed


DESIGN = {"randomized": 4, "controlled": 3, "observational": 2, "case_series": 1}
DIMENSIONS = ("attrition", "selection", "measurement")


def grade(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.grade-plan.v1", ("sources", "target", "assessments", "minimum_groups", "conflict_width"))
    registry, records, uncertainty = reviewed(plan["sources"], root)
    target = obj(plan["target"], ("dimensions", "unit"))
    scope = dimension(target["dimensions"])
    unit, width = quantity(plan["conflict_width"], target["unit"])
    if width < 0:
        raise ResearchError("Toleransi konflik tidak boleh negatif.")
    minimum = integer(plan["minimum_groups"], "Grup minimum", 1, 50)
    by_source = {}
    for row in items(plan["assessments"], 150, 1):
        obj(row, ("source_id", "design", "citation", "risk"))
        key = identifier(row["source_id"], "Sumber")
        if key in by_source or row["design"] not in DESIGN:
            raise ResearchError("Penilaian ganda atau desain metodologis tidak dikenal.")
        levels = obj(row["risk"], DIMENSIONS)
        for level in levels.values():
            if level not in ("low", "unclear", "high"):
                raise ResearchError("Status risiko perlu low, unclear, atau high.")
        by_source[key] = (row["design"], text(row["citation"], "Pointer telaah desain"), levels)
    evaluated = []
    grouped = {}
    for record in records:
        if dimension(record["dimensions"]) != scope or record["unit"] != unit:
            continue
        key = record["source_id"]
        reference = record["source"]
        if key not in by_source:
            evaluated.append({"source_id": key, "source": reference, "status": "missing_design_assessment"})
            continue
        design, citation, risks = by_source[key]
        penalty = sum({"low": 0, "unclear": 1, "high": 2}[level] for level in risks.values())
        quality = max(0, DESIGN[design] - penalty)
        item = {"source_id": key, "source": reference, "status": "graded", "quality": quality,
                "design": design, "risk": risks, "methodology_ref": citation, "estimate": record["estimate"]}
        evaluated.append(item)
        group = reference["independence_group"]
        if quality >= 2:
            late = grouped.setdefault(group, [])
            late.append((Decimal(record["estimate"]), quality))
    central = [median([number for number, _ in records]) for records in grouped.values()]
    diversity = None if not central else max(central) - min(central)
    if len(grouped) < minimum:
        verdict = "insufficient_graded_independent_groups"
    elif diversity > width:
        verdict = "conflicting_graded_estimates"
    elif all(max(rank for _, rank in samples) >= 3 for samples in grouped.values()):
        verdict = "consistent_on_declared_design_rubric"
    else:
        verdict = "limited_support_on_rubric"
    return {"schema": "ace.institute.evidence-grade.v1", "plan_sha256": expected, "source_register_sha256": identity(registry),
            "status": verdict, "unit": unit, "graded_groups": sorted(grouped),
            "grade_counts": dict(sorted(Counter(item["quality"] for item in evaluated if "quality" in item).items())),
            "between_group_spread": fmt(diversity) if diversity is not None else None,
            "evidence": evaluated, "held_rows": uncertainty}


if __name__ == "__main__":
    raise SystemExit(cli(grade, __doc__, rooted=True))
