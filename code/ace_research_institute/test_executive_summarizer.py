from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ResearchError, canonical, identity
from .deep_report_writer import make_report
from .executive_summarizer import summarize
from .test_deep_report_writer import report_plan


class SummaryTests(unittest.TestCase):
    def test_report_retains_supporting_evidence_and_gap_and_rejects_unlinked_citation(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            generation = report_plan(root)
            report = make_report(generation, identity(generation), root)

            def save(data):
                raw = canonical(data)
                (root / "report.json").write_bytes(raw)
                return {"path": "report.json", "sha256": sha256(raw).hexdigest()}

            plan = {"schema": "ace.institute.executive-summary-plan.v1",
                    "report": save(report), "max_points": 2, "max_held": 1}
            result = summarize(plan, identity(plan), root)
            self.assertEqual(result["highlights"][0]["amount"], {"value": "0.31", "unit": "fraction"})
            self.assertEqual(result["highlights"][0]["evidence"][0]["line"], 6)
            self.assertEqual(result["named_gaps"][0]["claim_id"], "missing")
            self.assertEqual(result["limitations"], ["Eksperimen hanya di meja."])
            report["sections"][0]["claims"][0]["sources"][0]["line"] = 1
            plan["report"] = save(report)
            with self.assertRaisesRegex(ResearchError, "Sitasi"):
                summarize(plan, identity(plan), root)
