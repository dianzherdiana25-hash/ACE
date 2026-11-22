"""Pilih kasus berizin sesuai celah belajar dan pisahkan petunjuk dari jawaban fasilitator."""
from ._contracts import (ProductionError, anchor, cli, identifier, identity, integer,
                         items, obj, schema, source_bytes, text)
from .hint_engine import leaks
from .learner_model import posterior


def select_case(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.case-plan.v1", ("profile", "topic", "maximum_level", "cases"))
    profile = posterior(plan["profile"], identity(plan["profile"]), root)
    topic = identifier(plan["topic"], "Topik kasus")
    ceiling = integer(plan["maximum_level"], "Tingkat maksimum", 1, 8)
    if topic not in profile["topic_posteriors"]:
        raise ProductionError("Topik kasus belum tercatat pada model learner.")
    valid = []
    held = []
    seen = set()
    for row in items(plan["cases"], 60, 1):
        obj(row, ("id", "topic", "level", "case", "permit_ref", "decisions", "answer_forms"))
        key = identifier(row["id"], "Kasus")
        if key in seen:
            raise ProductionError("ID kasus ganda.")
        seen.add(key)
        level = integer(row["level"], "Tingkat kasus", 1, 8)
        if row["topic"] != topic or level > ceiling:
            held.append({"case": key, "reason": "outside_topic_or_level"})
            continue
        if row["permit_ref"] is None:
            held.append({"case": key, "reason": "permission_missing"})
            continue
        origin = text(row["permit_ref"], "Pointer penggunaan kasus")
        ref = obj(row["case"], ("path", "sha256"))
        recorded = source_bytes(root, ref["path"], ref["sha256"], 180000).decode("utf-8")
        source_lines = recorded.splitlines()
        choices = []
        ids = set()
        reserved = [text(value, "Jawaban tertutup", 90) for value in items(row["answer_forms"], 30, 1)]
        for item in items(row["decisions"], 15, 1):
            obj(item, ("id", "line", "question"))
            decision = identifier(item["id"], "Keputusan")
            start = integer(item["line"], "Baris skenario", 1, len(source_lines))
            raw = text(item["question"], "Pertanyaan kasus", 380)
            if decision in ids or not raw.endswith("?"):
                raise ProductionError("Langkah kasus harus pertanyaan ber-ID unik.")
            ids.add(decision)
            scene = text(source_lines[start - 1], "Petikan skenario", 750)
            if leaks(raw + " " + scene, reserved):
                raise ProductionError("Kasus menyingkap bentuk jawaban yang ditahan.")
            choices.append({"id": decision, "line": start, "scenario": scene, "question": raw})
        valid.append((level, key, {"id": key, "topic": topic, "level": level, "source": ref,
                                   "permission_ref": origin, "decisions": choices}))
    state = profile["topic_posteriors"][topic]
    target_level = 1 if state["evidence_status"] != "observed" else 1 + state["posterior_mean_bp"] * (ceiling - 1) // 10000
    winner = min(valid, key=lambda item: (abs(item[0] - target_level), item[0], item[1]))[2] if valid else None
    return {"schema": "ace.teaching.case-lesson.v1", "plan_sha256": expected, "scope": "selected_case_material",
            "learner_profile_sha256": identity(profile), "topic": topic, "recommended_level": target_level,
            "case": winner, "held": held, "status": "draft" if winner else "no_case_available"}


if __name__ == "__main__":
    raise SystemExit(cli(select_case, __doc__, rooted=True))
