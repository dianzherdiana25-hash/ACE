import unittest

from ._contracts import identity
from .feedback_writer import feedback
from .test_grader import grade


class FeedbackTests(unittest.TestCase):
    def test_graded_response_maps_to_specific_repair_or_open_material_gap(self):
        plan = {"schema": "ace.teaching.feedback-plan.v1", "grade": grade(),
                "actions": [{"criterion": "volume", "practice": "Bandingkan diagram dua wadah.",
                             "source_ref": "fixture:diagram"}]}
        result = feedback(plan, identity(plan))
        self.assertEqual(result["improvement"][0]["id"], "volume")
        self.assertEqual(result["improvement"][0]["next_action"]["source_ref"], "fixture:diagram")
        self.assertEqual(result["missing_action"], ["reason"])
        self.assertEqual(result["strengths"][0]["id"], "state")
