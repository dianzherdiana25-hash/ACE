"""Tes integrasi paket EVO 0045 (AG141–AG149: Perkakas & Proyek).

Berjalan aman di baseline (`main`) dengan menguji `step_projects` dasar,
dan membuka suite penuh end-to-end 9 langkah EVO 0045 di bawah `@unittest.skipUnless(_ALL_WIRED, ...)`
saat seluruh branch AG141–AG149 digabungkan.
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
from ace_operational.store import OperationalStore

_EVO0045_STEPS = (
    "step_tool_registry",
    "step_tool_forge",
    "step_tool_retirement_scan",
    "step_repo_arena",
    "step_evo_scaffold",
    "step_pattern_catalog",
    "step_builder_onboarding_pack",
    "step_pr_pack",
    "step_evo_results_audit",
)
_ALL_WIRED = all(hasattr(leap_wiring, name) for name in _EVO0045_STEPS)


class Activation0045BaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ace-evo0045-base-")
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name) / "workspace"
        self.store = OperationalStore(self.ws)
        self.addCleanup(self.store.close)

    def test_baseline_step_projects_works(self) -> None:
        eng = ContinuousAutonomousEngine(store=self.store, workspace=self.ws)
        eng.cycle_count = 10
        out = leap_wiring.step_projects(eng)
        self.assertEqual(out["status"], "ok")


class Activation0045OverlayTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="ace-evo0045-overlay-")
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name) / "workspace"
        self.store = OperationalStore(self.ws)
        self.addCleanup(self.store.close)
        self.ws.mkdir(parents=True, exist_ok=True)

        now = leap_wiring._now_iso()
        (self.ws / "tool_forge_spec.json").write_text(
            json.dumps({
                "name": "overlay_norm_helper",
                "origin_gap": "gap-0045",
                "io_contract": {"inputs": ["payload"], "output": "normalized"},
            }),
            encoding="utf-8",
        )
        (self.ws / "tool_registry.json").write_text(
            json.dumps({
                "tools": [
                    {"name": "overlay_norm_helper", "version": "1.0.0", "origin_gap": "gap-0045", "status": "adopted"},
                    {"name": "stale_probe", "version": "0.1.0", "origin_gap": "gap-old", "status": "adopted"},
                ]
            }),
            encoding="utf-8",
        )
        (self.ws / "tool_usage.jsonl").write_text(
            json.dumps({"tool": "overlay_norm_helper", "success": True, "ts": now}) + "\n",
            encoding="utf-8",
        )
        (self.ws / "evo_scaffold_request.json").write_text(
            json.dumps({
                "evo_id": "EVO_0066",
                "title": "Uji Lapisan Proyek EVO 0045",
                "claim": "Scaffold proyek terisolasi di workspace.",
            }),
            encoding="utf-8",
        )
        (self.ws / "patterns_distilled.jsonl").write_text(
            json.dumps({
                "schema": "ace.pattern-distilled.v1",
                "event_class": "pattern_distilled",
                "kind": "semantic",
                "staging_only": True,
                "source_episode": "ep-0045",
                "task_shape": {
                    "task_kind": "code",
                    "keywords": ["arena", "tool"],
                    "constraints_detected": ["isolated"],
                },
                "approach": ["jalani audit statis sebelum eksekusi"],
                "pitfalls": ["mengedit repo utama langsung"],
                "provenance": {"output_sha256": "a" * 64},
            }) + "\n",
            encoding="utf-8",
        )
        (self.ws / "pr_release_manifest.json").write_text(
            json.dumps({
                "branch": "gravity/evo0045-demo",
                "base_ref": "main",
                "manifest_sha256": "b" * 64,
                "files": [
                    {
                        "path": "tools/tool_registry.py",
                        "status": "M",
                        "classification": "tools",
                        "size_bytes": 256,
                        "sha256": "c" * 64,
                        "in_allowlist": True,
                    }
                ],
            }),
            encoding="utf-8",
        )
        cdir = self.ws / "evo_consolidations"
        cdir.mkdir(parents=True)
        (cdir / "EVO_0003.md").write_text(
            "# KONSOLIDASI EVO 0003\n\n## GATE G1 (PASS)\n\nLulus.\n",
            encoding="utf-8",
        )

    @unittest.skipUnless(_ALL_WIRED, "Memerlukan seluruh branch EVO 0045 AG141–AG149 terpasang")
    def test_all_nine_evo0045_steps_produce_artifacts_cleanly(self) -> None:
        eng = ContinuousAutonomousEngine(store=self.store, workspace=self.ws)
        eng.cycle_count = 200
        for step_name in _EVO0045_STEPS:
            with self.subTest(step=step_name):
                res = getattr(leap_wiring, step_name)(eng)
                self.assertEqual(res.get("status"), "ok", f"{step_name} -> {res}")

        for name in (
            "tool_registry_snapshot.json",
            "tool_forge_log.jsonl",
            "tool_retirement_candidates.json",
            "repo_arena_report.json",
            "project_scaffolds.jsonl",
            "pattern_catalog.json",
            "builder_onboarding.md",
            "pr_pack.json",
            "evo_results_summary.json",
        ):
            self.assertTrue((self.ws / name).is_file(), f"missing artifact {name}")

    @unittest.skipUnless(_ALL_WIRED, "Memerlukan seluruh branch EVO 0045 AG141–AG149 terpasang")
    def test_engine_cycle_200_triggers_all_evo0045_cadences(self) -> None:
        eng = ContinuousAutonomousEngine(store=self.store, workspace=self.ws)
        eng.cycle_count = 199
        with patch.dict(os.environ, {"ACE_LEAPS": "1"}, clear=False):
            summary = eng.execute_cycle()
        self.assertEqual(summary["cycle"], 200)
        for name in (
            "tool_registry_snapshot.json",
            "tool_forge_log.jsonl",
            "tool_retirement_candidates.json",
            "repo_arena_report.json",
            "project_scaffolds.jsonl",
            "pattern_catalog.json",
            "builder_onboarding.md",
            "pr_pack.json",
            "evo_results_summary.json",
        ):
            self.assertTrue((self.ws / name).is_file(), f"cycle 200 missing {name}")


if __name__ == "__main__":
    unittest.main()
