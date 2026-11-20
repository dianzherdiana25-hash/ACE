"""Tes tiga invarian eksekusi: bersih, tanpa receipt, cap terlampaui, palsu, kelas A tak bertambat (AG85)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import execution_invariants


class ExecutionInvariantsTest(unittest.TestCase):
    def test_clean_trace_passes_and_four_violation_traces_caught(self) -> None:
        clean_receipts = [
            {"task_id": "t1", "status": "started", "at": "2026-11-20T01:00:00Z"},
            {"task_id": "t1", "status": "completed", "at": "2026-11-20T01:01:00Z"},
            {"task_id": "t2", "status": "started", "at": "2026-11-20T02:00:00Z"},
            {"task_id": "t2", "status": "completed", "at": "2026-11-20T02:01:00Z"},
        ]
        clean_execs = [
            {
                "task_id": "t1",
                "at": "2026-11-20T01:01:00Z",
                "class": "A",
                "evidence_refs": ["ev-001"],
                "anchor_verified": True,
            },
            {
                "task_id": "t2",
                "at": "2026-11-20T02:01:00Z",
                "class": "B",
                "anchor_verified": False,
            },
        ]

        # 1. Jejak bersih via CLI -> exit code 0, semua 3 invarian holds=True.
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            rec_f = root / "receipts.jsonl"
            exe_f = root / "execs.json"
            out_f = root / "inv.json"
            rec_f.write_text("\n".join(json.dumps(r) for r in clean_receipts) + "\n", encoding="utf-8")
            exe_f.write_text(json.dumps(clean_execs), encoding="utf-8")

            rc_ok = execution_invariants.main(
                ["--receipts", str(rec_f), "--executions", str(exe_f), "--daily-cap", "2", "--out", str(out_f)]
            )
            self.assertEqual(rc_ok, 0)
            rep_ok = json.loads(out_f.read_text(encoding="utf-8"))

        self.assertEqual(rep_ok["schema"], execution_invariants.SCHEMA)
        self.assertTrue(rep_ok["all_invariants_hold"])
        self.assertEqual(len(rep_ok["invariant_specs"]), 3)
        self.assertEqual(rep_ok["violations"], [])

        # 2. Jejak tanpa receipt (eksekusi di log tak punya receipt).
        rep_no_rec = execution_invariants.check_execution_invariants(
            clean_receipts[:2],
            clean_execs,
            daily_cap=5,
        )
        self.assertFalse(rep_no_rec["all_invariants_hold"])
        self.assertEqual(
            [v["code"] for v in rep_no_rec["violations"]],
            ["execution_without_receipt"],
        )

        # 3. Jejak cap harian terlampaui (3 eksekusi pada hari yang sama vs daily_cap=2).
        r_cap = clean_receipts + [
            {"task_id": "t3", "status": "started", "at": "2026-11-20T03:00:00Z"},
            {"task_id": "t3", "status": "completed", "at": "2026-11-20T03:01:00Z"},
        ]
        e_cap = clean_execs + [
            {"task_id": "t3", "at": "2026-11-20T03:01:00Z", "class": "A", "anchor_verified": True}
        ]
        rep_cap = execution_invariants.check_execution_invariants(r_cap, e_cap, daily_cap=2)
        self.assertFalse(rep_cap["all_invariants_hold"])
        self.assertIn("inv_daily_cap_not_exceeded", rep_cap["summary"]["violated_invariants"])

        # 4. Jejak palsu (completed tanpa started) + Kelas A tanpa jangkar terverifikasi.
        fake_receipts = [{"task_id": "t-fake", "status": "completed", "at": "2026-11-20T04:00:00Z"}]
        fake_execs = [
            {
                "task_id": "t-fake",
                "at": "2026-11-20T04:00:00Z",
                "class": "A",
                "evidence_refs": ["ev-missing"],
            }
        ]
        rep_fake = execution_invariants.check_execution_invariants(
            fake_receipts, fake_execs, daily_cap=5, verified_refs=["ev-001"]
        )
        self.assertFalse(rep_fake["all_invariants_hold"])
        codes = {v["code"] for v in rep_fake["violations"]}
        self.assertIn("terminal_without_started", codes)
        self.assertIn("class_a_without_verified_anchor", codes)


if __name__ == "__main__":
    unittest.main()
