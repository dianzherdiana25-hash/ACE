"""Urutkan permintaan siap dengan skor auditable dan pilih alokasi sesuai jam tersedia."""
from ._contracts import ResearchError, anchor, cli, identity, integer, obj, schema
from .research_intake import intake


FIELDS = ("impact", "urgency", "wait", "evidence", "effort_saving")


def prioritize(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.priority-plan.v1", ("intake", "weights", "hours"))
    options = obj(plan["weights"], FIELDS)
    weights = {key: integer(options[key], "Bobot kriteria", 0, 100) for key in FIELDS}
    if sum(weights.values()) != 100:
        raise ResearchError("Bobot prioritas perlu berjumlah 100.")
    budget = integer(plan["hours"], "Anggaran jam", 1, 5000)
    register = intake(plan["intake"], identity(plan["intake"]), root)
    ranked = []
    for item in register["eligible"]:
        age = item["queue_age_days"]
        urgency = max(0, min(100, 100 - 4 * item["days_until_due"]))
        evidence = min(100, 25 * len({ref["sha256"] for ref in item["evidence"]}))
        factors = {"impact": item["declared_impact"], "urgency": urgency, "wait": min(100, 3 * age),
                   "evidence": evidence, "effort_saving": max(0, 100 - 2 * item["effort_hours"])}
        subtotal = {key: values * weights[key] for key, values in factors.items()}
        ranked.append({"id": item["id"], "question": item["question"], "evidence": item["evidence"],
                       "hours": item["effort_hours"], "score_bp": sum(subtotal.values()), "weighted_breakdown": subtotal,
                       "requested_due": item["requested_due"], "submitted": item["submitted"]})
    ranked.sort(key=lambda row: (-row["score_bp"], row["requested_due"], row["submitted"], row["id"]))
    chosen = []
    for item in ranked:
        if item["hours"] <= budget:
            budget -= item["hours"]
            chosen.append(item["id"])
            item["allocation"] = "allocated"
        else:
            item["allocation"] = "budget_insufficient_at_position"
    return {"schema": "ace.institute.research-priority.v1", "plan_sha256": expected, "intake_sha256": identity(register),
            "method": "weighted_rank_then_fit_to_remaining_hours", "ranked": ranked,
            "allocated": chosen, "hours_left": budget, "held": [{"id": item["id"], "needs": item["needs"]}
                                                               for item in register["held"]]}


if __name__ == "__main__":
    raise SystemExit(cli(prioritize, __doc__, rooted=True))
