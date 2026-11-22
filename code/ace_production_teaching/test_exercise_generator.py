import unittest

from ._contracts import ProductionError, identity
from .exercise_generator import generate


def exercises():
    return {"schema": "ace.teaching.exercise-plan.v1", "seed": 41, "count_per_template": 4, "held_out": 2,
            "templates": [
                {"id": "sum", "topic": "numeric", "level": 1, "operation": "addition", "a": [1, 8], "b": [1, 8],
                 "prompt": "Jumlahkan {a} dan {b}.", "unit": "buah", "source_ref": "fixture:sum"},
                {"id": "divide", "topic": "numeric", "level": 3, "operation": "division", "a": [8, 20], "b": [0, 4],
                 "prompt": "Bagi {a} dengan {b}.", "unit": "buah", "source_ref": "fixture:divide"}]}


class ExerciseTests(unittest.TestCase):
    def test_tiers_distinct_held_out_operators_and_answers_are_mechanical(self):
        plan = exercises()
        run = generate(plan, identity(plan))
        self.assertEqual(run["held_out_key_sha256"], identity(run["held_out_key"]))
        self.assertEqual([item["level"] for item in run["questions"]], [1] * 4 + [3] * 4)
        practice = {item["id"] for item in run["practice_key"]}
        self.assertTrue(practice.isdisjoint({item["id"] for item in run["held_out_key"]}))
        seen = set()
        for row in run["practice_key"] + run["held_out_key"]:
            a, b = row["operands"]
            if row["method"] == "addition":
                self.assertEqual(int(row["answer"]), a + b)
                signature = tuple(sorted((a, b)))
                self.assertNotIn(signature, seen)
                seen.add(signature)
            else:
                self.assertEqual((a % b, int(row["answer"])), (0, a // b))
        self.assertEqual(run, generate(plan, identity(plan)))
        plan["templates"][1]["b"] = [0, 0]
        with self.assertRaisesRegex(ProductionError, "operand unik"):
            generate(plan, identity(plan))
