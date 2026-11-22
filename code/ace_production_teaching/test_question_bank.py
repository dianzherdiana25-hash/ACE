from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ProductionError, canonical, identity
from .exercise_generator import generate
from .question_bank import calibrate
from .test_exercise_generator import exercises
from .test_tabular_engine import save


class CalibratedBankTests(unittest.TestCase):
    def test_difficulty_is_scored_from_unique_learners_and_pinned_prompts(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            bank = exercises()
            target = generate(bank, identity(bank))["practice_key"][0]
            rows = [{"question": target["id"], "question_sha256": target["question_sha256"], "learner": key,
                     "answer": response} for key, response in (("first", target["answer"]), ("second", "-99"))]
            plan = {"schema": "ace.teaching.question-bank-plan.v1", "generator": bank, "minimum_attempts": 2,
                    "attempts": save(root, "attempts", b"\n".join(map(canonical, rows)))}
            output = calibrate(plan, identity(plan), root)
            grade = next(row for row in output["questions"] if row["question"]["id"] == target["id"])
            self.assertEqual((grade["success_bp"], grade["empirical_difficulty"]), (5000, "moderate"))
            self.assertEqual(output["total_calibrated"], 1)
            rows[0]["question_sha256"] = "a" * 64
            plan["attempts"] = save(root, "attempts", b"\n".join(map(canonical, rows)))
            with self.assertRaisesRegex(ProductionError, "hash prompt"):
                calibrate(plan, identity(plan), root)
