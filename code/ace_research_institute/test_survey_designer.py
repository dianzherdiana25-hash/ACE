import unittest

from ._contracts import ResearchError, identity
from .survey_designer import design_survey


class SurveyDesignTests(unittest.TestCase):
    def test_items_and_gates_preserve_consent_and_reverse_scoring(self):
        base = {"prompt": "Pertanyaan fixture?", "construct": "clarity", "source_ref": "fixture:item",
                "required": True, "visibility": None}
        plan = {"schema": "ace.institute.survey-plan.v1", "study": "fixture", "purpose": "Evaluasi materi",
                "consent_text": "Partisipasi bersifat sukarela.", "seed": 31, "constructs": [
                    {"id": "clarity", "definition": "Kejelasan petunjuk", "min_items": 2}],
                "questions": [base | {"id": "screen", "kind": "screen",
                    "options": [{"id": "yes", "label": "Ya"}, {"id": "no", "label": "Tidak"}]},
                    base | {"id": "rating", "kind": "likert", "scale_min": 1, "scale_max": 5, "reverse": True},
                    base | {"id": "follow", "kind": "open", "max_chars": 120,
                            "visibility": {"depends_on": "screen", "equals": "yes"}}]}
        report = design_survey(plan, identity(plan))
        self.assertEqual(report["sequence"][0]["id"], "screen")
        by_id = {row["id"]: row for row in report["sequence"]}
        self.assertEqual(by_id["rating"]["scale"], [1, 2, 3, 4, 5])
        self.assertTrue(by_id["rating"]["reverse_score"])
        self.assertEqual(by_id["follow"]["visibility"]["equals"], "yes")
        self.assertEqual(report, design_survey(plan, identity(plan)))
        plan["questions"][2]["visibility"]["depends_on"] = "rating"
        with self.assertRaisesRegex(ResearchError, "screening terdahulu"):
            design_survey(plan, identity(plan))
