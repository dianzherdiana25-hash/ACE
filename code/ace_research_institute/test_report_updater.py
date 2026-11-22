from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .deep_report_writer import make_report
from .report_updater import update
from .test_comparison_analyst import save
from .test_deep_report_writer import report_plan


class UpdateTests(unittest.TestCase):
    def test_new_estimate_changes_status_with_old_receipt_intact(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            generation = report_plan(root)
            report = make_report(generation, identity(generation), root)
            raw = canonical(report)
            original = save(root, "previous.json", raw)
            generation["checks"]["claims"][0]["value"] = "75"
            plan = {"schema": "ace.institute.update-plan.v1", "previous": original, "new_plan": generation}
            results = update(plan, identity(plan), root)
            self.assertEqual(results["unchanged_claims"], 1)
            self.assertEqual(results["change_list"][0]["after"]["status"], "contradicted")
            self.assertEqual(results["change_list"][0]["changed_fields"], ["amount", "status"])
            self.assertEqual((root / "previous.json").read_bytes(), raw)
