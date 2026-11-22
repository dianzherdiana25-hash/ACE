"""Rangkai panduan wawancara bercabang dengan kondisi, jejak keputusan, dan batas waktu."""

from ._contracts import ResearchError, anchor, cli, identifier, identity, integer, items, obj, schema, text


def _prepare(plan):
    start = identifier(plan["entry"], "Awal wawancara")
    limit = integer(plan["duration_cap"], "Waktu wawancara", 1, 180)
    questions = {}
    for row in items(plan["questions"], 120, 1):
        obj(row, ("id", "prompt", "purpose_ref", "minutes", "routes"))
        key = identifier(row["id"], "Pertanyaan")
        if key in questions:
            raise ResearchError("ID pertanyaan ganda.")
        routes = {}
        for route in items(row["routes"], 20, 1):
            obj(route, ("tag", "next"))
            label = identifier(route["tag"], "Tag jawaban")
            if label in routes:
                raise ResearchError("Tag cabang ganda.")
            destination = None if route["next"] is None else identifier(route["next"], "Tujuan cabang")
            routes[label] = destination
        if "otherwise" not in routes:
            raise ResearchError("Setiap simpul butuh jalur otherwise eksplisit.")
        questions[key] = {"id": key, "prompt": text(row["prompt"], "Pertanyaan", 420),
                          "purpose_ref": text(row["purpose_ref"], "Pointer tujuan"),
                          "minutes": integer(row["minutes"], "Menit pertanyaan", 1, limit), "routes": routes}
    if start not in questions or any(next_id not in questions for item in questions.values()
                                     for next_id in item["routes"].values() if next_id is not None):
        raise ResearchError("Pertanyaan awal atau tujuan cabang belum terdaftar.")
    finished = {}
    active = set()

    def visit(key):
        if key is None:
            return 0
        if key in active:
            raise ResearchError("Logika wawancara memiliki siklus.")
        if key not in finished:
            active.add(key)
            row = questions[key]
            finished[key] = row["minutes"] + max(visit(value) for value in row["routes"].values())
            active.remove(key)
        return finished[key]

    runtime = visit(start)
    if runtime > limit or len(finished) != len(questions):
        raise ResearchError("Jalur melampaui durasi atau ada pertanyaan tak terjangkau.")
    return start, questions, runtime


def prepare_kit(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.institute.interview-kit.v1", ("entry", "duration_cap", "questions", "responses"))
    start, bank, minutes = _prepare(plan)
    trace = []
    current = start
    for row in items(plan["responses"], 120):
        obj(row, ("question", "tag", "source_ref"))
        key = identifier(row["question"], "Pertanyaan yang dijawab")
        tag = identifier(row["tag"], "Tag jawaban")
        if key != current:
            raise ResearchError("Jawaban tidak mengikuti cabang dari kit.")
        item = bank[key]
        target = item["routes"].get(tag, item["routes"]["otherwise"])
        trace.append({"question": key, "tag": tag, "next": target, "source_ref": text(row["source_ref"], "Pointer jawaban"),
                      "purpose_ref": item["purpose_ref"]})
        current = target
    return {"schema": "ace.institute.interview-guide.v1", "plan_sha256": expected, "entry": start,
            "worst_case_minutes": minutes, "kit_sha256": identity(bank), "questions": list(bank.values()),
            "trace": trace, "next_question": bank.get(current), "status": "closed" if current is None else "incomplete"}


if __name__ == "__main__":
    raise SystemExit(cli(prepare_kit, __doc__))
