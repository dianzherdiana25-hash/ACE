from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .agenda_generator import propose_agenda
from .test_deep_report_writer import report_plan
from .test_literature_reviewer import hypotheses


class AgendaTests(unittest.TestCase):
    def test_conflicts_precede_missing_and_no_idea_invented_for_closed_claims(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            checks = report_plan(root)["checks"]
            checks["source_plan"] = hypotheses(root)
            plan = {"schema": "ace.institute.agenda-plan.v1", "checks": checks, "origin": "institute",
                    "limit": 1, "source_ref": "fixture:claim-audit"}
            result = propose_agenda(plan, identity(plan), root)
            entry = result["candidates"][0]
            self.assertEqual(entry["claim_id"], "valid")
            self.assertEqual(entry["why"], "mixed_evidence")
            self.assertEqual(entry["based_on"], ["fixture:claim-audit", "fixture:question"])
            self.assertEqual(entry["brain_of_origin"], "institute")
            self.assertEqual(result["deferred_claims"], ["missing"])
