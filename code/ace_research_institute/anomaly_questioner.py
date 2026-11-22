"""Ubah penyimpangan terukur menjadi pertanyaan yang bisa disangkal dan bertambat data."""
from decimal import Decimal

from ._contracts import anchor, cli, identity, integer, schema, text
from .pattern_finder import find_patterns


def questions(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.anomaly-question-plan.v1", ("patterns", "maximum", "source_ref", "units"))
    cap = integer(plan["maximum"], "Batas pertanyaan", 1, 100)
    source = text(plan["source_ref"], "Pointer analisis")
    unit = text(plan["units"], "Satuan hasil")
    patterns = find_patterns(plan["patterns"], identity(plan["patterns"]), root)
    pending = []
    unavailable = []
    for cohort in patterns["groups"]:
        key = cohort["group"]
        if cohort["anomaly_status"] == "mad_zero":
            unavailable.append({"group": key, "reason": "mad_zero"})
        for row in cohort["anomalies"]:
            probable = Decimal(row["abs_difference"])
            line = row["line"]
            generated = {
                "id": f"anomaly_{line}", "group": key, "kind": "investigate_measurement",
                "question": f"Apakah pengukuran ulang untuk kelompok {key} kembali ke distribusi acuan?",
                "falsifier": "Pengukuran ulang mempertahankan arah penyimpangan di luar ambang yang sama.",
                "source_ref": source, "data": {**patterns["source"], "line": line},
                "comparison": {"observed": row["value"], "median": cohort["median"], "unit": unit,
                               "absolute_difference": row["abs_difference"]},
                "suggested_check": "repeat_measurement",
            }
            pending.append((-probable, line, generated))
    pending.sort()
    return {"schema": "ace.institute.anomaly-questions.v1", "plan_sha256": expected, "patterns_sha256": identity(patterns),
            "items": [row for _, _, row in pending[:cap]], "remaining": len(pending) - min(len(pending), cap),
            "held_groups": unavailable, "scope": "questions_only"}


if __name__ == "__main__":
    raise SystemExit(cli(questions, __doc__, rooted=True))
