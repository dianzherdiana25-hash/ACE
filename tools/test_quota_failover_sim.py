"""Tes matriks keputusan lengkap untuk tools.quota_failover_sim (AG49)."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools import quota_failover_sim


class QuotaFailoverSimTest(unittest.TestCase):
    def test_full_decision_matrix_fixture(self) -> None:
        # Matriks penuh:
        # - judge: remaining=1, tanpa fallback -> step kritis pertama primary (sisa 0), kritis kedua wait.
        # - coder: remaining=1, fallback="front" -> non-kritis 1 pakai primary (sisa 0, BUKAN fallback dini),
        #   step kritis dengan primary habis TETAP wait meski fallback "front" masih punya kuota,
        #   lalu non-kritis 2 setelah primary habis pindah ke fallback ("front", sisa 2 -> 1),
        #   lalu non-kritis 3 dengan cost=2 saat fallback sisa=1 -> wait.
        budgets = {
            "judge": {"remaining": 1, "fallback_role": "front"},
            "coder": {"remaining": 1, "fallback_role": "front"},
            "front": {"remaining": 2},
            "validator": {"remaining": 0},  # tak ada fallback
        }
        steps = [
            {"step_id": "m1-crit-primary-ok", "role": "judge", "critical": True, "cost": 1},
            {
                "step_id": "m2-crit-primary-empty-never-fallback",
                "role": "judge",
                "critical": True,
                "cost": 1,
                "fallback_role": "front",
            },
            {"step_id": "m3-noncrit-primary-ok", "role": "coder", "critical": False, "cost": 1},
            {
                "step_id": "m4-crit-coder-still-empty-wait",
                "role": "coder",
                "critical": True,
                "cost": 1,
            },
            {
                "step_id": "m5-noncrit-primary-exhausted-fallback",
                "role": "coder",
                "critical": False,
                "cost": 1,
            },
            {
                "step_id": "m6-noncrit-fallback-insufficient-wait",
                "role": "coder",
                "critical": False,
                "cost": 2,
            },
            {
                "step_id": "m7-noncrit-no-fallback-wait",
                "role": "validator",
                "critical": False,
                "cost": 1,
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b_path = root / "budgets.json"
            s_path = root / "steps.jsonl"
            o_path = root / "out.json"
            b_path.write_text(json.dumps(budgets), encoding="utf-8")
            s_path.write_text(
                "\n".join(json.dumps(s) for s in steps) + "\n", encoding="utf-8"
            )

            rc = quota_failover_sim.main(
                ["--budgets", str(b_path), "--steps", str(s_path), "--out", str(o_path)]
            )
            self.assertEqual(rc, 0)
            rep = json.loads(o_path.read_text(encoding="utf-8"))

        self.assertEqual(rep["schema"], quota_failover_sim.SCHEMA)
        self.assertEqual(rep["summary"]["total_steps"], 7)
        self.assertEqual(rep["summary"]["critical_fallback_count"], 0)
        self.assertEqual(rep["summary"]["primary_count"], 2)
        self.assertEqual(rep["summary"]["fallback_count"], 1)
        self.assertEqual(rep["summary"]["wait_count"], 4)

        decisions = {row["step_id"]: row for row in rep["decisions"]}
        self.assertEqual(decisions["m1-crit-primary-ok"]["decision"], "primary")
        self.assertEqual(decisions["m1-crit-primary-ok"]["chosen_role"], "judge")

        # Langkah kritis dengan fallback tersedia pun TIDAK boleh jatuh ke fallback.
        self.assertEqual(decisions["m2-crit-primary-empty-never-fallback"]["decision"], "wait")
        self.assertEqual(
            decisions["m2-crit-primary-empty-never-fallback"]["reason"],
            "critical_primary_exhausted_no_fallback",
        )
        # Non-kritis dengan primary tersedia tidak boleh jatuh ke fallback dini.
        self.assertEqual(decisions["m3-noncrit-primary-ok"]["decision"], "primary")
        self.assertEqual(decisions["m4-crit-coder-still-empty-wait"]["decision"], "wait")
        # Baru setelah primary habis, non-kritis memakai fallback "front".
        self.assertEqual(decisions["m5-noncrit-primary-exhausted-fallback"]["decision"], "fallback")
        self.assertEqual(decisions["m5-noncrit-primary-exhausted-fallback"]["chosen_role"], "front")
        self.assertEqual(decisions["m6-noncrit-fallback-insufficient-wait"]["decision"], "wait")
        self.assertEqual(decisions["m7-noncrit-no-fallback-wait"]["decision"], "wait")

        self.assertEqual(rep["final_budgets"]["judge"]["remaining"], 0)
        self.assertEqual(rep["final_budgets"]["coder"]["remaining"], 0)
        self.assertEqual(rep["final_budgets"]["front"]["remaining"], 1)


if __name__ == "__main__":
    unittest.main()
