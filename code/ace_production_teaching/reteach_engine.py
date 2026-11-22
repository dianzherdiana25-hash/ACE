"""Pilih bahan ulang dengan pendekatan berbeda untuk kriteria yang belum lulus."""
from ._contracts import ProductionError, anchor, cli, identifier, identity, integer, items, obj, schema, text
from .grader import assess
from .hint_engine import leaks


def reteach(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.teaching.reteach-plan.v1", ("assessment", "prior_methods", "materials", "minutes", "reserved_answer"))
    result = assess(plan["assessment"], identity(plan["assessment"]))
    available = integer(plan["minutes"], "Batas menit", 1, 240)
    reserved = [text(answer, "Jawaban terlindungi", 110) for answer in items(plan["reserved_answer"], 30, 1)]
    past = {}
    for row in items(plan["prior_methods"], 60):
        obj(row, ("criterion", "method"))
        key = identifier(row["criterion"], "Kriteria")
        if key in past:
            raise ProductionError("Metode lama untuk kriteria ganda.")
        past[key] = identifier(row["method"], "Metode awal")
    choices = {}
    used = set()
    known = {row["id"] for row in result["criteria"]}
    for row in items(plan["materials"], 180, 1):
        obj(row, ("id", "criterion", "method", "narrative", "verification", "minutes", "source_ref"))
        key = identifier(row["id"], "Bahan remediasi")
        focus = identifier(row["criterion"], "Kriteria bahan")
        method = identifier(row["method"], "Metode")
        if key in used or focus not in known:
            raise ProductionError("Bahan ganda atau kriteria tidak terdaftar.")
        used.add(key)
        content = text(row["narrative"], "Arahan remediasi", 500)
        check = text(row["verification"], "Instruksi verifikasi", 300)
        if leaks(content + " " + check, reserved):
            continue
        choices.setdefault(focus, []).append({"id": key, "mode": method, "content": content,
                      "verification": check, "minutes": integer(row["minutes"], "Durasi remediasi", 1, 180),
                      "source_ref": text(row["source_ref"], "Pointer remediasi")})
    scheduled = []
    unresolved = []
    for row in sorted(result["criteria"], key=lambda item: (item["status"] != "contradiction", -item["weight_bp"], item["id"])):
        if row["status"] == "met":
            continue
        key = row["id"]
        if key not in past:
            unresolved.append({"criterion": key, "reason": "approach_before_unknown"})
            continue
        ranked = sorted((item for item in choices.get(key, []) if item["mode"] != past[key]),
                        key=lambda item: (item["minutes"], item["id"]))
        selected = next((item for item in ranked if item["minutes"] <= available), None)
        if selected is None:
            unresolved.append({"criterion": key, "reason": "different_method_missing" if not ranked else "time_budget"})
            continue
        available -= selected["minutes"]
        scheduled.append({"criterion": key, "previous_method": past[key], "reason": row["status"], "material": selected,
                          "rubric_ref": row["source_ref"]})
    return {"schema": "ace.teaching.reteach-draft.v1", "plan_sha256": expected, "grade_sha256": identity(result),
            "prepared": scheduled, "unresolved": unresolved, "minutes_left": available, "status": "draft_only"}


if __name__ == "__main__":
    raise SystemExit(cli(reteach, __doc__))
