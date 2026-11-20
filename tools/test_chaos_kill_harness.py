"""Tes chaos-kill dua titik bunuh berbeda + bandingkan state akhir vs lari utuh (AG75)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import chaos_kill_harness


class ChaosKillHarnessTest(unittest.TestCase):
    def test_two_different_kill_points_produce_identical_final_state(self) -> None:
        with TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "chaos.json"
            rc = chaos_kill_harness.main(
                ["--steps", "6", "--kill-at", "2,4", "--out", str(out_path)]
            )
            self.assertEqual(rc, 0)
            rep = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertEqual(rep["schema"], chaos_kill_harness.SCHEMA)
        self.assertTrue(rep["all_identical"])
        self.assertEqual(len(rep["scenarios"]), 2)
        for scenario, kp in zip(rep["scenarios"], (2, 4)):
            self.assertEqual(scenario["kill_after_step"], kp)
            self.assertTrue(scenario["child_killed_before_completion"])
            self.assertEqual(scenario["resumed_from_checkpoint_step"], kp)
            self.assertTrue(scenario["matches_unbroken_baseline"])
            self.assertEqual(scenario["resumed_digest"], scenario["baseline_digest"])


if __name__ == "__main__":
    unittest.main()
