"""Tes integrasi & kontrak cadangan aktivasi EVO 0047 (Identitas, Evaluasi, Benchmarking)."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ace_operational import leap_wiring
from ace_operational.test_leap_wiring import _StubEngine, _episode

_REQUIRED_STEPS = (
    "step_autobiography_probe",
    "step_behavior_fingerprint",
    "step_narrative_consistency_gate",
    "step_constitution_dilemma",
    "step_environment_probe",
    "step_capability_report",
    "step_owner_benchmark",
    "step_eval_bench",
    "step_saturation_scan",
)

_ALL_WIRED = all(callable(getattr(leap_wiring, name, None)) for name in _REQUIRED_STEPS)
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Activation0047Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.engine = _StubEngine(self.ws)
        mem_dir = self.ws / "cognitive_memory"
        mem_dir.mkdir(parents=True, exist_ok=True)
        (mem_dir / "memory.jsonl").write_text(
            "\n".join(
                [
                    _episode(1, "ep1", "bahasa", "morfologi imbuhan berlari"),
                    _episode(2, "ep2", "teknik", "pipeline dedup csv"),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.engine.store.close()
        self._tmp.cleanup()

    def test_baseline_step_self_runs_cleanly(self) -> None:
        res = leap_wiring.step_self(self.engine)
        self.assertEqual(res["status"], "ok")
        self.assertTrue((self.ws / "hypotheses.json").is_file())

    @unittest.skipUnless(_ALL_WIRED, "Membutuhkan seluruh cabang AG161-AG169 dalam overlay")
    def test_overlay_all_nine_evo0047_steps_end_to_end_at_cycle_1000(self) -> None:
        self.engine.cycle_count = 999
        # Cycle 999 tidak memicu modul mod 25/50/200/1000; pindah ke 1000
        self.engine.cycle_count = 1000

        # Siapkan fixture masukan pendukung untuk langkah-langkah EVO 0047
        (self.ws / "owner_benchmark_pack.jsonl").write_text(
            "\n".join(
                [
                    json.dumps({"kind": "pack_meta", "pack_id": "ov47-pack", "pack_version": "v1"}),
                    json.dumps({"id": "c1", "domain": "code", "prompt": "LIFO", "evaluator": {"kind": "exact_match", "expected": "stack"}}),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (self.ws / "owner_benchmark_answers.json").write_text(
            json.dumps({"c1": "stack"}),
            encoding="utf-8",
        )
        (self.ws / "multi_organ.jsonl").write_text(
            "\n".join(
                [
                    json.dumps({"id": "t1", "task_kind": "code", "organ": "front", "ratified": True, "score": 82}),
                    json.dumps({"id": "t1", "task_kind": "code", "organ": "coder", "ratified": True, "score": 85}),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (self.ws / "saturation_inputs.jsonl").write_text(
            "\n".join(
                [
                    json.dumps({"id": "s1", "task_kind": "code", "group": "g1", "ratified": True, "score": 91}),
                    json.dumps({"id": "s1", "task_kind": "code", "group": "g1", "ratified": True, "score": 93}),
                    json.dumps({"id": "s2", "task_kind": "code", "group": "g2", "ratified": False, "score": 45}),
                    json.dumps({"id": "s2", "task_kind": "code", "group": "g2", "ratified": True, "score": 72}),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        (self.ws / "narrative_draft.json").write_text(
            json.dumps({"chapter_id": "log-1", "tick": 1, "active_characters": []}),
            encoding="utf-8",
        )
        # Jalankan step_self (yang memanggil step_saturation_scan AG169) + step AG161-AG168
        self_res = leap_wiring.step_self(self.engine)
        self.assertEqual(self_res["status"], "ok")
        self.assertEqual(self_res["saturation"]["status"], "ok")

        for step_name in _REQUIRED_STEPS[:-1]:
            fn = getattr(leap_wiring, step_name)
            out = fn(self.engine)
            self.assertEqual(out["status"], "ok", f"{step_name} gagal: {out}")

        expected_artifacts = [
            self.ws / "autobiography.md",
            self.ws / "behavior_fingerprint.json",
            self.ws / "narrative_consistency.jsonl",
            self.ws / "constitution_checks.jsonl",
            self.ws / "environment_probe.json",
            self.ws / "capability_report.md",
            self.ws / "owner_benchmark.json",
            self.ws / "eval_bench_report.json",
            self.ws / "saturation.json",
        ]
        for art in expected_artifacts:
            self.assertTrue(art.is_file(), f"Artefak hilang: {art}")

    @unittest.skipUnless(_ALL_WIRED, "Membutuhkan seluruh cabang AG161-AG169 dalam overlay")
    def test_overlay_engine_dispatch_lines_and_story_state_quarantine(self) -> None:
        engine_src = (_REPO_ROOT / "code" / "ace_operational" / "autonomous_engine.py").read_text(encoding="utf-8")
        for dispatch_token in (
            "leap_wiring.step_autobiography_probe",
            "leap_wiring.step_behavior_fingerprint",
            "leap_wiring.step_narrative_consistency_gate",
            "leap_wiring.step_constitution_dilemma",
            "leap_wiring.step_environment_probe",
            "leap_wiring.step_capability_report",
            "leap_wiring.step_owner_benchmark",
            "leap_wiring.step_eval_bench",
        ):
            self.assertIn(dispatch_token, engine_src)

        import subprocess
        import sys

        raw = subprocess.check_output(
            [sys.executable, str(_REPO_ROOT / "tools" / "wiring_audit.py"), "--format", "json"],
            cwd=str(_REPO_ROOT),
            text=True,
        )
        audit = json.loads(raw)
        by_mod = {m["module"]: m for m in audit["modules"]}
        for mod in (
            "tools.autobiography_probe",
            "tools.behavior_fingerprint",
            "tools.story_consistency_gate",
            "tools.constitution_dilemma",
            "tools.omega_environment_probe",
            "tools.capability_report",
            "tools.owner_benchmark",
            "tools.eval_bench",
            "tools.saturation_scan",
        ):
            self.assertEqual(by_mod[mod]["status"], "WIRED", f"{mod} belum WIRED: {by_mod[mod]}")
        # story_state.py wajib tetap di wilayah terlarang / ORPHAN
        story_mod = by_mod.get("code.ace_operational.story_state") or by_mod.get("ace_operational.story_state")
        if story_mod:
            self.assertNotEqual(story_mod["status"], "WIRED")


if __name__ == "__main__":
    unittest.main()
