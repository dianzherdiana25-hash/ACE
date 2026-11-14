"""Tests for the unified OAIE-∞ CLI (`ace_operational.oaie_cli`)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class OaieCliTests(unittest.TestCase):
    def _run_cli(self, workspace: Path, *args: str) -> dict:
        proc = subprocess.run(
            [sys.executable, "-m", "ace_operational.oaie_cli", "--workspace", str(workspace), *args],
            cwd=str(Path(__file__).resolve().parents[2]),
            env={**os.environ, "PYTHONPATH": "code"},
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return json.loads(proc.stdout)

    def test_cli_status_run_cycle_factory_and_work_order(self) -> None:
        with tempfile.TemporaryDirectory() as d1:
            ws = Path(d1)
            st = self._run_cli(ws, "status")
            self.assertTrue(st["dag_chain_valid"])

            rc = self._run_cli(ws, "run-cycle", "--cycles", "3")
            self.assertTrue(rc["verified_unlimited_ok"])
            self.assertEqual(rc["unhandled_crashes"], 0)
            self.assertGreaterEqual(rc["synthesized_skills"], 4)

            fac = self._run_cli(ws, "factory")
            self.assertEqual(len(fac["products"]), 2)
            self.assertEqual(fac["receipts_verified_o1"], [True, True])

            ev = self._run_cli(ws, "evolve-once", "--generation-id", "gen-cli")
            self.assertEqual(ev["epoch_a_skills_synthesized"], 4)
            self.assertTrue(ev["dag_chain_valid"])

            wo = self._run_cli(ws, "work-order", "--order-id", "wo-test", "--goal", "Verify CLI")
            self.assertEqual(len(wo["order_sha256"]), 64)
            self.assertTrue((ws / "ACE_WORK_ORDER.json").exists())


if __name__ == "__main__":
    unittest.main()
