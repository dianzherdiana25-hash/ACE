#!/usr/bin/env python3
"""Unit tests untuk tools/kbm_schedule.py (WS-C #10)."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.kbm_schedule import KbmScheduleError, SCHEDULE_SCHEMA, build_schedule, main


class TestKbmSchedule(unittest.TestCase):
    def test_schedule_status_completed_overdue_and_upcoming(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            catalog = tmp / "catalog.json"
            catalog.write_text(
                json.dumps(
                    {
                        "serials": [
                            {
                                "id": "seri_mercusuar",
                                "title": "Penjaga Mercusuar",
                                "total_chapters": 5,
                                "completed_chapters": 1,
                                "weekly_target": 2,
                                "start_date": "2026-11-01",
                            },
                            {
                                "id": "seri_pelabuhan",
                                "title": "Kabut Pelabuhan",
                                "total_chapters": 4,
                                "completed_chapters_list": [1, 3],
                                "weekly_target": 3,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            out_path = tmp / "schedule.json"
            rc = main(
                [
                    str(catalog),
                    "--start-date",
                    "2026-11-10",
                    "--as-of",
                    "2026-11-12",
                    "--out",
                    str(out_path),
                ]
            )
            self.assertEqual(rc, 0)
            rep = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(rep["schema"], SCHEDULE_SCHEMA)
            self.assertEqual(rep["summary"]["total_serials"], 2)
            self.assertEqual(rep["summary"]["total_chapters"], 9)
            self.assertEqual(rep["summary"]["completed"], 3)

            by_id = {s["id"]: s for s in rep["serials"]}
            # seri_mercusuar (weekly=2 -> days 0, 3, 7, 10, 14 from Nov 1: Nov 1, Nov 4, Nov 8, Nov 11, Nov 15)
            # Bab 1 completed, bab 2..4 (< Nov 12) overdue, bab 5 (Nov 15 >= Nov 12) scheduled.
            m_slots = by_id["seri_mercusuar"]["slots"]
            self.assertEqual([s["status"] for s in m_slots], ["completed", "overdue", "overdue", "overdue", "scheduled"])
            self.assertEqual(m_slots[-1]["scheduled_date"], "2026-11-15")

            # seri_pelabuhan (start Nov 10, weekly=3 -> days 0, 2, 4, 7: Nov 10, Nov 12, Nov 14, Nov 17)
            # completed_chapters_list=[1, 3] => bab 1 completed, bab 2 scheduled (Nov 12 >= Nov 12), bab 3 completed, bab 4 scheduled.
            p_slots = by_id["seri_pelabuhan"]["slots"]
            self.assertEqual([s["status"] for s in p_slots], ["completed", "scheduled", "completed", "scheduled"])
            self.assertGreaterEqual(len(rep["summary"]["next_upcoming"]), 3)
            self.assertEqual(rep["summary"]["next_upcoming"][0]["scheduled_date"], "2026-11-12")

    def test_validation_errors_and_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            dup_cat = tmp / "dup.json"
            dup_cat.write_text(
                json.dumps(
                    [
                        {"id": "a", "total_chapters": 2},
                        {"id": "a", "total_chapters": 3},
                    ]
                ),
                encoding="utf-8",
            )
            with self.assertRaises(KbmScheduleError):
                build_schedule(dup_cat)

            bad_ch = tmp / "bad_ch.json"
            bad_ch.write_text(
                json.dumps({"serials": [{"id": "s1", "total_chapters": 2, "completed_chapters": 5}]}),
                encoding="utf-8",
            )
            self.assertEqual(main([str(bad_ch), "--as-of", "bad-date"]), 2)
            self.assertEqual(main([str(tmp / "missing.json")]), 2)


if __name__ == "__main__":
    unittest.main()
