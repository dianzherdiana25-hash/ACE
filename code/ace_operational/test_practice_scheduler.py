"""Tes kebijakan penjadwalan praktik berjarak & eskalasi kesulitan (AG64)."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
import unittest

from ace_operational.practice_scheduler import schedule_gap_practice


class _FixtureGapStore:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def list_gap_histories(self):
        return list(self._rows)


class PracticeSchedulerTests(unittest.TestCase):
    def test_recently_failed_scheduled_before_stabilizing_and_stable_escalates(self) -> None:
        now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
        store = _FixtureGapStore(
            [
                {
                    "gap_id": "gap-stable-passes",
                    "family": "bfs",
                    "difficulty": 2,
                    "last_practiced_at": "2026-11-20T11:30:00Z",
                    "recent_outcomes": ["fail", "pass", "pass", "pass"],
                },
                {
                    "gap_id": "gap-consolidating",
                    "family": "json_parser",
                    "difficulty": 2,
                    "last_practiced_at": "2026-11-20T11:30:00Z",
                    "recent_outcomes": ["fail", "pass"],
                },
                {
                    "gap_id": "gap-recent-fail",
                    "family": "progressive_tax",
                    "difficulty": 3,
                    "last_practiced_at": "2026-11-20T11:50:00Z",
                    "recent_outcomes": ["pass", "fail", "fail"],
                },
            ]
        )

        plan = schedule_gap_practice(store, now=now)
        self.assertEqual(
            [row["gap_id"] for row in plan],
            ["gap-recent-fail", "gap-consolidating", "gap-stable-passes"],
        )

        by_id = {row["gap_id"]: row for row in plan}
        # Gap yang baru gagal dijadwalkan jauh lebih awal daripada gap stabil.
        self.assertLess(by_id["gap-recent-fail"]["scheduled_at"], by_id["gap-stable-passes"]["scheduled_at"])
        self.assertLess(by_id["gap-recent-fail"]["interval_hours"], by_id["gap-stable-passes"]["interval_hours"])
        self.assertEqual(by_id["gap-recent-fail"]["difficulty_action"], "step_down_remediation")
        self.assertEqual(by_id["gap-recent-fail"]["recommended_difficulty"], 2)

        # Gap stabil mengalami eskalasi kesulitan (2 -> 3) dengan interval lebih lebar.
        self.assertEqual(by_id["gap-stable-passes"]["difficulty_action"], "escalate")
        self.assertEqual(by_id["gap-stable-passes"]["recommended_difficulty"], 3)
        self.assertGreater(by_id["gap-stable-passes"]["interval_hours"], by_id["gap-consolidating"]["interval_hours"])
        for row in plan:
            self.assertTrue(row["reasons"])

    def test_no_engine_imports(self) -> None:
        src = (Path(__file__).resolve().parent / "practice_scheduler.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn("autonomous_engine", node.module)


if __name__ == "__main__":
    unittest.main()
