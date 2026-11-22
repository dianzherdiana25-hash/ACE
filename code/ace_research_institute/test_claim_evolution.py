from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .claim_evolution import evolution
from .deep_report_writer import make_report
from .test_comparison_analyst import save
from .test_deep_report_writer import report_plan


class EvolutionTests(unittest.TestCase):
    def test_changes_and_unchanged_versions_are_traced_with_chronology(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = report_plan(root)
            first = save(root, "first.json", canonical(make_report(plan, identity(plan), root)))
            plan["checks"]["claims"][0]["value"] = "53"
            last = save(root, "last.json", canonical(make_report(plan, identity(plan), root)))
            wrapped = {"schema": "ace.institute.claim-history-plan.v1", "history": [
                {"id": "last", "date": "2025-05-11", **last}, {"id": "first", "date": "2025-05-01", **first},
                {"id": "repeat", "date": "2025-05-02", **first}]}
            change = evolution(wrapped, identity(wrapped), root)
            self.assertEqual(change["ordered_versions"], ["first", "repeat", "last"])
            self.assertEqual([r["status"] for r in change["timeline"]["valid"]], ["supported", "contradicted"])
            self.assertEqual(change["timeline"]["valid"][1]["report"], last)
            self.assertEqual(len(change["timeline"]["missing"]), 1)
