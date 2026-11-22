"""Uji reproduksi temuan dengan kriteria desain dan toleransi efek yang ditetapkan terpisah."""
from decimal import Decimal

from ._contracts import ResearchError, anchor, cli, fmt, identifier, identity, integer, items, obj, schema, text
from ._evidence import dimension, quantity, reviewed


def assess(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.replication-assessment.v1", ("sources", "prior", "replication", "protocol"))
    register, measurements, held = reviewed(plan["sources"], root)
    index = {(row["source_id"], row["id"]): row for row in measurements}
    current = []
    for key in ("prior", "replication"):
        value = obj(plan[key], ("source_id", "id"))
        reference = tuple(identifier(value[name], name) for name in ("source_id", "id"))
        current.append(index.get(reference))
    rule = obj(plan["protocol"], ("unit", "maximum_delta", "minimum_sample", "direction", "checks", "source_ref"))
    unit, permitted = quantity(rule["maximum_delta"], rule["unit"])
    size = integer(rule["minimum_sample"], "Sampel per studi", 1, 10**8)
    direction = rule["direction"]
    if permitted < 0 or direction not in ("same_sign", "any"):
        raise ResearchError("Toleransi atau ketentuan arah tidak sah.")
    protocol_ref = text(rule["source_ref"], "Pointer protokol")
    checklist = {}
    for row in items(rule["checks"], 30, 1):
        obj(row, ("id", "status", "source_ref"))
        name = identifier(row["id"], "Langkah desain")
        if name in checklist or row["status"] not in ("matched", "deviated", "unknown"):
            raise ResearchError("Nama desain duplikat atau status tidak sah.")
        checklist[name] = {"status": row["status"], "source_ref": text(row["source_ref"], "Pointer komparasi desain")}
    left, right = current
    missing = []
    cases = {"prior": left, "replication": right}
    missing.extend(name for name, record in cases.items() if record is None)
    delta = None
    result = None
    if not missing:
        if any(row["unit"] != unit or row["sample_size"] < size for row in current) or dimension(left["dimensions"]) != dimension(right["dimensions"]):
            missing.append("incomparable_scope_or_sample")
        if left["source"]["independence_group"] == right["source"]["independence_group"]:
            missing.append("same_independence_group")
    missing.extend(name for name, decision in checklist.items() if decision["status"] != "matched")
    if not missing:
        a, b = Decimal(left["estimate"]), Decimal(right["estimate"])
        delta = abs(a - b)
        signs_match = (a > 0) - (a < 0) == (b > 0) - (b < 0)
        result = delta <= permitted and (direction == "any" or signs_match)
    return {"schema": "ace.institute.replication-review.v1", "plan_sha256": expected,
            "register_sha256": identity(register), "status": ("blocked" if result is None else
            ("matches_predefined_effect_rule" if result else "does_not_match_effect_rule")),
            "protocol_ref": protocol_ref, "design_checks": checklist, "held": missing, "records": cases,
            "effect_delta": fmt(delta) if delta is not None else None, "unit": unit, "table_holds": held}


if __name__ == "__main__":
    raise SystemExit(cli(assess, __doc__, rooted=True))
