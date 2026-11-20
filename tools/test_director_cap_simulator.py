"""Tes regresi fixture-only untuk tools.director_cap_simulator (AG45)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools import director_cap_simulator


def _make_day_receipts(day: str, completed: int, failed: int) -> list[dict]:
    rows: list[dict] = []
    idx = 0
    for _ in range(completed):
        idx += 1
        tid = f"{day}-t{idx}"
        rows.append({"status": "started", "task_id": tid, "at": f"{day}T01:0{idx}:00Z"})
        rows.append({"status": "completed", "task_id": tid, "at": f"{day}T01:1{idx}:00Z"})
    for _ in range(failed):
        idx += 1
        tid = f"{day}-t{idx}"
        rows.append({"status": "started", "task_id": tid, "at": f"{day}T02:0{idx}:00Z"})
        rows.append({"status": "failed", "task_id": tid, "at": f"{day}T02:1{idx}:00Z"})
    return rows


class DirectorCapSimulatorTest(unittest.TestCase):
    def test_seven_day_pattern_aimd_transitions(self) -> None:
        # Pola 7 hari:
        # - Hari 1 (2026-11-10): 2 ok, 0 fail (100%) -> cap 2 -> 3 (promote)
        # - Hari 2 (2026-11-11): 3 ok, 0 fail (100%) -> cap 3 -> 4 (promote)
        # - Hari 3 (2026-11-12): 3 ok, 1 fail (75%)  -> cap 4 -> 4 (hold band)
        # - Hari 4 (2026-11-13): 1 ok, 3 fail (25%)  -> cap 4 -> 2 (shrink)
        # - Hari 5 (2026-11-14): 0 ok, 2 fail (0%)   -> cap 2 -> 1 (shrink)
        # - Hari 6 (2026-11-15): 1 ok, 0 fail (100%) -> cap 1 -> 2 (recover/promote)
        # - Hari 7 (2026-11-16): 2 ok, 0 fail (100%) -> cap 2 -> 3 (promote)
        pattern = [
            ("2026-11-10", 2, 0),
            ("2026-11-11", 3, 0),
            ("2026-11-12", 3, 1),
            ("2026-11-13", 1, 3),
            ("2026-11-14", 0, 2),
            ("2026-11-15", 1, 0),
            ("2026-11-16", 2, 0),
        ]
        lines: list[str] = []
        for day, ok, fail in pattern:
            for item in _make_day_receipts(day, ok, fail):
                lines.append(json.dumps(item))
        # Tambahkan baris robek di ekor untuk memastikan simulator tahan tanpa crash.
        lines.append('{"status": "started", "task_id": "torn')

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rec_path = root / "receipts.jsonl"
            out_path = root / "sim.json"
            rec_path.write_text("\n".join(lines), encoding="utf-8")

            rc = director_cap_simulator.main(
                ["--receipts", str(rec_path), "--out", str(out_path)]
            )
            self.assertEqual(rc, 0)
            rep = json.loads(out_path.read_text(encoding="utf-8"))

        self.assertEqual(rep["schema"], director_cap_simulator.SCHEMA)
        self.assertEqual(len(rep["malformed_lines"]), 1)
        summary = rep["summary"]
        self.assertEqual(summary["days_replayed"], 7)
        self.assertEqual(summary["final_cap"], 3)
        self.assertEqual(summary["min_cap_observed"], 1)
        self.assertEqual(summary["max_cap_observed"], 4)
        self.assertEqual(summary["promotions"], 4)
        self.assertEqual(summary["shrinks"], 2)
        self.assertEqual(summary["holds"], 1)

        trace = rep["daily_trace"]
        self.assertEqual(
            [(row["day"], row["cap_start"], row["cap_next"], row["rule_applied"]) for row in trace],
            [
                ("2026-11-10", 2, 3, "high_success_rate_promote"),
                ("2026-11-11", 3, 4, "high_success_rate_promote"),
                ("2026-11-12", 4, 4, "hold_band"),
                ("2026-11-13", 4, 2, "low_success_rate_shrink"),
                ("2026-11-14", 2, 1, "low_success_rate_shrink"),
                ("2026-11-15", 1, 2, "high_success_rate_promote"),
                ("2026-11-16", 2, 3, "high_success_rate_promote"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
