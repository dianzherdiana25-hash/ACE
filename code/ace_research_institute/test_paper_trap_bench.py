from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ._contracts import canonical, identity
from .paper_trap_bench import bench_traps
from .test_comparison_analyst import save
from .test_source_collector import HEADER


class TrapTests(unittest.TestCase):
    def test_hold_is_reported_when_expected_claims_do_not_match(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            rows = ("## Introduction\n" + HEADER + "| bait | group | speed | lab | 100 | s | 8 | - | - |\n"
                    + "## Results\n" + HEADER + "| real | group | speed | lab | 6 | s | 8 | 2 | 7 |\n"
                    + "| bad | group | speed | lab | 6 | s | 8 | 9 | 10 |\n")
            source = save(root, "trap.md", rows.encode())
            gold = {"schema": "ace.institute.paper-trap-gold.v1", "papers": [
                {"id": "trap", "never_accept": ["bait", "bad"], "accept": ["real"], "minimum_holds": 1}]}
            plan = {"schema": "ace.institute.paper-trap-plan.v1", "gold": save(root, "gold.json", canonical(gold)),
                    "paper_plan": {"schema": "ace.institute.paper-plan.v1", "papers": [
                        {"id": "trap", "title": "Fixture", "independence_group": "fixture", **source}]}}
            result = bench_traps(plan, identity(plan), root)
            self.assertEqual(result["passed"], 1)
            self.assertEqual(result["cases"][0]["present"], ["real"])
            gold["papers"][0]["accept"] = ["real", "made_up"]
            plan["gold"] = save(root, "gold.json", canonical(gold))
            result = bench_traps(plan, identity(plan), root)
            self.assertEqual(result["status"], "fixture_hold")
            self.assertEqual(result["cases"][0]["missed_claims"], ["made_up"])
