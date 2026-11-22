"""Ukur cakupan perspektif pada bukti yang dapat ditunjuk untuk sisi dan konteks yang sama."""
from collections import defaultdict

from ._contracts import ResearchError, anchor, cli, identifier, identity, integer, items, obj, schema, text
from .claim_checker import check_claims


def assess_cover(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.viewpoint-plan.v1", ("checks", "target", "perspectives", "stance_labels"))
    source = check_claims(plan["checks"], identity(plan["checks"]), root)
    target = identifier(plan["target"], "Klaim target")
    claim = next((row for row in source["claims"] if row["id"] == target), None)
    if claim is None:
        raise ResearchError("Klaim belum dicatat.")
    labels = {}
    for row in items(plan["stance_labels"], 200):
        obj(row, ("source_id", "perspective", "annotation_ref"))
        key = identifier(row["source_id"], "Sumber")
        side = identifier(row["perspective"], "Perspektif")
        if key in labels:
            raise ResearchError("Satu sumber memiliki pelabelan perspektif ganda.")
        labels[key] = side, text(row["annotation_ref"], "Pointer label perspektif")
    seen = {}
    for row in items(plan["perspectives"], 40, 1):
        obj(row, ("id", "minimum_groups", "description"))
        perspective = identifier(row["id"], "Perspektif")
        if perspective in seen:
            raise ResearchError("Perspektif ganda.")
        seen[perspective] = (integer(row["minimum_groups"], "Grup minimum", 1, 50), text(row["description"], "Deskripsi"))
    if any(side not in seen for side, _ in labels.values()):
        raise ResearchError("Label perspektif merujuk sisi belum didefinisikan.")
    included = defaultdict(list)
    unlabeled = set()
    for row in claim["measurements"]:
        source_id = row["source_id"]
        if source_id not in labels:
            unlabeled.add(source_id)
            continue
        side, reference = labels[source_id]
        included[side].append({"id": source_id, "classification": row["classification"],
                               "independence_group": row["independence_group"], "source": row["source"], "annotation_ref": reference})
    results = []
    for name, (count, description) in sorted(seen.items()):
        sources = included[name]
        groups = sorted({row["independence_group"] for row in sources})
        results.append({"id": name, "description": description, "groups": groups,
                        "required_groups": count, "missing_groups": max(0, count - len(groups)),
                        "measurements": sources})
    achieved = sum(not row["missing_groups"] for row in results)
    return {"schema": "ace.institute.viewpoint-coverage.v1", "plan_sha256": expected,
            "check_sha256": identity(source), "target": target, "unlabeled_sources": sorted(unlabeled),
            "covered": achieved, "expected_perspectives": len(results), "perspectives": results}


if __name__ == "__main__":
    raise SystemExit(cli(assess_cover, __doc__, rooted=True))
