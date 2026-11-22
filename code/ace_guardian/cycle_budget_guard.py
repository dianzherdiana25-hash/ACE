"""Rencanakan langkah siklus menurut biaya aktual saat ini dan cadangan untuk langkah wajib."""
from ._contracts import GuardianError, anchor, cli, identifier, integer, items, obj, schema

def plan_budget(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.cycle-budget.v1", ("total_ms", "spent_ms", "remaining_steps"))
    limit = integer(plan["total_ms"], "Anggaran siklus", 1, 100_000_000)
    spent = integer(plan["spent_ms"], "Terpakai", 0, 100_000_000)
    rows = []
    seen = set()
    for row in items(plan["remaining_steps"], 300, 1):
        obj(row, ("id", "estimated_ms", "maximum_ms", "required"))
        key = identifier(row["id"], "Langkah")
        reservation = integer(row["estimated_ms"], "Estimasi", 0, 100_000_000)
        hard = integer(row["maximum_ms"], "Batas langkah", 1, 100_000_000)
        if key in seen or type(row["required"]) is not bool:
            raise GuardianError("Langkah ganda atau prioritas tidak sah.")
        seen.add(key)
        rows.append((key, reservation, hard, row["required"]))
    required = sum(item[1] for item in rows if item[3])
    held = [row[0] for row in rows if row[3] and row[1] > row[2]]
    if held or required + spent > limit:
        return {"status": "held", "required_held": held, "reserved_ms": required, "remaining_ms": max(0, limit - spent),
                "steps": []}
    after = limit - spent - required
    result = []
    for key, estimate, ceiling, mandatory in rows:
        if mandatory:
            reason = "required"
        elif estimate > ceiling:
            reason = "step_limit"
        elif estimate > after:
            reason = "reserve_for_required"
        else:
            reason = "within_budget"
            after -= estimate
        result.append({"id": key, "decision": "run_fixture" if reason in ("required", "within_budget") else "defer",
                       "reason": reason, "estimated_ms": estimate})
    return {"status": "planned", "reserved_ms": required, "remaining_ms": after, "steps": result}

if __name__ == "__main__":
    raise SystemExit(cli(plan_budget, __doc__))
