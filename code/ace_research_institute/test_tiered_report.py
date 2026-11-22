from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .deep_report_writer import make_report
from .test_comparison_analyst import save
from .test_deep_report_writer import report_plan
from .tiered_report import build_tiers


class TiersTests(unittest.TestCase):
    def test_three_reader_views_preserve_sources_and_do_not_promote_gaps(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            design = report_plan(root)
            source = make_report(design, identity(design), root)
            plan = {"schema": "ace.institute.tiers-plan.v1", "report": save(root, "report.json", canonical(source)),
                    "owner_points": 1, "technical_points": 2}
            levels = build_tiers(plan, identity(plan), root)["reader_levels"]
            self.assertEqual(list(levels), ["owner", "reviewer", "technical"])
            self.assertEqual(levels["owner"]["highlights"][0]["claim_id"], "valid")
            self.assertEqual(levels["owner"]["named_gaps"][0]["claim_id"], "missing")
            self.assertEqual(levels["reviewer"]["references"], source["sources"])
            self.assertEqual(levels["technical"]["markdown_sha256"], source["markdown_sha256"])
