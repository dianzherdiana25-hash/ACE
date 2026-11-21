"""Verifier ringkasan statistik, pemisahan warm-up, dan sampel nyata."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ace_software_factory import perf_profiler
from ace_software_factory._contracts import identity
from ace_software_factory.build_loop import _description
from ace_software_factory.repo_scaffolder import materialize


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory())) / "source"
        self.files = {"tests/test_load.py": b"import unittest\nclass Load(unittest.TestCase):\n"
                      b"    def test_total(self):\n        self.assertEqual(sum(range(5)), 10)\n"}
        materialize(self.root, self.files)
        self.plan = {"schema": "ace.factory-perf-plan.v1", "source_ref": "fixture/load", "label": "akumulasi",
                     "files": _description(self.files), "warmup": 1, "repeats": 3, "timeout_seconds": 6,
                     "expected_tests": 1, "max_p95_ns": 10}

    def test_ignores_warmup_and_reports_percentile_and_budget(self):
        outcomes = iter((0, 500, 510, 513, 600, 610, 615, 626))
        result = perf_profiler.profile(self.root, self.plan, identity(self.plan), clock=lambda: next(outcomes),
                                       runner=lambda path, limit: {"status": "passed", "tests": 1, "skipped": 0})
        self.assertEqual(result["statistics"], {"min_ns": 3, "max_ns": 11, "median_ns": 10, "p95_ns": 11, "mean_ns": 8})
        self.assertEqual(result["status"], "over_budget")
        self.assertFalse(result["samples"][0]["measured"])

    def test_missing_tests_prevent_successful_performance_verdict(self):
        result = perf_profiler.profile(self.root, self.plan, identity(self.plan),
                                       runner=lambda path, limit: {"status": "passed", "tests": 2, "skipped": 0})
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["statistics"])

    def test_profiles_a_real_offline_workload_with_monotonic_clock(self):
        self.plan.update(warmup=0, repeats=1, max_p95_ns=None)
        result = perf_profiler.profile(self.root, self.plan, identity(self.plan))
        if result["samples"][0]["test"]["status"] == "sandbox_unavailable":
            self.skipTest("bubblewrap atau user namespaces tidak tersedia")
        self.assertEqual(result["status"], "measured")
        self.assertGreater(result["statistics"]["p95_ns"], 0)
        self.assertEqual(result["samples"][0]["test"]["tests"], 1)
