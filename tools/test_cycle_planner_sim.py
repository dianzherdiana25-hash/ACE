"""Tes matriks keadaan kebijakan perencana siklus (AG77)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import cycle_planner_sim


class CyclePlannerSimTest(unittest.TestCase):
    def test_state_matrix_heavy_before_exhaustion_and_critical_first_when_sick(self) -> None:
        steps = [
            {"step_id": "s-light-noncrit", "role": "coder", "critical": False, "cost": 1, "weight": 1},
            {"step_id": "s-heavy-noncrit", "role": "coder", "critical": False, "cost": 4, "weight": 8},
            {"step_id": "s-crit-small", "role": "coder", "critical": True, "cost": 1, "weight": 5},
        ]

        # 1. Rumah sehat dengan kuota coder=5 -> kritis jalan, lalu langkah BERAT (cost=4) didahulukan
        # sebelum langkah ringan menghabiskan sisa kuota; total 1+4=5 habis tepat, langkah ringan tunda.
        healthy_world = {
            "schema": "ace.house-world-model.v1",
            "house_state": "healthy",
            "is_sick": False,
            "bridge_health": {"ok": True},
            "budgets": {"roles": {"coder": {"remaining": 5, "limit": 10}}},
        }
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            w_path = root / "world.json"
            s_path = root / "steps.json"
            o_path = root / "plan.json"
            w_path.write_text(json.dumps(healthy_world), encoding="utf-8")
            s_path.write_text(json.dumps(steps), encoding="utf-8")
            self.assertEqual(
                cycle_planner_sim.main(
                    ["--world-model", str(w_path), "--steps", str(s_path), "--out", str(o_path)]
                ),
                0,
            )
            rep_healthy = json.loads(o_path.read_text(encoding="utf-8"))

        self.assertEqual(rep_healthy["summary"]["scheduled_order"], ["s-crit-small", "s-heavy-noncrit"])
        self.assertEqual(rep_healthy["summary"]["deferred_steps"], ["s-light-noncrit"])
        by_id = {d["step_id"]: d for d in rep_healthy["decisions"]}
        self.assertIn("heavy_step_scheduled_before_quota_fragmented", by_id["s-heavy-noncrit"]["reasons"])
        self.assertIn("insufficient_role_budget", by_id["s-light-noncrit"]["reasons"][0])

        # 2. Rumah sakit (masih ada sisa kuota & bridge hidup) -> kritis dulu, semua non-kritis ditunda!
        sick_world = {
            "schema": "ace.house-world-model.v1",
            "house_state": "sick",
            "is_sick": True,
            "bridge_health": {"ok": True},
            "budgets": {"roles": {"coder": {"remaining": 10, "limit": 10}}},
        }
        rep_sick = cycle_planner_sim.plan_cycle_steps(sick_world, steps)
        self.assertEqual(rep_sick["summary"]["scheduled_order"], ["s-crit-small"])
        self.assertEqual(sorted(rep_sick["summary"]["deferred_steps"]), ["s-heavy-noncrit", "s-light-noncrit"])
        sick_by_id = {d["step_id"]: d for d in rep_sick["decisions"]}
        self.assertEqual(sick_by_id["s-crit-small"]["reasons"], ["critical_first_while_house_sick"])
        self.assertEqual(sick_by_id["s-heavy-noncrit"]["reasons"], ["deferred_non_critical_while_house_sick"])

        # 3. Rumah stale -> perilaku bertahan: non-kritis ditunda, kritis tetap aman jalan.
        stale_world = {
            "schema": "ace.house-world-model.v1",
            "house_state": "stale",
            "is_sick": True,
            "bridge_health": {"ok": True},
            "budgets": {"roles": {"coder": {"remaining": 3, "limit": 10}}},
        }
        rep_stale = cycle_planner_sim.plan_cycle_steps(stale_world, steps)
        self.assertEqual(rep_stale["summary"]["scheduled_order"], ["s-crit-small"])
        self.assertEqual(rep_stale["summary"]["defer_count"], 2)


if __name__ == "__main__":
    unittest.main()
