"""Tes integrasi penuh Wave-2 Refill (AG201-AG223) & lintas seluruh AKTIVASI (EVO 0041-0051)."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ace_operational import leap_wiring
from ace_operational.test_leap_wiring import _StubEngine, _episode

_WAVE2_STEPS = (
    "step_bridge_self_check",
    "step_organ_registry_validate",
    "step_repo_cartography",
    "step_program_glossary",
    "step_seal_run",
    "step_arc_rubric",
    "step_specialization_delta",
    "step_curriculum_lab",
    "step_inheritance_probe",
    "step_recall_ablation",
    "step_corpus_freeze_packer",
    "step_relay_spool_tools",
    "step_director_screen",
    "step_redteam_rotation",
    "step_kbm_titles",
    "step_kbm_produce",
    "step_mutation_engine",
    "step_drift_quarantine",
    "step_atomic_lease",
    "step_evidence_archiver",
    "step_generational_ladder",
    "step_mobile_report",
    "step_mission_proposers",
)

_WAVE2_ARTIFACTS = (
    "bridge_self_check.json",
    "organ_registry_validation.json",
    "repo_cartography.json",
    "program_glossary.json",
    "seal_run_status.json",
    "arc_rubric.json",
    "specialization_delta.json",
    "curriculum_lab.md",
    "inheritance_probe.json",
    "recall_ablation.json",
    "corpus_freeze_pack.json",
    "relay_spool_validation.json",
    "director_screen.json",
    "redteam_rotation.json",
    "kbm_titles_report.json",
    "kbm_produce_status.json",
    "mutation_proposal.json",
    "drift_quarantine.json",
    "atomic_lease_status.json",
    "evidence_archiver_status.json",
    "generational_ladder.json",
    "mobile_report.md",
    "mission_proposer.json",
)

_WAVE2_TARGET_MODULES = (
    "tools.bridge_self_check",
    "tools.organ_registry_validate",
    "tools.repo_cartography",
    "tools.program_glossary",
    "tools.seal_run",
    "tools.arc_rubric",
    "tools.specialization_delta",
    "tools.curriculum_lab",
    "tools.inheritance_probe",
    "tools.recall_ablation",
    "tools.corpus_freeze_packer",
    "tools.relay_spool_tools",
    "tools.director_screen",
    "tools.redteam_rotation",
    "tools.kbm_titles",
    "tools.kbm_produce",
    "tools.kbm_production_queue",
    "ace_operational.mutation_engine",
    "ace_core_repair.drift_quarantine",
    "ace_self_dev.atomic_lease",
    "ace_self_dev.evidence_archiver",
    "ace_self_dev.generational_ladder",
    "ace_report.mobile_report",
    "ace_mission.proposers",
)

_REPRESENTATIVE_EARLIER = (
    "step_memory_hygiene_audit",    # EVO 0041
    "step_mastery_board",           # EVO 0042
    "step_director_prose_audit",    # EVO 0043
    "step_receipt_chain_verify",    # EVO 0044
    "step_tool_registry",           # EVO 0045
    "step_brain_registry",          # EVO 0046
    "step_capability_report",       # EVO 0047
    "step_self_assessment",         # EVO 0048
    "step_experiment_designer",     # EVO 0049
    "step_verdict_board",           # EVO 0050
)

_WAVE2_WIRED = all(callable(getattr(leap_wiring, n, None)) for n in _WAVE2_STEPS)
_TOTAL_WIRED = _WAVE2_WIRED and all(
    callable(getattr(leap_wiring, n, None)) for n in _REPRESENTATIVE_EARLIER
)
_REPO_ROOT = Path(__file__).resolve().parents[2]


class ActivationWave2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.engine = _StubEngine(self.ws)
        mem_dir = self.ws / "cognitive_memory"
        mem_dir.mkdir(parents=True, exist_ok=True)
        (mem_dir / "memory.jsonl").write_text(
            _episode(1, "ep1", "governansi", "audit wave2") + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.engine.store.close()
        self._tmp.cleanup()

    def test_baseline_checkpoint_and_self_run_cleanly(self) -> None:
        self.assertEqual(leap_wiring.step_checkpoint(self.engine)["status"], "ok")
        self.assertEqual(leap_wiring.step_self(self.engine)["status"], "ok")

    def test_wave2_step_and_artifact_inventories_match(self) -> None:
        self.assertEqual(len(_WAVE2_STEPS), 23)
        self.assertEqual(len(set(_WAVE2_STEPS)), 23)
        self.assertEqual(len(_WAVE2_ARTIFACTS), 23)
        self.assertEqual(len(set(_WAVE2_ARTIFACTS)), 23)
        self.assertEqual(len(_WAVE2_TARGET_MODULES), 24)

    @unittest.skipUnless(_WAVE2_WIRED, "Membutuhkan seluruh cabang AG201-AG223 dalam overlay")
    def test_overlay_wave2_all_steps_end_to_end(self) -> None:
        self.engine.cycle_count = 1000
        for name in _WAVE2_STEPS:
            out = getattr(leap_wiring, name)(self.engine)
            self.assertEqual(out["status"], "ok", f"{name} gagal: {out}")

        for rel in _WAVE2_ARTIFACTS:
            self.assertTrue((self.ws / rel).is_file(), f"Artefak Wave-2 hilang: {rel}")

        engine_src = (_REPO_ROOT / "code" / "ace_operational" / "autonomous_engine.py").read_text(encoding="utf-8")
        for name in _WAVE2_STEPS:
            self.assertIn(f"leap_wiring.{name}", engine_src)

        tree = ast.parse((_REPO_ROOT / "code" / "ace_operational" / "leap_wiring.py").read_text(encoding="utf-8"))
        fn_names = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
        dups = [x for x in set(fn_names) if fn_names.count(x) > 1]
        self.assertEqual(dups, [], f"Duplikat fungsi di leap_wiring.py: {dups}")

    @unittest.skipUnless(_TOTAL_WIRED, "Membutuhkan overlay total EVO 0041-0051 (AG101-AG223)")
    def test_total_overlay_wiring_audit_and_quarantine(self) -> None:
        raw = subprocess.check_output(
            [sys.executable, str(_REPO_ROOT / "tools" / "wiring_audit.py"), "--format", "json"],
            cwd=str(_REPO_ROOT),
            text=True,
        )
        audit = json.loads(raw)
        summary = audit["summary"]
        self.assertGreaterEqual(summary["wired"], 417)
        self.assertEqual(summary["menunggu_engineer_utama"], 23)

        by_mod = {m["module"]: m for m in audit["modules"]}
        for mod in _WAVE2_TARGET_MODULES:
            self.assertEqual(by_mod[mod]["status"], "WIRED", f"{mod} belum WIRED")

        for protected in (
            "ace_operational.abc_v3_scorer",
            "ace_operational.admission_hygiene",
            "ace_operational.memory_writeback",
            "ace_operational.story_state",
            "tools.self_send",
        ):
            self.assertNotIn("code/ace_operational/leap_wiring.py", by_mod[protected]["non_test_callers"])


if __name__ == "__main__":
    unittest.main()
