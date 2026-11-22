from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .research_costing import cost
from .test_comparison_analyst import save


class TimeCostTests(unittest.TestCase):
    def test_overlap_merged_wait_separate_and_null_active_reported(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = b"\n".join(canonical({"id": f"r{i}", "study": study, "kind": kind, "depth": "deep",
                    "start": f"2025-01-01T00:00:{start:02d}Z", "end": f"2025-01-01T00:00:{end:02d}Z"})
                    for i, (study, kind, start, end) in enumerate(
                        (("base", "active", 0, 20), ("base", "active", 10, 35),
                         ("base", "wait", 35, 50), ("next", "active", 0, 25), ("blank", "wait", 10, 20))))
            plan = {"schema": "ace.institute.research-cost-plan.v1", "receipts": save(root, "times", raw)}
            result = cost(plan, identity(plan), root)["by_depth"][0]
            self.assertEqual((result["complete"], result["total"], result["median_active_seconds"]), (2, 3, "30"))
            self.assertEqual(result["active_seconds_total"], "60")
            self.assertEqual(result["studies"][0]["declared_wait_seconds"], 15)
            self.assertIsNone(result["studies"][1]["active_seconds"])
