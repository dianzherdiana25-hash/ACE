from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .deep_report_writer import make_report
from .institute_quarterly import quarterly
from .test_comparison_analyst import save
from .test_deep_report_writer import report_plan


class QuarterlyTests(unittest.TestCase):
    def test_quarter_exclusive_boundary_and_missing_reports_do_not_dilute_denominator(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            draft = report_plan(root)
            report = save(root, "report.json", canonical(make_report(draft, identity(draft), root)))
            plan = {"schema": "ace.institute.quarter-plan.v1", "quarter": "2025-Q1", "minimum_score_bp": 8000,
                    "sources": [{"id": label, "completed_date": date, "source_ref": "fixture:roster", "report": evidence}
                                for label, date, evidence in (("main", "2025-03-31", report),
                                                               ("open", "2025-03-31", None), ("later", "2025-04-01", report))]}
            summary = quarterly(plan, identity(plan), root)
            self.assertEqual((summary["reviewed_count"], summary["rubric_passes"], summary["median_rubric_bp"]), (1, 1, 10000))
            self.assertEqual(summary["period"], ["2025-01-01", "2025-04-01"])
            self.assertEqual(summary["evidence_gaps"][0]["id"], "open")
            self.assertEqual(summary["out_of_quarter"][0]["id"], "later")
