"""Tes regresi fixture-only untuk tools.engine_idle_report (AG48)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools import engine_idle_report


class EngineIdleReportTest(unittest.TestCase):
    def test_exhausted_day_2026_11_20_vs_healthy_comparison_day(self) -> None:
        # Hari sehat (2026-11-19): siklus konstan 60s, tanpa exhausted, idle 0 menit.
        log_entries = [
            {"ts": "2026-11-19T01:00:00Z", "state": "running", "cycle_seconds": 60},
            {"ts": "2026-11-19T02:00:00Z", "state": "running", "cycle_seconds": 60},
            {"ts": "2026-11-19T03:00:00Z", "state": "running", "cycle_seconds": 60},
            # Hari 2026-11-20: siklus memanjang lalu budget coder & front habis ±03:40 dan idle 180 menit.
            {"ts": "2026-11-20T01:00:00Z", "state": "running", "cycle_seconds": 60},
            {"ts": "2026-11-20T02:00:00Z", "state": "running", "cycle_seconds": 180},
            {"ts": "2026-11-20T03:30:00Z", "state": "running", "cycle_seconds": 600},
            {
                "ts": "2026-11-20T03:40:00Z",
                "event": "budget_exhausted",
                "role": "coder",
                "state": "idle",
            },
            {
                "ts": "2026-11-20T04:15:00Z",
                "event": "budget_exhausted",
                "role": "front",
                "state": "idle",
            },
            {"ts": "2026-11-20T06:40:00Z", "state": "stopped"},
        ]

        snapshots = [
            {
                "ts": "2026-11-19T03:05:00Z",
                "status": "running",
                "budgets": {
                    "coder": {"used": 20, "limit": 100, "remaining": 80},
                    "front": {"used": 10, "limit": 100, "remaining": 90},
                },
            },
            {
                "ts": "2026-11-20T03:42:00Z",
                "status": "idle",
                "budgets": {
                    "coder": {"used": 100, "limit": 100, "remaining": 0},
                    "front": {"used": 95, "limit": 100, "remaining": 5},
                },
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_path = root / "engine.jsonl"
            snap_path = root / "snapshots.json"
            out_path = root / "idle.json"
            log_path.write_text(
                "\n".join(json.dumps(r) for r in log_entries) + "\n", encoding="utf-8"
            )
            snap_path.write_text(json.dumps(snapshots), encoding="utf-8")

            rc = engine_idle_report.main(
                ["--log", str(log_path), "--snapshots", str(snap_path), "--out", str(out_path)]
            )
            self.assertEqual(rc, 0)
            rep = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertEqual(rep["schema"], engine_idle_report.SCHEMA)
        self.assertEqual(rep["summary"]["healthy_days"], ["2026-11-19"])
        self.assertEqual(rep["summary"]["exhausted_days"], ["2026-11-20"])
        self.assertEqual(
            rep["summary"]["first_exhaustion_per_role"],
            {
                "coder": "2026-11-20T03:40:00Z",
                "front": "2026-11-20T04:15:00Z",
            },
        )

        healthy_day = rep["by_day"]["2026-11-19"]
        self.assertTrue(healthy_day["healthy"])
        self.assertEqual(healthy_day["idle_minutes"], 0.0)
        self.assertFalse(healthy_day["cycles_lengthening"])
        self.assertEqual(healthy_day["budget_exhaustions"], {})

        bad_day = rep["by_day"]["2026-11-20"]
        self.assertFalse(bad_day["healthy"])
        self.assertAlmostEqual(bad_day["idle_minutes"], 180.0, places=3)
        self.assertTrue(bad_day["cycles_lengthening"])
        self.assertEqual(bad_day["first_cycle_seconds"], 60.0)
        self.assertEqual(bad_day["last_cycle_seconds"], 600.0)


if __name__ == "__main__":
    unittest.main()
