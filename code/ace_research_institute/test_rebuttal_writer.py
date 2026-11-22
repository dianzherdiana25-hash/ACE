from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import identity
from .rebuttal_writer import rebut
from .test_literature_reviewer import DIMS, hypotheses


class RebuttalTests(unittest.TestCase):
    def test_contradiction_and_support_both_preserved_with_minimum_group_break(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = {"schema": "ace.institute.rebuttal-plan.v1", "target": "target",
                    "minimum_conflicting_groups": 1, "max_cites": 3, "limitation": "Hanya konteks lab.",
                    "checks": {"schema": "ace.institute.claim-plan.v1", "source_plan": hypotheses(root), "claims": [
                        {"id": "target", "text": "Angka cahaya", "source_ref": "fixture:claim", "dimensions": DIMS,
                         "value": "31", "unit": "pct", "tolerance": "1", "minimum_groups": 1, "minimum_sample": 5}]}}
            report = rebut(plan, identity(plan), root)
            self.assertEqual(report["status"], "counterevidence_found")
            self.assertIn("0.46 fraction", report["markdown"])
            self.assertIn("left.md:6", report["markdown"])
            self.assertNotIn("wrong.md", report["markdown"])
            plan["minimum_conflicting_groups"] = 2
            self.assertEqual(rebut(plan, identity(plan), root)["status"], "waiting_for_evidence")
