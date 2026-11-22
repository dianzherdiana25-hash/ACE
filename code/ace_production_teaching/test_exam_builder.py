import unittest

from ._artifacts import unpack
from ._contracts import ProductionError, identity
from .exam_builder import exam
from .exercise_generator import generate
from .test_exercise_generator import exercises


class ExamsTests(unittest.TestCase):
    def test_heldout_answers_separate_from_readable_prompt(self):
        bank = exercises()
        plan = {"schema": "ace.teaching.exam-plan.v1", "title": "Ujian zona", "bank": bank,
                "seed": 9, "minutes": 15, "formats": ["docx"], "targets": [
                   {"topic": "numeric", "level": 3, "count": 2, "points_each": 5}]}
        data, key, report = exam(plan, identity(plan))
        self.assertEqual(report["total_points"], 10)
        self.assertEqual(report["key_sha256"], identity(key))
        questions = {row["id"]: row for row in generate(bank, identity(bank))["questions"]}
        body = unpack(data["document.docx"])["word/document.xml"].decode()
        for answer in key["answers"]:
            item = questions[answer["item_id"]]
            self.assertEqual(item["split"], "held_out")
            self.assertIn(item["prompt"], body)
        self.assertNotIn("answers", body)
        plan["targets"][0]["count"] += 1
        with self.assertRaisesRegex(ProductionError, "held-out"):
            exam(plan, identity(plan))
