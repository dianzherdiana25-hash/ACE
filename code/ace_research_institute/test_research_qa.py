from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .deep_report_writer import make_report
from .research_qa import quality
from .test_comparison_analyst import save
from .test_deep_report_writer import report_plan


class ReportQATests(unittest.TestCase):
    def test_report_hash_rechecks_independent_measurement_rows(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = report_plan(root)
            report = make_report(inputs, identity(inputs), root)
            plan = {"schema": "ace.institute.qa-plan.v1", "report": save(root, "report.json", canonical(report)),
                    "minimum_bp": 8500, "minimum_unique_documents": 1, "minimum_limitations": 1}
            check = quality(plan, identity(plan), root)
            self.assertEqual(check["score_bp"], 10000)
            self.assertEqual(check["verified_claims"], {"valid": ["e1"]})
            report["sections"][0]["claims"][0]["amount"]["value"] = "0.9"
            plan["report"] = save(root, "report.json", canonical(report))
            check = quality(plan, identity(plan), root)
            self.assertEqual(check["status"], "hold")
            self.assertEqual(check["missing_support"], ["valid"])
            (root / "paper.md").write_text("different")
            self.assertEqual(quality(plan, identity(plan), root)["source_findings"][0]["source"], "e1")
