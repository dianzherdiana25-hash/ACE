"""Pilih pertanyaan yang membuka alasan dari jawaban, rubrik, dan prasyarat yang belum jelas."""
from ._contracts import ProductionError, anchor, cli, identifier, identity, integer, items, obj, schema, text
from .grader import assess
from .hint_engine import leaks


def ask(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.teaching.socratic-plan.v1", ("grade_input", "question_bank", "seen", "protected_answer"))
    grade = assess(plan["grade_input"], identity(plan["grade_input"]))
    prior = {identifier(value, "Pertanyaan sebelumnya") for value in items(plan["seen"], 80)}
    hidden = [text(value, "Jawaban yang ditahan", 90) for value in items(plan["protected_answer"], 30, 1)]
    statuses = {row["id"]: row["status"] for row in grade["criteria"]}
    named = set()
    ranked = []
    withheld = []
    for row in items(plan["question_bank"], 100, 1):
        obj(row, ("id", "focus_criterion", "type", "question", "priority", "source_ref"))
        key = identifier(row["id"], "Pertanyaan Socratic")
        target = identifier(row["focus_criterion"], "Kriteria fokus")
        if key in named or target not in statuses or row["type"] not in ("clarify", "contrast", "justify", "generalize"):
            raise ProductionError("Pertanyaan ganda atau tidak sesuai kriteria.")
        named.add(key)
        topic = text(row["question"], "Pertanyaan", 500)
        if not topic.endswith("?"):
            raise ProductionError("Butir Socratic wajib berbentuk pertanyaan.")
        origin = text(row["source_ref"], "Pointer strategi")
        score = integer(row["priority"], "Prioritas butir", 0, 100)
        if leaks(topic, hidden):
            withheld.append({"id": key, "reason": "reserved_answer_overlap"})
            continue
        if key in prior:
            continue
        weight = {"contradiction": 300, "partial_or_missing": 200, "met": 100}[statuses[target]]
        if statuses[target] == "met" and row["type"] != "generalize":
            continue
        ranked.append((-(weight + score), key, {"id": key, "for_criterion": target, "observed": statuses[target],
                                               "type": row["type"], "question": topic, "source_ref": origin}))
    winner = min(ranked)[2] if ranked else None
    return {"schema": "ace.teaching.socratic-question.v1", "plan_sha256": expected,
            "grade_sha256": identity(grade), "selected": winner, "held": withheld,
            "status": "question_selected" if winner else "no_labeled_question"}


if __name__ == "__main__":
    raise SystemExit(cli(ask, __doc__))
