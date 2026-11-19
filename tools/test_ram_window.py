#!/usr/bin/env python3
"""Tes unit untuk `tools/ram_window.py` (Gelombang C3).

Memverifikasi perhitungan kombinasi beban yang muat di bawah margin RAM,
urutan eksekusi dengan jawaban analitik yang diketahui, deteksi beban
oversized, serta stabilitas aritmetika `Decimal`.
"""
from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.ram_window import (
    RAM_WINDOW_SCHEMA,
    RamWindowError,
    parse_workloads,
    plan_ram_windows,
    render_markdown,
)


class RamWindowTests(unittest.TestCase):
    def test_known_answer_combinations_and_schedule_never_exceeds_margin(self) -> None:
        # Total RAM = 16 GiB, Margin = 4 GiB -> plafon aman = 12 GiB.
        # Beban:
        #   model_a: 7.5 GiB, durasi 30
        #   embed_b: 4.5 GiB, durasi 10  (7.5 + 4.5 = 12.0 tepat di plafon!)
        #   audit_c: 6.0 GiB, durasi 20  (tidak muat bersama model_a: 13.5 > 12; muat bersama embed_b: 10.5 <= 12)
        #   lint_d:  2.0 GiB, durasi 15  (muat bersama audit_c+embed_b? 6+4.5+2=12.5 > 12; muat bersama audit_c: 8 <= 12)
        workloads = parse_workloads(
            [
                {"name": "model_a", "gib": "7.5", "duration": 30},
                {"name": "embed_b", "gib": "4.5", "duration": 10},
                {"name": "audit_c", "gib": "6.0", "duration": 20},
                {"name": "lint_d", "gib": "2.0", "duration": 15},
            ]
        )
        plan = plan_ram_windows(workloads, total_ram_gib=16, margin_gib=4)

        self.assertEqual(plan["schema"], RAM_WINDOW_SCHEMA)
        self.assertEqual(plan["safe_ceiling_gib"], "12")
        self.assertTrue(plan["all_fit"])
        self.assertTrue(plan["invariant_never_exceeds_margin"])
        self.assertEqual(plan["oversized_count"], 0)

        # Kombinasi maksimal yang diketahui persis:
        # {embed_b, model_a} = 12, {audit_c, embed_b} = 10.5, {lint_d, model_a} = 9.5,
        # {audit_c, lint_d} = 8, {embed_b, lint_d} = 6.5 (tambah 6.0 atau 7.5 > 12)
        maximal_sets = {frozenset(c["workloads"]) for c in plan["maximal_safe_combinations"]}
        self.assertEqual(
            maximal_sets,
            {
                frozenset({"model_a", "embed_b"}),
                frozenset({"audit_c", "embed_b"}),
                frozenset({"model_a", "lint_d"}),
                frozenset({"audit_c", "lint_d"}),
                frozenset({"embed_b", "lint_d"}),
            },
        )

        # Jadwal FFD by RAM:
        # 1) model_a (7.5, 30): [0, 30)
        # 2) audit_c (6.0, 20): tidak muat di 0 (7.5+6=13.5>12), mulai di 30: [30, 50)
        # 3) embed_b (4.5, 10): muat di 0 bersama model_a (7.5+4.5=12<=12): [0, 10)
        # 4) lint_d  (2.0, 15): tidak muat di 0 (12+2=14>12), mulai di 10 bersama model_a (7.5+2=9.5<=12): [10, 25)
        sched_by_name = {row["name"]: (row["start"], row["end"]) for row in plan["schedule"]}
        self.assertEqual(
            sched_by_name,
            {
                "model_a": ("0", "30"),
                "embed_b": ("0", "10"),
                "lint_d": ("10", "25"),
                "audit_c": ("30", "50"),
            },
        )
        self.assertEqual(plan["makespan"], "50")
        self.assertEqual(plan["peak_ram_gib"], "12")
        self.assertEqual(plan["min_headroom_gib"], "0")

        # Pastikan tidak ada satu pun jendela melampaui plafon aman 12 GiB.
        for win in plan["windows"]:
            self.assertLessEqual(Decimal(win["used_gib"]), Decimal("12"))
            self.assertGreaterEqual(Decimal(win["headroom_gib"]), Decimal("0"))

    def test_oversized_workload_is_flagged_and_cli_exits_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            wf = tmp_dir / "workloads.json"
            wf.write_text(
                json.dumps(
                    {
                        "workloads": [
                            {"name": "tiny", "gib": "3.2", "duration": 5},
                            {"name": "giant_70b", "gib": "42.5", "duration": 60},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            md_out = tmp_dir / "plan.md"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.ram_window",
                    str(wf),
                    "--total-ram-gib",
                    "16",
                    "--margin-gib",
                    "2",
                    "--markdown-out",
                    str(md_out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertFalse(payload["all_fit"])
            self.assertEqual(payload["oversized_count"], 1)
            self.assertEqual(payload["oversized_workloads"][0]["name"], "giant_70b")
            self.assertEqual(payload["oversized_workloads"][0]["excess_gib"], "28.5")
            self.assertEqual(render_markdown(payload), md_out.read_text(encoding="utf-8"))

    def test_rejects_invalid_inputs(self) -> None:
        with self.assertRaises(RamWindowError):
            parse_workloads([])
        with self.assertRaises(RamWindowError):
            parse_workloads([{"name": "a", "gib": -1, "duration": 10}])
        with self.assertRaises(RamWindowError):
            parse_workloads([{"name": "dup", "gib": 1, "duration": 1}, {"name": "dup", "gib": 2, "duration": 2}])
        wl = parse_workloads([{"name": "ok", "gib": 2, "duration": 5}])
        with self.assertRaises(RamWindowError):
            plan_ram_windows(wl, total_ram_gib=8, margin_gib=8)


if __name__ == "__main__":
    unittest.main()
