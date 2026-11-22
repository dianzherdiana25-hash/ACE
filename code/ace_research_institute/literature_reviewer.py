"""Rangkum kesepakatan atau konflik tinjauan pustaka per grup sumber independen."""
from collections import defaultdict
from decimal import Decimal
from statistics import median

from ._contracts import ResearchError, anchor, cli, fmt, identifier, identity, integer, items, obj, schema, text
from ._evidence import dimension, quantity, reviewed


def _render(results):
    lines = ["# Tinjauan pustaka", ""]
    for row in results:
        lines.extend([f"## {row['id']}", "", row["question"], "", f"Status **{row['status']}**", ""])
        if row["group_range"] is not None:
            low, high = row["group_range"]
            lines.extend([f"Rentang median per grup **{low}–{high} {row['unit']}**.", ""])
        for item in row["studies"]:
            where = item["source"]
            lines.append(f"- {item['estimate']} {row['unit']}, n={item['sample_size']}. "
                         f"Sumber `{item['source_id']}` `{where['path']}:{where['line']}`.")
        lines.append("")
    return "\n".join(lines)


def review(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.literature-plan.v1", ("sources", "questions"))
    registry, claims, held = reviewed(plan["sources"], root)
    cohorts = defaultdict(list)
    for row in claims:
        cohorts[(dimension(row["dimensions"]), row["unit"])].append(row)
    seen = set()
    results = []
    for row in items(plan["questions"], 60, 1):
        obj(row, ("id", "question", "dimensions", "unit", "agreement_width", "minimum_groups", "minimum_sample"))
        key = identifier(row["id"], "Rumusan")
        if key in seen:
            raise ResearchError("Rumusan tinjauan ganda.")
        seen.add(key)
        question = text(row["question"], "Pertanyaan")
        dims = dimension(row["dimensions"])
        unit, compatibility = quantity(row["agreement_width"], row["unit"])
        if compatibility < 0:
            raise ResearchError("Ambang rentang tinjauan perlu nonnegatif.")
        req_groups = integer(row["minimum_groups"], "Grup yang dibutuhkan", 1, 40)
        req_size = integer(row["minimum_sample"], "Ukuran sampel minimum", 1, 10**8)
        matched = [item for item in cohorts[(dims, unit)] if item["sample_size"] >= req_size]
        grouped = defaultdict(list)
        for item in matched:
            grouped[item["source"]["independence_group"]].append(Decimal(item["estimate"]))
        values = {name: median(samples) for name, samples in sorted(grouped.items())}
        spread = (min(values.values()), max(values.values())) if values else None
        if len(values) < req_groups:
            status = "insufficient_independent_groups"
        elif (spread[1] - spread[0]) <= compatibility:
            status = "observed_group_agreement"
        else:
            status = "group_disagreement"
        results.append({"id": key, "question": question, "unit": unit, "status": status,
                        "agreement_width": fmt(compatibility), "minimum_groups": req_groups,
                        "observed_groups": len(values), "group_medians": {name: fmt(value) for name, value in values.items()},
                        "group_range": [fmt(value) for value in spread] if values else None,
                        "studies": sorted(matched, key=lambda item: (item["source_id"], item["source"]["line"]))})
    return {"schema": "ace.institute.literature-review.v1", "plan_sha256": expected,
            "source_register_sha256": identity(registry), "held_table_rows": held, "results": results,
            "markdown": _render(results)}


if __name__ == "__main__":
    raise SystemExit(cli(review, __doc__, rooted=True))
