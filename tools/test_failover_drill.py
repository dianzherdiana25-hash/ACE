"""Tes perencana drill failover: determinisme seed + pengisian laporan waktu kosong (AG86)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import failover_drill


class FailoverDrillTest(unittest.TestCase):
    def test_same_seed_produces_identical_plan_and_blank_report_fills_cleanly(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            p1_file = root / "plan1.json"
            p2_file = root / "plan2.json"
            filled_file = root / "filled.json"

            self.assertEqual(
                failover_drill.main(["plan", "--seed", "42", "--date", "2026-11-25", "--out", str(p1_file)]),
                0,
            )
            self.assertEqual(
                failover_drill.main(["plan", "--seed", "42", "--date", "2026-11-25", "--out", str(p2_file)]),
                0,
            )
            self.assertEqual(p1_file.read_bytes(), p2_file.read_bytes())

            plan = json.loads(p1_file.read_text(encoding="utf-8"))
            plan_other_seed = failover_drill.build_failover_drill_plan(seed=99, window_date="2026-11-25")
            self.assertNotEqual(plan["planned_utc"], plan_other_seed["planned_utc"])

            self.assertTrue(plan["plan_only"])
            self.assertFalse(plan["executes_shutdown"])
            self.assertEqual(len(plan["shutdown_sequence"]), 3)
            self.assertTrue(all(not item["executed"] for item in plan["shutdown_sequence"]))
            self.assertEqual(plan["time_report_template"]["status"], "BLANK")
            self.assertIsNone(plan["time_report_template"]["metrics_seconds"]["total_rto"])

            # Isi laporan waktu kosong terstruktur via CLI.
            self.assertEqual(
                failover_drill.main(
                    [
                        "fill-report",
                        "--plan",
                        str(p1_file),
                        "--t-trigger",
                        "2026-11-25T10:00:00Z",
                        "--t-detected",
                        "2026-11-25T10:00:15Z",
                        "--t-takeover-complete",
                        "2026-11-25T10:01:00Z",
                        "--t-health-verified",
                        "2026-11-25T10:01:20Z",
                        "--notes",
                        "latihan terstruktur selesai",
                        "--out",
                        str(filled_file),
                    ]
                ),
                0,
            )
            filled = json.loads(filled_file.read_text(encoding="utf-8"))

        self.assertEqual(filled["schema"], failover_drill.TIME_REPORT_SCHEMA)
        self.assertEqual(filled["drill_id"], plan["drill_id"])
        self.assertEqual(filled["status"], "FILLED")
        self.assertEqual(filled["metrics_seconds"]["detection_latency"], 15.0)
        self.assertEqual(filled["metrics_seconds"]["takeover_duration"], 45.0)
        self.assertEqual(filled["metrics_seconds"]["recovery_verify_duration"], 20.0)
        self.assertEqual(filled["metrics_seconds"]["total_rto"], 80.0)


if __name__ == "__main__":
    unittest.main()
