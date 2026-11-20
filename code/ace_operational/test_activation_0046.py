"""Tes integrasi paket EVO 0046 (AG151–AG159: Organ Jembatan & Replikasi).

Berjalan aman di baseline (`main`) dengan menguji `step_organs` dasar (di-mock smoke),
dan membuka suite penuh end-to-end 9 langkah EVO 0046 di bawah `@unittest.skipUnless(_ALL_WIRED, ...)`
saat seluruh branch AG151–AG159 digabungkan.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ace_operational import leap_wiring
from ace_operational.autonomous_engine import ContinuousAutonomousEngine
from ace_operational.brain_registry import BrainRegistry
from ace_operational.store import OperationalStore

_EVO0046_STEPS = (
    "step_brain_registry",
    "step_organ_quality_board",
    "step_organ_forensics",
    "step_cross_organ_agreement",
    "step_engine_idle_report",
    "step_quota_failover_sim",
    "step_ram_window",
    "step_failover_drill",
    "step_home_replication",
)
_ALL_WIRED = all(hasattr(leap_wiring, name) for name in _EVO0046_STEPS)


class Activation0046BaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ace-evo0046-base-")
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name) / "workspace"
        self.store = OperationalStore(self.ws)
        self.addCleanup(self.store.close)

    def test_baseline_step_organs_works(self) -> None:
        eng = ContinuousAutonomousEngine(store=self.store, workspace=self.ws)
        eng.cycle_count = 1
        with patch("tools.organ_smoke.run_organ_smoke", return_value={"scores": {"front": 0.9, "coder": 0.8}}):
            out = leap_wiring.step_organs(eng)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["best"], "front")


class Activation0046OverlayTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ace-evo0046-overlay-")
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name) / "workspace"
        self.store = OperationalStore(self.ws)
        self.addCleanup(self.store.close)
        self.ws.mkdir(parents=True, exist_ok=True)

        reg = BrainRegistry(self.ws / "brain_registry.json")
        reg.register("b-front", kind="local", descriptor="Qwen3-8B", status="active")
        reg.register("b-ext", kind="bridge", descriptor="gemini", status="declared-unavailable")

        (self.ws / "director_exec_receipts.jsonl").write_text(
            json.dumps({"task_id": "rx1", "organ": "groq/qwen", "status": "completed", "at": "2026-11-20T01:00:00Z"}) + "\n",
            encoding="utf-8",
        )
        (self.ws / "proposal_grounding.jsonl").write_text(
            json.dumps({"task_id": "rx1", "organ": "groq/qwen", "grounded": True, "at": "2026-11-20T01:00:00Z"}) + "\n",
            encoding="utf-8",
        )
        (self.ws / "organ.log").write_text(
            "2026-11-20T01:00:00Z llama-server booting\n"
            "2026-11-20T01:00:05Z brain_bridge restarting service\n",
            encoding="utf-8",
        )
        (self.ws / "organ_outputs.jsonl").write_text(
            "\n".join([
                json.dumps({"task_id": "t1", "organ": "groq/qwen", "status": "ok", "answer": "YA"}),
                json.dumps({"task_id": "t1", "organ": "gemini/flash", "status": "ok", "answer": "YA"}),
            ]) + "\n",
            encoding="utf-8",
        )
        (self.ws / "engine_events.jsonl").write_text(
            json.dumps({"ts": "2026-11-20T01:00:00Z", "state": "active", "cycle_seconds": 1.2}) + "\n",
            encoding="utf-8",
        )

    @unittest.skipUnless(_ALL_WIRED, "Memerlukan seluruh branch EVO 0046 AG151–AG159 terpasang")
    def test_all_nine_evo0046_steps_produce_artifacts_cleanly(self) -> None:
        db_files = [p for p in self.ws.rglob("*") if p.is_file() and p.suffix in (".db", ".sqlite", ".sqlite3")]
        self.assertTrue(db_files)
        db_before = db_files[0].read_bytes()

        eng = ContinuousAutonomousEngine(store=self.store, workspace=self.ws)
        eng.cycle_count = 1000
        for step_name in _EVO0046_STEPS:
            with self.subTest(step=step_name):
                res = getattr(leap_wiring, step_name)(eng)
                self.assertEqual(res.get("status"), "ok", f"{step_name} -> {res}")

        for name in (
            "brain_registry_snapshot.json",
            "organ_quality.json",
            "organ_forensics.jsonl",
            "organ_agreement.json",
            "engine_idle.json",
            "failover_accounting.jsonl",
            "ram_window_log.jsonl",
            "failover_drill.json",
            "home_replication_status.json",
        ):
            self.assertTrue((self.ws / name).is_file(), f"missing artifact {name}")

        self.assertEqual(db_files[0].read_bytes(), db_before)

    @unittest.skipUnless(_ALL_WIRED, "Memerlukan seluruh branch EVO 0046 AG151–AG159 terpasang")
    def test_engine_cycles_1000_and_1001_trigger_all_evo0046_cadences(self) -> None:
        eng = ContinuousAutonomousEngine(store=self.store, workspace=self.ws)
        eng.cycle_count = 999
        with patch.dict(os.environ, {"ACE_LEAPS": "1"}, clear=False), \
                patch("tools.organ_smoke.run_organ_smoke", return_value={"scores": {"front": 0.9, "coder": 0.8}}):
            s1000 = eng.execute_cycle()
            s1001 = eng.execute_cycle()
        self.assertEqual(s1000["cycle"], 1000)
        self.assertEqual(s1001["cycle"], 1001)
        for name in (
            "brain_registry_snapshot.json",
            "organ_quality.json",
            "organ_forensics.jsonl",
            "organ_agreement.json",
            "engine_idle.json",
            "failover_accounting.jsonl",
            "ram_window_log.jsonl",
            "failover_drill.json",
            "home_replication_status.json",
        ):
            self.assertTrue((self.ws / name).is_file(), f"cycles 1000-1001 missing {name}")


if __name__ == "__main__":
    unittest.main()
