"""Tes integrasi paket EVO 0044 (AG131–AG139: Rumah, Kustodi & Ketangguhan).

Berjalan aman di baseline (`main`) dengan menguji `step_checkpoint` & `step_house` dasar,
dan membuka suite penuh end-to-end 9 langkah EVO 0044 di bawah `@unittest.skipUnless(_ALL_WIRED, ...)`
saat seluruh branch AG131–AG139 digabungkan.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ace_operational import leap_wiring
from ace_operational.autonomous_engine import ContinuousAutonomousEngine
from ace_operational.store import OperationalStore

_EVO0044_STEPS = (
    "step_receipt_chain_verify",
    "step_custody_manifest_check",
    "step_checkpoint_chain_verify",
    "step_verify_self_dev",
    "step_restore_drill",
    "step_coverage_and_flaky_audit",
    "step_bundle_manifest",
    "step_migration_rehearsal",
    "step_run_evidence_pack",
)
_ALL_WIRED = all(hasattr(leap_wiring, name) for name in _EVO0044_STEPS)


class Activation0044BaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ace-evo0044-base-")
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name) / "workspace"
        self.store = OperationalStore(self.ws)
        self.addCleanup(self.store.close)

    def test_baseline_checkpoint_and_house_work(self) -> None:
        eng = ContinuousAutonomousEngine(store=self.store, workspace=self.ws)
        eng.cycle_count = 1
        ckpt = leap_wiring.step_checkpoint(eng)
        self.assertEqual(ckpt["status"], "ok")
        self.assertEqual(ckpt["chain_len"], 1)
        house = leap_wiring.step_house(eng)
        self.assertEqual(house["status"], "ok")


class Activation0044OverlayTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ace-evo0044-overlay-")
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name) / "workspace"
        self.store = OperationalStore(self.ws)
        self.addCleanup(self.store.close)
        self.ws.mkdir(parents=True, exist_ok=True)

        # Receipt chain fixture
        (self.ws / "director_exec_receipts.jsonl").write_text(
            "\n".join([
                json.dumps({"status": "started", "task_id": "t-44", "at": "2026-11-20T01:00:00Z"}),
                json.dumps({"status": "completed", "task_id": "t-44", "at": "2026-11-20T01:02:00Z"}),
            ]) + "\n",
            encoding="utf-8",
        )

        # Custody fixture
        cust = self.ws / "custody"
        cust.mkdir(parents=True, exist_ok=True)
        cust_file = cust / "state.json"
        cust_file.write_text('{"custody": "ok"}\n', encoding="utf-8")
        digest = hashlib.sha256(cust_file.read_bytes()).hexdigest()
        (self.ws / "custody_manifest.json").write_text(
            json.dumps({"files": [{"path": "state.json", "sha256": digest}]}),
            encoding="utf-8",
        )

        # Bundle manifest fixture (names-only audit, canary must never leak)
        from tools import bridge_home
        self.canary = "TEST_CANARY_NO_LEAK_0044"
        (self.ws / "bundle_manifest.json").write_text(
            json.dumps({
                "schema": bridge_home.BUNDLE_MANIFEST_SCHEMA,
                "entries": [{"name": n, "value": self.canary} for n in bridge_home.REQUIRED_ENTRY_NAMES],
            }),
            encoding="utf-8",
        )

        # Live workspace artifact that isolated steps must never mutate
        self.note = self.ws / "state_note.json"
        self.note.write_bytes(b'{"immutable": true}\n')

    @unittest.skipUnless(_ALL_WIRED, "Memerlukan seluruh branch EVO 0044 AG131–AG139 terpasang")
    def test_all_nine_evo0044_steps_produce_artifacts_cleanly(self) -> None:
        eng = ContinuousAutonomousEngine(store=self.store, workspace=self.ws)
        eng.cycle_count = 1000
        self.assertEqual(leap_wiring.step_checkpoint(eng)["status"], "ok")

        for step_name in _EVO0044_STEPS:
            with self.subTest(step=step_name):
                res = getattr(leap_wiring, step_name)(eng)
                self.assertEqual(res.get("status"), "ok", f"{step_name} -> {res}")

        expected_artifacts = (
            "receipt_chain_status.json",
            "custody_check.json",
            "checkpoint_chain_status.json",
            "self_verification.json",
            "restore_drill_report.json",
            "test_health.json",
            "bundle_status.json",
            "bundle_manifest_prev.json",
            "migration_rehearsal.json",
            "run_evidence_pack.json",
        )
        for name in expected_artifacts:
            self.assertTrue((self.ws / name).is_file(), f"missing artifact {name}")

        self.assertEqual(self.note.read_bytes(), b'{"immutable": true}\n')
        self.assertNotIn(self.canary, (self.ws / "bundle_status.json").read_text(encoding="utf-8"))
        self.assertNotIn(self.canary, (self.ws / "bundle_manifest_prev.json").read_text(encoding="utf-8"))

    @unittest.skipUnless(_ALL_WIRED, "Memerlukan seluruh branch EVO 0044 AG131–AG139 terpasang")
    def test_engine_cycle_1000_triggers_all_evo0044_cadences(self) -> None:
        eng = ContinuousAutonomousEngine(store=self.store, workspace=self.ws)
        eng.cycle_count = 999
        with patch.dict(os.environ, {"ACE_LEAPS": "1"}, clear=False):
            summary = eng.execute_cycle()
        self.assertEqual(summary["cycle"], 1000)
        for name in (
            "receipt_chain_status.json",
            "custody_check.json",
            "checkpoint_chain_status.json",
            "self_verification.json",
            "restore_drill_report.json",
            "test_health.json",
            "bundle_status.json",
            "migration_rehearsal.json",
            "run_evidence_pack.json",
        ):
            self.assertTrue((self.ws / name).is_file(), f"cycle 1000 missing {name}")


if __name__ == "__main__":
    unittest.main()
