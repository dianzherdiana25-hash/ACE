"""Uji unit untuk harness fuzz ringan tools/fuzz_parsers.py."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from tools.fuzz_parsers import (
    FUZZ_MATRIX_SCHEMA,
    STANDARD_ITERATIONS,
    STANDARD_SEEDS,
    collect_targets,
    run_fuzz,
    run_fuzz_matrix,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "fuzz_parsers.py"
FUZZ_DOC = REPO_ROOT / "tools" / "FUZZ_STANDARD.md"


class FuzzParsersTests(unittest.TestCase):
    """Memastikan harness fuzz deterministik dan bebas crash tak tertangani."""

    def test_run_fuzz_deterministic_and_zero_unhandled_crashes(self) -> None:
        r1 = run_fuzz(seed=20261117, iterations=120)
        r2 = run_fuzz(seed=20261117, iterations=120)
        self.assertEqual(r1, r2)
        self.assertTrue(r1["passed"], f"Ada crash fuzz: {r1}")
        self.assertEqual(r1["total_crashes"], 0)
        self.assertGreaterEqual(r1["target_count"], 7)

    def test_three_seeds_300_iterations_matrix_passes_with_zero_crashes(self) -> None:
        matrix = run_fuzz_matrix(seeds=STANDARD_SEEDS, iterations=STANDARD_ITERATIONS)
        self.assertEqual(matrix["schema"], FUZZ_MATRIX_SCHEMA)
        self.assertEqual(matrix["seeds"], [20261117, 20261118, 20261119])
        self.assertEqual(matrix["iterations_per_target"], 300)
        self.assertEqual(matrix["total_runs"], 3)
        self.assertEqual(matrix["total_crashes"], 0)
        self.assertTrue(matrix["passed"], f"Ada crash fuzz matrix: {matrix}")

    def test_collect_targets_includes_tools_and_safe_code_parsers(self) -> None:
        targets = collect_targets()
        self.assertIn("ace_mobile_dashboard.parse_logs_to_stories", targets)
        self.assertIn("ace_ai_diagnostic.audit_consultations", targets)
        self.assertIn("dashboard_state_build.rp_to_int", targets)
        self.assertIn("code.ace_visual_bridge.cli.process", targets)
        self.assertIn("code.ace_host_exchange.contracts.verify", targets)
        self.assertIn("code.ace_autonomy.policy.BudgetCeiling", targets)
        self.assertIn("code.ace_code_agent.read_failure_history", targets)
        self.assertTrue(FUZZ_DOC.is_file())

    def test_cli_exits_0_with_valid_json_report_and_rejects_bad_args(self) -> None:
        p_ok = subprocess.run(
            [sys.executable, str(SCRIPT), "--seeds", "20261117,20261118", "--iterations", "50"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(p_ok.returncode, 0, p_ok.stderr)
        payload = json.loads(p_ok.stdout)
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["seeds"], [20261117, 20261118])

        p_bad = subprocess.run(
            [sys.executable, str(SCRIPT), "--iterations", "0"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(p_bad.returncode, 2)
        self.assertIn("Error:", p_bad.stderr)

        p_bad_seeds = subprocess.run(
            [sys.executable, str(SCRIPT), "--seeds", "abc"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(p_bad_seeds.returncode, 2)


if __name__ == "__main__":
    unittest.main()
