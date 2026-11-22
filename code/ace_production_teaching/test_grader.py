import unittest

from ._contracts import identity
from .grader import assess


def grade(exercise="answer"):
    return {"schema": "ace.teaching.open-grade-plan.v1", "exercise": exercise, "passing_bp": 6000,
            "response": {"text": "Suhu tetap namun volume tidak tetap. Massa stabil.", "source_ref": "fixture:reply"},
            "criteria": [
                {"id": "state", "weight": 3000, "hits_needed": 2, "must_mention": ["suhu", "tetap"],
                 "contradictions": [], "source_ref": "fixture:state"},
                {"id": "volume", "weight": 4000, "hits_needed": 1, "must_mention": ["volume"],
                 "contradictions": ["volume tidak tetap"], "source_ref": "fixture:volume"},
                {"id": "reason", "weight": 3000, "hits_needed": 2, "must_mention": ["massa", "gas"],
                 "contradictions": [], "source_ref": "fixture:reason"}]}


class GradingTests(unittest.TestCase):
    def test_exact_phrase_contradiction_overrides_surface_hit_and_partial_credit(self):
        plan = grade()
        report = assess(plan, identity(plan))
        self.assertEqual(report["score_bp"], 4500)
        self.assertEqual([item["earned_bp"] for item in report["criteria"]], [3000, 0, 1500])
        self.assertEqual(report["criteria"][1]["opposed_by"], ["volume tidak tetap"])
        self.assertNotIn(plan["response"]["text"], str(report))
