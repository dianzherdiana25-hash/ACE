"""Klasifikasi konflik dua paper setelah konteks, sampel, dan satuan dibandingkan."""
from decimal import Decimal

from ._contracts import ResearchError, anchor, cli, fmt, identifier, identity, items, obj, schema
from ._evidence import dimension, quantity, reviewed


def compare_papers(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.paper-conflict-plan.v1", ("source_plan", "pairs"))
    register, rows, held = reviewed(plan["source_plan"], root)
    index = {(row["source_id"], row["id"]): row for row in rows}
    result = []
    visited = set()
    for request in items(plan["pairs"], 100, 1):
        obj(request, ("id", "left", "right", "material_value", "material_unit"))
        key = identifier(request["id"], "Perbandingan")
        if key in visited:
            raise ResearchError("Perbandingan paper ganda.")
        visited.add(key)
        left, right = [obj(request[side], ("paper", "measurement")) for side in ("left", "right")]
        refs = [tuple(identifier(ref[label], label) for label in ("paper", "measurement")) for ref in (left, right)]
        if refs[0] == refs[1]:
            raise ResearchError("Bandingkan dua pengukuran yang berbeda.")
        unit, threshold = quantity(request["material_value"], request["material_unit"])
        if threshold <= 0:
            raise ResearchError("Perbedaan material harus positif.")
        records = [index.get(ref) for ref in refs]
        a, b = records
        measures = None
        if a is None or b is None:
            status = "measurement_unavailable"
        elif dimension(a["dimensions"]) != dimension(b["dimensions"]) or a["unit"] != unit or b["unit"] != unit:
            status = "incompatible_scope"
        elif a["source"]["independence_group"] == b["source"]["independence_group"]:
            status = "same_independence_group"
        else:
            difference = abs(Decimal(a["estimate"]) - Decimal(b["estimate"]))
            overlap = None
            if a["interval"] is not None and b["interval"] is not None:
                lower = max(Decimal(study["interval"]["lower"]) for study in records)
                upper = min(Decimal(study["interval"]["upper"]) for study in records)
                overlap = lower <= upper
            if difference < threshold:
                status = "difference_below_threshold"
            elif overlap is True:
                status = "material_estimates_overlapping_intervals"
            elif overlap is False:
                status = "material_difference_disjoint_intervals"
            else:
                status = "material_difference_uncertainty_unavailable"
            measures = {"delta": fmt(difference), "unit": unit, "intervals_overlap": overlap}
        result.append({"id": key, "status": status, "refs": [left, right], "records": records, "comparison": measures})
    return {"schema": "ace.institute.paper-conflict.v1", "plan_sha256": expected,
            "register_sha256": identity(register), "findings": result, "held_rows": held}


if __name__ == "__main__":
    raise SystemExit(cli(compare_papers, __doc__, rooted=True))
