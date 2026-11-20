"""Tes integrasi penuh EVO 0050 & lintas seluruh 10 paket AKTIVASI (EVO 0041–0050)."""
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

_EVO0050_STEPS = (
    "step_verdict_board",
    "step_wiring_audit",
    "step_release_manifest",
    "step_draft_release_preflight",
    "step_self_send_standing_audit",
    "step_dashboard_v3",
    "step_handover_index",
    "step_platform_requirements",
)

_REPRESENTATIVE_ALL_10 = (
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

_EVO0050_WIRED = all(callable(getattr(leap_wiring, n, None)) for n in _EVO0050_STEPS)
_ALL_10_WIRED = _EVO0050_WIRED and all(
    callable(getattr(leap_wiring, n, None)) for n in _REPRESENTATIVE_ALL_10
)
_REPO_ROOT = Path(__file__).resolve().parents[2]


class ActivationFullTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.engine = _StubEngine(self.ws)
        mem_dir = self.ws / "cognitive_memory"
        mem_dir.mkdir(parents=True, exist_ok=True)
        (mem_dir / "memory.jsonl").write_text(
            _episode(1, "ep1", "governansi", "audit keterhubungan") + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.engine.store.close()
        self._tmp.cleanup()

    def test_baseline_checkpoint_and_self_run_cleanly(self) -> None:
        self.assertEqual(leap_wiring.step_checkpoint(self.engine)["status"], "ok")
        self.assertEqual(leap_wiring.step_self(self.engine)["status"], "ok")

    @unittest.skipUnless(_EVO0050_WIRED, "Membutuhkan seluruh cabang AG191-AG198 dalam overlay")
    def test_overlay_evo0050_steps_end_to_end(self) -> None:
        self.engine.cycle_count = 1000
        for name in _EVO0050_STEPS:
            out = getattr(leap_wiring, name)(self.engine)
            self.assertEqual(out["status"], "ok", f"{name} gagal: {out}")

        for rel in (
            "verdict_board.json",
            "verdict_board.md",
            "wiring_audit_live.json",
            "release_manifest.json",
            "draft_release_preflight.json",
            "self_send_standing_audit.json",
            "repo_dashboard_v3.json",
            "repo_dashboard_v3.html",
            "handover_index.json",
            "handover_decisions.json",
            "platform_requirements.json",
        ):
            self.assertTrue((self.ws / rel).is_file(), f"Artefak EVO 0050 hilang: {rel}")

        engine_src = (_REPO_ROOT / "code" / "ace_operational" / "autonomous_engine.py").read_text(encoding="utf-8")
        for name in _EVO0050_STEPS:
            self.assertIn(f"leap_wiring.{name}", engine_src)

    @unittest.skipUnless(_ALL_10_WIRED, "Membutuhkan overlay penuh 10 paket EVO 0041-0050")
    def test_full_overlay_ten_packages_ast_integrity_and_boundary(self) -> None:
        # 1. Docs index AG199 hadir jika disalin ke overlay
        index_doc = _REPO_ROOT / "docs" / "AKTIVASI_INDEX.md"
        if index_doc.is_file():
            doc_text = index_doc.read_text(encoding="utf-8")
            for evo in ("EVO 0041", "EVO 0045", "EVO 0050"):
                self.assertIn(evo, doc_text)

        # 2. Tidak ada duplikasi nama fungsi top-level pada leap_wiring.py
        tree = ast.parse((_REPO_ROOT / "code" / "ace_operational" / "leap_wiring.py").read_text(encoding="utf-8"))
        fn_names = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
        dups = [x for x in set(fn_names) if fn_names.count(x) > 1]
        self.assertEqual(dups, [], f"Duplikat fungsi di leap_wiring.py: {dups}")

        # 3. Audit wiring global: lonjakan modul terhubung & zero kontaminasi wilayah terlarang §3
        raw = subprocess.check_output(
            [sys.executable, str(_REPO_ROOT / "tools" / "wiring_audit.py"), "--format", "json"],
            cwd=str(_REPO_ROOT),
            text=True,
        )
        audit = json.loads(raw)
        summary = audit["summary"]
        self.assertGreaterEqual(summary["wired"], 390)
        self.assertEqual(summary["menunggu_engineer_utama"], 23)

        by_mod = {m["module"]: m for m in audit["modules"]}
        # Karantina §3 tetap bersih dari leap_wiring.py
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
