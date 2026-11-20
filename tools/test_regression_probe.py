"""Tes pelari probe regresi: deret stabil vs deret menurun menerbitkan insiden (AG78)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import regression_probe


REPO_ROOT = Path(__file__).resolve().parents[1]
HELDOUT_PACK = REPO_ROOT / "tools" / "fixtures" / "heldout_regression_tasks_v1.jsonl"


class RegressionProbeTest(unittest.TestCase):
    def test_stable_series_produces_no_incident_and_drop_creates_incident_file(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            stable_series = root / "stable_series.json"
            stable_incident = root / "stable_incident.json"

            # 1. Deret stabil atas paket AG29 (8 tugas: 1.0 -> 0.875, turun 0.125 <= ambang 0.15).
            res1 = regression_probe.run_probe_and_append_series(
                HELDOUT_PACK,
                stable_series,
                lambda t: t["expected_zero_record_flagged"],
                incident_path=stable_incident,
                drop_threshold=0.15,
                run_id="r1",
            )
            res2 = regression_probe.run_probe_and_append_series(
                HELDOUT_PACK,
                stable_series,
                lambda t: (False if t["id"] == "ho-01" else t["expected_zero_record_flagged"]),
                incident_path=stable_incident,
                drop_threshold=0.15,
                run_id="r2",
            )
            self.assertEqual(res1["score"], 1.0)
            self.assertAlmostEqual(res2["score"], 0.875, places=6)
            self.assertFalse(res2["regression_detected"])
            self.assertIsNone(res2["incident_file"])
            self.assertFalse(stable_incident.exists())

            # 2. Deret menurun melampaui ambang: 1.0 -> 0.50 (drop 0.50 > 0.15) -> terbitkan berkas insiden!
            degrading_series = root / "degrading_series.json"
            drop_incident = root / "drop_incident.json"
            regression_probe.run_probe_and_append_series(
                HELDOUT_PACK,
                degrading_series,
                lambda t: t["expected_zero_record_flagged"],
                incident_path=drop_incident,
                drop_threshold=0.15,
                run_id="base",
            )
            bad_res = regression_probe.run_probe_and_append_series(
                HELDOUT_PACK,
                degrading_series,
                lambda t: (False if t["domain"] == "code" else t["expected_zero_record_flagged"]),
                incident_path=drop_incident,
                drop_threshold=0.15,
                run_id="regressed",
            )
            self.assertTrue(bad_res["regression_detected"])
            self.assertEqual(bad_res["incident_file"], str(drop_incident))
            self.assertTrue(drop_incident.is_file())

            inc = json.loads(drop_incident.read_text(encoding="utf-8"))
            series_data = json.loads(degrading_series.read_text(encoding="utf-8"))

        self.assertEqual(inc["schema"], regression_probe.INCIDENT_SCHEMA)
        self.assertEqual(inc["baseline_score"], 1.0)
        self.assertLess(inc["current_score"], 0.85)
        self.assertGreater(inc["drop"], 0.15)
        self.assertIn("ho-01", inc["failing_task_ids"])
        self.assertEqual(len(series_data["runs"]), 2)

    def test_cli_runs_cleanly_over_ag29_pack(self) -> None:
        with TemporaryDirectory() as tmp:
            series = Path(tmp) / "cli_series.json"
            inc = Path(tmp) / "cli_incident.json"
            rc = regression_probe.main(
                [
                    "--pack",
                    str(HELDOUT_PACK),
                    "--series",
                    str(series),
                    "--incident-out",
                    str(inc),
                ]
            )
            self.assertEqual(rc, 0)
            self.assertTrue(series.is_file())
            self.assertFalse(inc.exists())


if __name__ == "__main__":
    unittest.main()
