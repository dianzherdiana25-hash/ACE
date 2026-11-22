import unittest

from ._contracts import ProductionError, identity
from .exercise_generator import generate
from .explained_key import explain_answers
from .test_exercise_generator import exercises


class KeyExplanationsTests(unittest.TestCase):
    def test_division_explanation_verifies_zero_remainder_and_locked_key(self):
        table = exercises()
        content = generate(table, identity(table))
        keys = content["practice_key"] + content["held_out_key"]
        choices = [row["id"] for row in keys if row["method"] == "division"]
        plan = {"schema": "ace.teaching.explained-key-plan.v1", "generator": table, "ids": choices,
                "expected_key_sha256": identity(keys)}
        receipt = explain_answers(plan, identity(plan))
        self.assertTrue(all(row["steps"][-1]["result"] == 0 for row in receipt["items"]))
        self.assertTrue(receipt["instructor_only"])
        plan["expected_key_sha256"] = "e" * 64
        with self.assertRaisesRegex(ProductionError, "anchor"):
            explain_answers(plan, identity(plan))
