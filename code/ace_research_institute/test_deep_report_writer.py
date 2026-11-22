from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import ResearchError, identity
from .deep_report_writer import make_report
from .test_literature_reviewer import DIMS
from .test_source_collector import source, source_plan


def report_plan(root):
    sources = source_plan([source(root, "paper", "cohort", "| value | group | cahaya | lab | 31 | pct | 30 | - | - |")])
    claim = {"id": "valid", "text": "Cahaya 31 persen.", "value": "31", "unit": "pct",
             "source_ref": "fixture:question", "dimensions": DIMS, "tolerance": "1",
             "minimum_groups": 1, "minimum_sample": 10}
    missing = claim | {"id": "missing", "source_ref": "fixture:open", "text": "Angka belum didukung 95 persen.",
                      "value": "95", "dimensions": DIMS | {"population": "different"}}
    return {"schema": "ace.institute.report-plan.v1", "title": "Sinar", "question": "Seberapa besar cahaya?",
            "checks": {"schema": "ace.institute.claim-plan.v1", "source_plan": sources, "claims": [claim, missing]},
            "sections": [{"id": "findings", "title": "Temuan", "importance": 70, "claims": ["valid"]},
                         {"id": "open", "title": "Celah", "importance": 80, "claims": ["missing"]}],
            "limitations": ["Eksperimen hanya di meja."]}


class ReportTests(unittest.TestCase):
    def test_numeric_findings_have_citation_and_unsupported_quantity_omitted(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = report_plan(root)
            report = make_report(plan, identity(plan), root)
            self.assertIn("0.31 fraction", report["markdown"])
            self.assertIn("paper.md:6", report["markdown"])
            self.assertNotIn("95 persen", str(report))
            self.assertEqual(report["markdown_sha256"], sha256(report["markdown"].encode()).hexdigest())
            self.assertEqual(report["sections"][1]["claims"][0]["status"], "insufficient_evidence")
            plan["sections"].pop()
            with self.assertRaisesRegex(ResearchError, "belum ditempatkan"):
                make_report(plan, identity(plan), root)
