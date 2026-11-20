"""Tes tiga keadaan model dunia rumah + aturan kebaruan telemetri (AG76)."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
import unittest

from ace_operational.house_model import SCHEMA, build_house_world_model


class HouseWorldModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
        self.fresh_telemetry = {
            "budgets": {
                "updated_at": "2026-11-20T11:58:00Z",
                "roles": {
                    "front": {"remaining": 150, "limit": 200},
                    "coder": {"remaining": 120, "limit": 200},
                },
            },
            "bridge_health": {"updated_at": "2026-11-20T11:59:30Z", "ok": True},
            "engine_status": {"updated_at": "2026-11-20T11:59:00Z", "running": True},
            "queue": {"updated_at": "2026-11-20T11:59:10Z", "depth": 3, "critical_pending": 1},
        }

    def test_three_house_states_healthy_stale_and_sick(self) -> None:
        # 1. Sehat & segar penuh.
        healthy = build_house_world_model(self.fresh_telemetry, now=self.now, max_age_seconds=300)
        self.assertEqual(healthy["schema"], SCHEMA)
        self.assertEqual(healthy["house_state"], "healthy")
        self.assertTrue(healthy["all_fresh"])
        self.assertFalse(healthy["is_sick"])
        self.assertEqual(healthy["stale_subsystems"], [])
        self.assertEqual(healthy["queue"]["depth"], 3)

        # 2. Data basi (bridge_health > 300s, engine tanpa updated_at) WAJIB ditandai basi meski ok/running True.
        stale_tel = {
            **self.fresh_telemetry,
            "bridge_health": {"updated_at": "2026-11-20T11:50:00Z", "ok": True},
            "engine_status": {"running": True},
        }
        stale = build_house_world_model(stale_tel, now=self.now, max_age_seconds=300)
        self.assertEqual(stale["house_state"], "stale")
        self.assertFalse(stale["all_fresh"])
        self.assertTrue(stale["is_sick"])
        self.assertTrue(stale["bridge_health"]["stale"])
        self.assertTrue(stale["engine_status"]["stale"])
        self.assertEqual(stale["stale_subsystems"], ["bridge_health", "engine_status"])

        # 3. Rumah sakit (bridge mati + kuota coder habis).
        sick_tel = {
            **self.fresh_telemetry,
            "bridge_health": {"updated_at": "2026-11-20T11:59:30Z", "ok": False},
            "budgets": {
                "updated_at": "2026-11-20T11:59:30Z",
                "roles": {
                    "front": {"remaining": 20, "limit": 200},
                    "coder": {"remaining": 0, "limit": 200},
                },
            },
        }
        sick = build_house_world_model(sick_tel, now=self.now, max_age_seconds=300)
        self.assertEqual(sick["house_state"], "sick")
        self.assertTrue(sick["is_sick"])
        self.assertEqual(sick["exhausted_roles"], ["coder"])

    def test_no_engine_imports(self) -> None:
        src = (Path(__file__).resolve().parent / "house_model.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                self.assertNotIn("autonomous_engine", node.module)


if __name__ == "__main__":
    unittest.main()
