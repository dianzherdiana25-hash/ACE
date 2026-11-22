"""Kalibrasi bank latihan dari jawaban fixture terikat pertanyaan dan kunci yang sama."""
from collections import defaultdict

from ._contracts import (ProductionError, anchor, cli, decode, identifier, identity,
                         integer, number, obj, schema, source_bytes)
from .exercise_generator import generate


def calibrate(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.question-bank-plan.v1", ("generator", "attempts", "minimum_attempts"))
    minimum = integer(plan["minimum_attempts"], "Jumlah learner unik", 1, 200)
    generated = generate(plan["generator"], identity(plan["generator"]))
    keys = {row["id"]: row for row in [*generated["practice_key"], *generated["held_out_key"]]}
    questions = {row["id"]: row for row in generated["questions"]}
    source = obj(plan["attempts"], ("path", "sha256"))
    stream = source_bytes(root, source["path"], source["sha256"], 1_500_000)
    observations = defaultdict(dict)
    for line, row in enumerate(stream.splitlines(), 1):
        if line > 30000:
            raise ProductionError("Jumlah percobaan bank melewati batas.")
        if not row.strip():
            continue
        value = obj(decode(row), ("question", "question_sha256", "learner", "answer"))
        name = identifier(value["question"], "Soal percobaan")
        learner = identifier(value["learner"], "ID learner")
        key = keys.get(name)
        if key is None or key["question_sha256"] != value["question_sha256"] or learner in observations[name]:
            raise ProductionError("Percobaan ganda, soal asing atau hash prompt berbeda.")
        answer = number(value["answer"], "Jawaban numerik")
        observations[name][learner] = (answer == number(key["answer"], "Kunci"), line)
    bank = []
    for name, item in sorted(questions.items()):
        rows = observations[name]
        count = len(rows)
        correct = sum(passed for passed, _ in rows.values())
        rate = correct * 10000 // count if count else None
        band = "uncalibrated" if count < minimum else (
            "hard" if rate < 3500 else ("moderate" if rate < 7500 else "easy"))
        bank.append({"question": item, "question_sha256": keys[name]["question_sha256"], "attempts": count, "correct": correct,
                     "success_bp": rate, "empirical_difficulty": band, "source_lines": sorted(line for _, line in rows.values())})
    return {"schema": "ace.teaching.calibrated-bank.v1", "plan_sha256": expected,
            "attempts": source, "scope": "one_attempt_per_learner_per_question",
            "questions": bank, "total_calibrated": sum(row["empirical_difficulty"] != "uncalibrated" for row in bank)}


if __name__ == "__main__":
    raise SystemExit(cli(calibrate, __doc__, rooted=True))
