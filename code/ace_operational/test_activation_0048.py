"""Tes integrasi & cadangan aktivasi EVO 0048 (Kesadaran Diri & Metakognisi)."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ace_operational import leap_wiring
from ace_operational.cognitive_memory import CognitiveMemory
from ace_operational.test_leap_wiring import _StubEngine

_REQUIRED_STEPS = (
    "step_self_assessment",
    "step_continuity_probe",
    "step_periodic_self_report",
    "step_daily_digest",
    "step_metacog_consolidate",
    "step_writeback_diagnose",
    "step_self_dev_git_audit",
    "step_successor_inventory",
    "step_successor_variant",
)

_ALL_WIRED = all(callable(getattr(leap_wiring, name, None)) for name in _REQUIRED_STEPS)
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Activation0048Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.engine = _StubEngine(self.ws)
        CognitiveMemory(self.ws / "cognitive_memory").remember(
            kind="semantic",
            content={"topic": "metacog", "text": "rantai hash valid untuk overlay 0048"},
            source_kind="operator",
        )

    def tearDown(self) -> None:
        self.engine.store.close()
        self._tmp.cleanup()

    def test_baseline_checkpoint_runs_cleanly(self) -> None:
        res = leap_wiring.step_checkpoint(self.engine)
        self.assertEqual(res["status"], "ok")
        self.assertTrue((self.ws / "step_checkpoints.jsonl").is_file())

    @unittest.skipUnless(_ALL_WIRED, "Membutuhkan seluruh cabang AG171-AG179 dalam overlay")
    def test_overlay_all_nine_evo0048_steps_end_to_end_at_cycle_1000(self) -> None:
        self.engine.cycle_count = 1000
        self.engine.store.record_receipt(
            task_id="t48",
            action_kind="check",
            input_data=b"",
            output_data=b"",
            command_or_operation="fixture",
            exit_code=0,
            passed=True,
        )

        # Fixture pendukung
        (self.ws / "metacog_observations.json").write_text(
            json.dumps(
                {
                    "records": [
                        {"id": "o1", "domain": "code", "actual_success": False, "predicted_prob": 0.85, "summary": "bridge retry"},
                        {"id": "o2", "domain": "code", "actual_success": False, "predicted_prob": 0.80, "summary": "bridge retry"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        repo_dir = self.ws / "mini_repo"
        repo_dir.mkdir()
        env_git = {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "t@example.com",
            "PATH": "/usr/bin:/bin",
        }
        subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True, env=env_git)
        (repo_dir / "f.txt").write_text("v1\n", encoding="utf-8")
        subprocess.run(["git", "add", "f.txt"], cwd=repo_dir, check=True, env=env_git)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo_dir, check=True, env=env_git)
        oid = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_dir, text=True).strip()
        (self.ws / "self_dev_audit_spec.json").write_text(
            json.dumps({"repo_dir": str(repo_dir), "base": oid, "tip": oid, "expected": []}),
            encoding="utf-8",
        )
        (self.ws / "successor_snapshot").mkdir()
        (self.ws / "successor_snapshot" / "item.jsonl").write_text(
            json.dumps({"tag": "successor-0006", "status": "ok"}) + "\n",
            encoding="utf-8",
        )
        (self.ws / "successor_variant_spec.json").write_text(
            json.dumps(
                {
                    "variant_id": "v-48",
                    "origin_commit": oid,
                    "target_file": "tools/x.py",
                    "diff_text": "--- a/tools/x.py\n+++ b/tools/x.py\n@@ -1 +1 @@\n-a=1\n+a=2\n",
                    "prediction": {"expected_advantage": "clean", "success_metric": "score"},
                }
            ),
            encoding="utf-8",
        )

        db_before = (self.ws / "ace_operational.sqlite3").read_bytes()
        for step_name in _REQUIRED_STEPS:
            fn = getattr(leap_wiring, step_name)
            out = fn(self.engine)
            self.assertEqual(out["status"], "ok", f"{step_name} gagal: {out}")

        # writeback_diagnose tidak boleh mengubah byte DB sumber (note step_writeback_diagnose read-only snapshot)
        # Cek semua artefak EVO 0048 tertulis
        for rel in (
            "self_assessment_chain.jsonl",
            "self_assessment_latest.json",
            "continuity_probe.json",
            "periodic_self_report.json",
            "daily_digest.json",
            "metacog_consolidation.json",
            "writeback_diagnose.json",
            "self_dev_git_audit.json",
            "successor_inventory.json",
            "successor_variant_status.json",
        ):
            self.assertTrue((self.ws / rel).is_file(), f"Artefak hilang: {rel}")
        self.assertGreater(len(db_before), 0)

    @unittest.skipUnless(_ALL_WIRED, "Membutuhkan seluruh cabang AG171-AG179 dalam overlay")
    def test_overlay_engine_dispatch_lines_and_wiring_audit(self) -> None:
        engine_src = (_REPO_ROOT / "code" / "ace_operational" / "autonomous_engine.py").read_text(encoding="utf-8")
        for token in (
            "leap_wiring.step_self_assessment",
            "leap_wiring.step_continuity_probe",
            "leap_wiring.step_periodic_self_report",
            "leap_wiring.step_daily_digest",
            "leap_wiring.step_metacog_consolidate",
            "leap_wiring.step_writeback_diagnose",
            "leap_wiring.step_self_dev_git_audit",
            "leap_wiring.step_successor_inventory",
            "leap_wiring.step_successor_variant",
        ):
            self.assertIn(token, engine_src)

        raw = subprocess.check_output(
            [sys.executable, str(_REPO_ROOT / "tools" / "wiring_audit.py"), "--format", "json"],
            cwd=str(_REPO_ROOT),
            text=True,
        )
        by_mod = {m["module"]: m for m in json.loads(raw)["modules"]}
        for mod in (
            "tools.self_assessment",
            "tools.self_model_continuity_probe",
            "tools.periodic_self_report",
            "tools.daily_digest",
            "tools.metacog_memory_consolidate",
            "tools.writeback_diagnose",
            "tools.self_dev_git_audit",
            "tools.successor_inventory",
            "tools.successor_variant",
        ):
            self.assertEqual(by_mod[mod]["status"], "WIRED", f"{mod} belum WIRED: {by_mod[mod]}")
        self.assertNotIn("code/ace_operational/leap_wiring.py", by_mod["ace_operational.memory_writeback"]["non_test_callers"])


if __name__ == "__main__":
    unittest.main()
