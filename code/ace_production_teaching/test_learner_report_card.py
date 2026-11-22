from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._artifacts import unpack
from ._contracts import identity
from .learner_report_card import report_card
from .test_learner_model import profile


class ReportCardTests(unittest.TestCase):
    def test_period_specific_score_and_null_visible_in_native_report(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = {"schema": "ace.teaching.report-card-plan.v1", "profile": profile(root),
                    "start": "2025-04-10", "title": "Rapor", "formats": ["docx"]}
            files, receipt = report_card(plan, identity(plan), root)
            base, target = receipt["topics"]
            self.assertEqual(base["points"], [2, 4])
            self.assertEqual(base["period_score_bp"], 5000)
            self.assertEqual(base["attempt_refs"][0]["line"], 2)
            self.assertIsNone(target["period_score_bp"])
            self.assertIn(b"Belum diukur", unpack(files["document.docx"])["word/document.xml"])
