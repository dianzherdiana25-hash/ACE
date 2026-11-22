from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .test_comparison_analyst import save
from .test_deep_report_writer import report_plan
from .viral_claim_watcher import monitor


class WatchTests(unittest.TestCase):
    def test_only_unverified_matched_growth_enters_review(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            readings = [{"claim": key, "origin": "primary", "date": when, "observations": count}
                        for key in ("valid", "missing") for when, count in (("2025-01-20", 20), ("2025-01-19", 2))]
            readings.append({"claim": "solo", "origin": "third", "date": "2025-01-20", "observations": 450})
            item = save(root, "watch.jsonl", b"\n".join(map(canonical, readings)) + b"\n")
            plan = {"schema": "ace.institute.claim-watch-plan.v1", "source": item, "as_of": "2025-01-20",
                    "window_days": 1, "minimum_new": 10, "minimum_growth": 8,
                    "claim_check": report_plan(root)["checks"]}
            report = monitor(plan, identity(plan), root)
            self.assertEqual([(r["claim_id"], r["delta"]) for r in report["needs_review"]], [("missing", 18)])
            self.assertEqual(report["needs_review"][0]["evidence_lines"], [[3], [4]])
            self.assertEqual(report["held"], [{"claim_id": "solo", "reason": "no_matched_observations"}])
