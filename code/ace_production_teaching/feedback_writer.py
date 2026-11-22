"""Buat umpan balik per kriteria dari penilaian aktual dan tindakan perbaikan yang dirujuk."""
from ._contracts import ProductionError, anchor, cli, identifier, identity, items, obj, schema, text
from .grader import assess


def feedback(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.teaching.feedback-plan.v1", ("grade", "actions"))
    result = assess(plan["grade"], identity(plan["grade"]))
    known = {row["id"] for row in result["criteria"]}
    reflection = {}
    for row in items(plan["actions"], 65, 1):
        obj(row, ("criterion", "practice", "source_ref"))
        key = identifier(row["criterion"], "Kriteria")
        if key in reflection or key not in known:
            raise ProductionError("Aksi ganda atau tidak menunjuk kriteria yang dinilai.")
        reflection[key] = {"practice": text(row["practice"], "Langkah ulang", 400),
                           "source_ref": text(row["source_ref"], "Pointer latihan ulang")}
    strengths = []
    improvement = []
    open_gaps = []
    for entry in result["criteria"]:
        key, status = entry["id"], entry["status"]
        detail = {name: entry[name] for name in ("id", "earned_bp", "weight_bp", "source_ref")}
        if status == "met":
            strengths.append({**detail, "observed_terms": entry["hit"]})
            continue
        if key not in reflection:
            open_gaps.append(key)
        improvement.append({**detail, "status": status, "observed_terms": entry["hit"],
                            "conflicts": entry["opposed_by"], "next_action": reflection.get(key)})
    improvement.sort(key=lambda item: (item["status"] != "contradiction", item["earned_bp"] - item["weight_bp"], item["id"]))
    return {"schema": "ace.teaching.feedback.v1", "plan_sha256": expected, "exercise": result["exercise"],
            "grade_sha256": identity(result), "response_ref": result["response_source"], "score_bp": result["score_bp"],
            "strengths": strengths, "improvement": improvement, "missing_action": open_gaps}


if __name__ == "__main__":
    raise SystemExit(cli(feedback, __doc__))
