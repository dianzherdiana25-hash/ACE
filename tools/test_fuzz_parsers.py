"""Uji unit untuk harness fuzz ringan tools/fuzz_parsers.py."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from tools.fuzz_parsers import collect_targets, run_fuzz

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "fuzz_parsers.py"


class FuzzParsersTests(unittest.TestCase):
    """Memastikan harness fuzz deterministik dan bebas crash tak tertangani."""

    def test_run_fuzz_deterministic_and_zero_unhandled_crashes(self) -> None:
        r1 = run_fuzz(seed=20261117, iterations=120)
        r2 = run_fuzz(seed=20261117, iterations=120)
        self.assertEqual(r1, r2)
        self.assertTrue(r1["passed"], f"Ada crash fuzz: {r1}")
        self.assertEqual(r1["total_crashes"], 0)
        self.assertGreaterEqual(r1["target_count"], 3)

    def test_collect_targets_includes_core_tools_parsers(self) -> None:
        targets = collect_targets()
        self.assertIn("ace_mobile_dashboard.parse_logs_to_stories", targets)
        self.assertIn("ace_ai_diagnostic.audit_consultations", targets)
        self.assertIn("dashboard_state_build.rp_to_int", targets)

    def test_cli_exits_0_with_valid_json_report_and_rejects_bad_iterations(self) -> None:
        p_ok = subprocess.run(
            [sys.executable, str(SCRIPT), "--seed", "42", "--iterations", "50"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(p_ok.returncode, 0, p_ok.stderr)
        payload = json.loads(p_ok.stdout)
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["seed"], 42)

        p_bad = subprocess.run(
            [sys.executable, str(SCRIPT), "--iterations", "0"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(p_bad.returncode, 2)
        self.assertIn("Error:", p_bad.stderr)


if __name__ == "__main__":
    unittest.main()
