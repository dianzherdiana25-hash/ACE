import unittest

from ._contracts import identity
from .socratic_questioner import ask
from .test_grader import grade


class SocraticTests(unittest.TestCase):
    def test_ask_conflict_before_partial_and_skip_answer_disclosure(self):
        plan = {"schema": "ace.teaching.socratic-plan.v1", "grade_input": grade(), "seen": [], "protected_answer": ["tetap"],
                "question_bank": [
                   {"id": label, "focus_criterion": criterion, "type": kind, "question": question,
                    "priority": 5, "source_ref": f"fixture:{label}"}
                   for label, criterion, kind, question in (
                       ("false", "volume", "contrast", "Apakah tetap?"),
                       ("why", "volume", "justify", "Mengapa berubah?"),
                       ("second", "reason", "clarify", "Apa yang berperan?"))]}
        result = ask(plan, identity(plan))
        self.assertEqual(result["selected"]["id"], "why")
        self.assertEqual(result["held"], [{"id": "false", "reason": "reserved_answer_overlap"}])
        plan["seen"] = ["why"]
        self.assertEqual(ask(plan, identity(plan))["selected"]["id"], "second")
