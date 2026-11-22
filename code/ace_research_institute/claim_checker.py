"""Periksa klaim angka terhadap tabel sumber dengan konteks dan satuan yang benar."""
from decimal import Decimal

from ._contracts import ResearchError, anchor, cli, fmt, identifier, identity, integer, items, obj, schema, text
from ._evidence import dimension, quantity, reviewed


def _source_groups(sources, key):
    return sorted({item["independence_group"] for item in sources if item["classification"] == key})


def _measurements(claim, evidence, family, target, tolerance, size):
    rows = []
    excluded = []
    scope = dimension(claim["dimensions"])
    for item in evidence:
        other = dimension(item["dimensions"])
        if other != scope or item["unit"] != family or item["sample_size"] < size:
            if other[1] == scope[1]:
                excluded.append({"source_id": item["source_id"], "line": item["source"]["line"],
                                 "reason": "different_scope_unit_or_sample"})
            continue
        measured = Decimal(item["estimate"])
        difference = abs(measured - target)
        lower, upper = target - tolerance, target + tolerance
        interval = item["interval"]
        if difference <= tolerance:
            classification = "supports"
        elif interval and Decimal(interval["lower"]) <= upper and Decimal(interval["upper"]) >= lower:
            classification = "interval_overlaps"
        else:
            classification = "contradicts"
        rows.append({"source_id": item["source_id"], "measurement_id": item["id"], "source": item["source"],
                     "independence_group": item["source"]["independence_group"], "estimate": item["estimate"],
                     "difference": fmt(difference), "classification": classification, "interval": interval,
                     "sample_size": item["sample_size"]})
    return rows, excluded


def check_claims(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.claim-plan.v1", ("source_plan", "claims"))
    register, evidence, held_rows = reviewed(plan["source_plan"], root)
    results = []
    seen = set()
    for row in items(plan["claims"], 200, 1):
        obj(row, ("id", "text", "source_ref", "dimensions", "value", "unit", "tolerance", "minimum_groups", "minimum_sample"))
        key = identifier(row["id"], "Klaim")
        if key in seen:
            raise ResearchError("ID klaim ganda.")
        seen.add(key)
        description = text(row["text"], "Teks klaim")
        pointer = text(row["source_ref"], "Pointer klaim")
        size = integer(row["minimum_sample"], "Sampel minimum", 1, 10**8)
        required = integer(row["minimum_groups"], "Grup minimum", 1, 50)
        unit, target = quantity(row["value"], row["unit"])
        _, tolerance = quantity(row["tolerance"], row["unit"])
        if tolerance < 0:
            raise ResearchError("Toleransi tidak boleh negatif.")
        checks, excluded = _measurements(row, evidence, unit, target, tolerance, size)
        support = _source_groups(checks, "supports")
        conflict = _source_groups(checks, "contradicts")
        if support and conflict:
            status = "mixed_evidence"
        elif len(support) >= required:
            status = "supported"
        elif len(conflict) >= required:
            status = "contradicted"
        else:
            status = "insufficient_evidence"
        results.append({"id": key, "claim": description, "source_ref": pointer, "value": fmt(target), "unit": unit, "dimensions": row["dimensions"],
                        "tolerance": fmt(tolerance), "minimum_groups": required, "status": status,
                        "support_groups": support, "contradict_groups": conflict, "measurements": checks, "excluded": excluded})
    summary = {status: sum(row["status"] == status for row in results) for status in (
        "supported", "contradicted", "mixed_evidence", "insufficient_evidence")}
    return {"schema": "ace.institute.claim-check.v1", "plan_sha256": expected, "source_register_sha256": identity(register),
            "source_table_holds": held_rows, "summary": summary, "claims": results}


if __name__ == "__main__":
    raise SystemExit(cli(check_claims, __doc__, rooted=True))
