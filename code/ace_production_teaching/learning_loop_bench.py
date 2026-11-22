"""Bandingkan replika learner simulasi yang sama dengan dan tanpa petunjuk pada latihan terpisah."""
from collections import defaultdict
from fractions import Fraction

from ._contracts import ProductionError, anchor, cli, decode, identifier, identity, integer, items, obj, schema, source_bytes
from .feedback_writer import feedback
from .grader import assess
from .hint_engine import next_hint

STRATEGIES = {
    "sum": ("jumlahkan kedua bilangan", lambda a, b: a + b),
    "product": ("jumlahkan kelompok berulang", lambda a, b: sum(a for _ in range(b))),
    "difference": ("kurangi bilangan kedua dari pertama", lambda a, b: a - b),
}
TOPICS = {"add": "sum", "multiply": "product", "subtract": "difference"}

def _problem(raw):
    problem = obj(raw, ("id", "topic", "operands"))
    key = identifier(problem["id"], "Latihan")
    topic = identifier(problem["topic"], "Topik")
    if topic not in TOPICS:
        raise ProductionError("Topik latihan simulasi tidak dikenal.")
    sides = tuple(integer(value, "Operand loop", 2, 40) for value in items(problem["operands"], 2, 2))
    signature = tuple(sorted(sides)) if topic != "subtract" else sides
    return key, topic, sides, (topic, *signature)

def _rubric(key, expected, answer, reference):
    def signed_token(value):
        sign = "negative" if value < 0 else "nonnegative"
        return f"answer_{sign}_{abs(value)}"
    return {"schema": "ace.teaching.open-grade-plan.v1", "exercise": key, "passing_bp": 10_000,
            "response": {"text": signed_token(answer), "source_ref": f"fixture:attempt:{key}"},
            "criteria": [{"id": "value", "weight": 10_000, "hits_needed": 1, "must_mention": [signed_token(expected)],
                          "contradictions": [], "source_ref": reference}]}

def _feedback(key, expected, reply):
    grade = _rubric(key, expected, reply, f"fixture:practice:{key}")
    data = {"schema": "ace.teaching.feedback-plan.v1", "grade": grade,
            "actions": [{"criterion": "value", "practice": "Pilih operasi yang sesuai dengan arti soal.",
                         "source_ref": f"fixture:practice:{key}"}]}
    return feedback(data, identity(data))

def _hint(key, expected, chain):
    data = {"schema": "ace.teaching.hint-plan.v1", "exercise": key, "provided_ids": [],
            "answer_forms": [str(expected)], "chain": chain}
    result = next_hint(data, identity(data))
    candidate = result["hint"]
    learned = next((method for method, (phrase, _) in STRATEGIES.items()
                    if candidate and candidate["prompt"] == phrase), None)
    return learned, identity(result)

def _arm(practice, held, initial, hints, count, treated):
    known = dict(initial)
    verified = defaultdict(set)
    trace = []
    for (key, topic, operands, signature), expected in practice:
        before = STRATEGIES[known.get(topic, "sum")][1](*operands)
        baseline_grade = _feedback(key, expected, before)
        if baseline_grade["score_bp"] == 10_000 or not treated:
            trace.append({"id": key, "topic": topic, "initial_score_bp": baseline_grade["score_bp"],
                          "hint_receipt": None, "corrected_score_bp": None, "learned": None})
            continue
        strategy, receipt = _hint(key, expected, hints[topic])
        corrected = None
        if strategy is not None:
            retry = STRATEGIES[strategy][1](*operands)
            correction = _feedback(key, expected, retry)
            corrected = correction["score_bp"]
            if corrected == 10_000:
                verified[(topic, strategy)].add(signature)
        learned = None
        if strategy is not None and len(verified[(topic, strategy)]) >= count:
            known[topic] = strategy
            learned = strategy
        trace.append({"id": key, "topic": topic, "initial_score_bp": baseline_grade["score_bp"],
                      "hint_receipt": receipt, "corrected_score_bp": corrected, "learned": learned})
    answers = []
    for (key, topic, operands, _), expected in held:
        predicted = STRATEGIES[known.get(topic, "sum")][1](*operands)
        mark = _rubric(key, expected, predicted, f"fixture:heldout:{key}")
        assessed = assess(mark, identity(mark))
        answers.append({"id": key, "prediction": predicted, "correct": assessed["status"] == "passes_rubric"})
    return {"trace": trace, "known": known, "answered": answers, "correct": sum(row["correct"] for row in answers)}

def bench(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.teaching.learning-loop.v1", ("holdout", "practice", "initial", "hints", "verified_corrections"))
    scope = obj(plan["holdout"], ("path", "sha256"))
    payload = decode(source_bytes(root, scope["path"], scope["sha256"], 500_000))
    schema(payload, "ace.teaching.learning-holdout.v1", ("cases",))
    correction_count = integer(plan["verified_corrections"], "Perbaikan terverifikasi", 1, 10)
    if not isinstance(plan["initial"], dict) or set(plan["initial"]) - TOPICS.keys() or any(
        not isinstance(value, str) or value not in STRATEGIES for value in plan["initial"].values()
    ):
        raise ProductionError("Strategi awal pola latihan tidak sah.")
    hints = obj(plan["hints"], TOPICS.keys())
    ids, signatures = set(), set()
    practice = []
    held = []
    for row in items(plan["practice"], 120, 1):
        problem = _problem(row)
        key, topic, operands, signature = problem
        if key in ids or signature in signatures:
            raise ProductionError("Latihan berulang.")
        ids.add(key)
        signatures.add(signature)
        practice.append((problem, STRATEGIES[TOPICS[topic]][1](*operands)))
    for row in items(payload["cases"], 240, 1):
        obj(row, ("problem", "answer"))
        problem = _problem(row["problem"])
        if problem[0] in ids or problem[-1] in signatures:
            raise ProductionError("Held-out berbagi ID atau operand dengan latihan.")
        ids.add(problem[0])
        signatures.add(problem[-1])
        held.append((problem, integer(row["answer"], "Kunci held-out", -1600, 1600)))
    without = _arm(practice, held, plan["initial"], hints, correction_count, False)
    taught = _arm(practice, held, plan["initial"], hints, correction_count, True)
    delta = taught["correct"] - without["correct"]
    return {"scope": "deterministic_learner_with_observed_practice_corrections", "plan_sha256": expected,
            "holdout": scope, "tasks": len(held), "without_hint": without, "with_hint": taught,
            "delta_correct": delta, "gain_fraction": str(Fraction(delta, len(held))),
            "relative_gain": str(Fraction(delta, without["correct"])) if without["correct"] else None}

if __name__ == "__main__":
    raise SystemExit(cli(bench, __doc__, rooted=True))
