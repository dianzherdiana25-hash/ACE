"""Tes integrasi paket EVO 0041 (AG101–AG109: Memori & Recall).

Berjalan aman di baseline (`main`) dengan menguji struktur Step 3d serta kontrak
dasar `leap_wiring`, dan membuka suite penuh end-to-end 9 langkah EVO 0041
saat seluruh branch AG101–AG109 digabungkan.
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
from ace_operational.cognitive_memory import CognitiveMemory
from ace_operational.store import OperationalStore

_EVO0041_STEPS = (
    "step_memory_hygiene_audit",
    "step_memory_decay",
    "step_memory_chain_compare",
    "step_recall",
    "step_recall_probes",
    "step_embedding_index",
    "step_introspect_recall",
    "step_transfer_probe",
    "step_metacog_consolidation",
)
_ALL_WIRED = all(hasattr(leap_wiring, name) for name in _EVO0041_STEPS)


class Activation0041BaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ace-evo0041-")
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name) / "workspace"
        self.store = OperationalStore(self.ws)
        self.addCleanup(self.store.close)
        self.mem_dir = self.ws / "cognitive_memory"
        self.mem = CognitiveMemory(self.mem_dir)
        d1 = self.mem.anchor_evidence(b"evo0041-evidence-1")
        self.mem.remember(
            kind="episodic",
            content={"topic": "morfologi imbuhan", "text": "latihan morfologi berlari menulis"},
            source_kind="evidence",
            source_ref=d1,
            confidence=0.9,
        )
        self.mem.remember(
            kind="episodic",
            content={"topic": "csv pipeline", "text": "validasi sha256 pipeline csv json"},
            source_kind="evidence",
            source_ref=d1,
            confidence=0.85,
        )
        self.store.record_gap(
            source_task_id="evo0041-gap-1",
            error_type="skill_missing",
            missing_skill_or_tool="morfologi imbuhan",
            description_id="butuh contoh morfologi imbuhan berlari",
            reproduction_ref="probe:evo0041",
        )

    def test_baseline_memory_fixture_and_recall_step_safe(self) -> None:
        mem_path = self.mem_dir / "memory.jsonl"
        eng = ContinuousAutonomousEngine(store=self.store, workspace=self.ws)
        eng.cycle_count = 10
        before_bytes = mem_path.read_bytes()
        out = leap_wiring.step_recall(eng)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(mem_path.read_bytes(), before_bytes)
        self.assertTrue((self.ws / "semantic_memory.json").is_file())
        self.assertTrue((self.ws / "recall_probe.jsonl").is_file())

    def test_empty_workspace_recall_fails_closed(self) -> None:
        empty_ws = Path(self._tmp.name) / "empty_ws"
        empty_store = OperationalStore(empty_ws)
        self.addCleanup(empty_store.close)
        eng = ContinuousAutonomousEngine(store=empty_store, workspace=empty_ws)
        eng.cycle_count = 10
        out = leap_wiring.step_recall(eng)
        self.assertEqual(out["status"], "ok")


class Activation0041OverlayTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ace-evo0041-overlay-")
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name) / "workspace"
        self.store = OperationalStore(self.ws)
        self.addCleanup(self.store.close)
        self.mem_dir = self.ws / "cognitive_memory"
        self.mem = CognitiveMemory(self.mem_dir)
        d1 = self.mem.anchor_evidence(b"evo0041-overlay-evidence")
        self.mem.remember(
            kind="episodic",
            content={"topic": "bridge relay backoff", "text": "jeda eksponensial cegah busy loop"},
            source_kind="evidence",
            source_ref=d1,
            confidence=0.92,
        )
        self.mem.remember(
            kind="episodic",
            content={"topic": "morfologi bahasa indonesia", "text": "imbuhan awalan ber me di ter"},
            source_kind="evidence",
            source_ref=d1,
            confidence=0.88,
        )
        self.store.record_gap(
            source_task_id="evo0041-overlay-gap",
            error_type="skill_missing",
            missing_skill_or_tool="bridge relay backoff",
            description_id="jeda eksponensial bridge relay",
            reproduction_ref="probe:overlay",
        )
        gid = self.store.list_gaps(status="OPEN")[0]["gap_id"]
        self.store.create_task(
            kind="director_proposal",
            title_id="Proposal Tertambat",
            user_request="uji jangkar",
            normalized_goal="Proposal Tertambat",
            model_backend="groq/openai/gpt-oss-120b",
            priority=5,
            checkpoint={"proposal": {"based_on": [gid]}},
            hold_for_review=True,
        )
        self.store.create_task(
            kind="director_proposal",
            title_id="Proposal Tanpa Based On",
            user_request="uji tanpa jangkar",
            normalized_goal="Proposal Tanpa Based On",
            model_backend="groq/openai/gpt-oss-120b",
            priority=5,
            checkpoint={"proposal": {}},
            hold_for_review=True,
        )

    @unittest.skipUnless(_ALL_WIRED, "Membutuhkan seluruh branch AG101–AG109 EVO 0041 digabungkan")
    def test_full_evo0041_pipeline_at_cycle_200(self) -> None:
        mem_path = self.mem_dir / "memory.jsonl"
        eng = ContinuousAutonomousEngine(store=self.store, workspace=self.ws)
        before_leap_bytes = mem_path.read_bytes()

        # Pastikan seluruh fungsi step baru murni baca terhadap memory.jsonl
        for fn_name in _EVO0041_STEPS:
            res = getattr(leap_wiring, fn_name)(eng)
            self.assertEqual(res.get("status"), "ok", f"{fn_name} gagal: {res}")
        self.assertEqual(mem_path.read_bytes(), before_leap_bytes)

        eng.cycle_count = 199  # execute_cycle menaikkan ke 200 (%10, %25, %50, %200 aktif semua)
        with patch.dict(os.environ, {"ACE_LEAPS": "1"}, clear=False):
            summary = eng.execute_cycle()

        self.assertEqual(summary["cycle"], 200)
        leaps = summary.get("leaps", {})
        for expected_key in (
            "recall",
            "memory_hygiene",
            "memory_decay",
            "memory_chain_compare",
            "recall_probes",
            "embedding_index",
            "introspect_recall",
            "transfer_probe",
            "metacog_consolidation",
        ):
            self.assertIn(expected_key, leaps, f"Step {expected_key} hilang di summary['leaps']")
            self.assertEqual(leaps[expected_key]["status"], "ok", f"Step {expected_key}: {leaps[expected_key]}")

        self.assertGreaterEqual(leaps["recall"]["anchor_audit"]["anchored"], 1)
        self.assertGreaterEqual(leaps["recall"]["anchor_audit"]["missing_based_on"], 1)

        expected_artifacts = (
            self.ws / "memory_hygiene.json",
            self.ws / "memory_decay_plan.json",
            self.ws / "memory_chain_report.json",
            self.ws / "memory_chain_prev.jsonl",
            self.ws / "anchor_audit.jsonl",
            self.ws / "recall_probes.json",
            self.ws / "cognitive_memory" / "embedding_index.jsonl",
            self.ws / "embedding_index_state.json",
            self.ws / "recall_introspection.jsonl",
            self.ws / "transfer_probe_report.json",
            self.ws / "metacog_consolidation.jsonl",
        )
        for art in expected_artifacts:
            self.assertTrue(art.is_file(), f"Artefak {art.name} tidak terbuat")

        # Pastikan rencana decay non-destruktif
        decay = json.loads((self.ws / "memory_decay_plan.json").read_text(encoding="utf-8"))
        self.assertFalse(decay.get("delete_records", False))


if __name__ == "__main__":
    unittest.main()
