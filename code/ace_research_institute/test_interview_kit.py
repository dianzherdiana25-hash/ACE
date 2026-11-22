import unittest

from ._contracts import ResearchError, identity
from .interview_kit import prepare_kit


class InterviewTests(unittest.TestCase):
    def test_expected_branch_and_timing_guards(self):
        plan = {"schema": "ace.institute.interview-kit.v1", "entry": "screen", "duration_cap": 6,
                "questions": [{"id": "screen", "prompt": "Cuaca terlihat?", "minutes": 2, "purpose_ref": "fixture:screen",
                    "routes": [{"tag": "yes", "next": "probe"}, {"tag": "otherwise", "next": None}]},
                    {"id": "probe", "prompt": "Apa yang terlihat?", "minutes": 4, "purpose_ref": "fixture:probe",
                    "routes": [{"tag": "otherwise", "next": None}]}],
                "responses": [{"question": "screen", "tag": "yes", "source_ref": "fixture:reply"}]}
        report = prepare_kit(plan, identity(plan))
        self.assertEqual(report["worst_case_minutes"], 6)
        self.assertEqual(report["next_question"]["id"], "probe")
        self.assertEqual(report["trace"][0]["source_ref"], "fixture:reply")
        plan["responses"].append({"question": "probe", "tag": "seen", "source_ref": "fixture:anecdote"})
        self.assertEqual(prepare_kit(plan, identity(plan))["status"], "closed")
        plan["questions"][1]["routes"][0]["next"] = "screen"
        with self.assertRaisesRegex(ResearchError, "siklus"):
            prepare_kit(plan, identity(plan))
