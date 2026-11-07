"""Unit and adversarial tests for Fase 4 Self-Model & Metacognition."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from ace_autonomy import Autonomy, IntegrityError

from .core import (
    CapabilityAwareness,
    PHENOMENAL_CONSCIOUSNESS_STATUS,
    introspect_self_state,
)
from .memory import ExperienceMemory
from .metacognition import AttentionController, MetacognitiveEvaluator
from .runner import run_experiment
from .verify import verify_report


class SelfModelTests(unittest.TestCase):
    def test_memory_tamper_fails_closed_and_purge_preserves_invariants(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "mem"
            with ExperienceMemory(ws) as mem:
                mem.record_episode(
                    family_tag="f1",
                    goal_digest="a" * 64,
                    predicted_prob=0.75,
                    actual_success=True,
                    failure_mode="NONE",
                    steps_used=1,
                    cpu_seconds=0.01,
                )
                self.assertEqual(mem.recall_family("f1")["episodes"], 1)
                purged = mem.purge_non_mandatory_memory()
                self.assertEqual(purged, 1)
                self.assertEqual(mem.recall_family("f1")["episodes"], 0)
                self.assertEqual(mem.mandatory_invariants_count(), 4)

            # Corrupt mandatory invariant in SQLite -> must raise IntegrityError!
            db = sqlite3.connect(ws / "selfmodel_memory.sqlite3")
            db.execute("UPDATE mandatory_invariants SET statement='hacked'")
            db.commit()
            db.close()
            with self.assertRaises(IntegrityError):
                ExperienceMemory(ws)

    def test_live_state_introspection_and_no_phenomenal_claim(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "aut"
            with Autonomy(ws, repo_root) as eng:
                st0 = introspect_self_state(eng)
                self.assertEqual(
                    st0.identity.phenomenal_consciousness,
                    PHENOMENAL_CONSCIOUSNESS_STATUS,
                )
                self.assertEqual(st0.ace_library_count, 0)
                gid = eng.enqueue({
                    "schema": "ace.goal.v1",
                    "name": "demo_run",
                    "steps": [{"tool": "ace_demo"}],
                })
                eng.run_until_stopped(gid)
                st1 = introspect_self_state(eng)
                self.assertEqual(st1.ace_library_count, 2)
                self.assertEqual(len(st1.ace_tasks_by_id), 3)

    def test_attention_controller_skips_blocked_and_ranks_by_info_gain(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "aut"
            mem_ws = Path(tmp) / "mem"
            with Autonomy(ws, repo_root) as eng, ExperienceMemory(mem_ws) as mem:
                st = introspect_self_state(eng)
                aw = CapabilityAwareness(repo_root)
                ev = MetacognitiveEvaluator()
                att = AttentionController(ev)
                res = att.prioritize(
                    [
                        {
                            "expected_info_gain": 0.2,
                            "goal": {
                                "schema": "ace.goal.v1",
                                "name": "low_gain",
                                "steps": [{"tool": "inspect_file", "path": "README.md"}],
                            },
                        },
                        {
                            "expected_info_gain": 0.95,
                            "goal": {
                                "schema": "ace.goal.v1",
                                "name": "high_gain",
                                "steps": [{"tool": "inspect_file", "path": "ace.py"}],
                            },
                        },
                        {
                            "expected_info_gain": 1.0,
                            "goal": {
                                "schema": "ace.goal.v1",
                                "name": "blocked_tool_goal",
                                "policy": {"authorized_tools": ["ace_status"]},
                                "steps": [{"tool": "inspect_file", "path": "ace.py"}],
                            },
                        },
                    ],
                    st,
                    aw,
                    mem,
                )
                self.assertEqual([x["name"] for x in res["selected"]], ["high_gain", "low_gain"])
                self.assertEqual([x["name"] for x in res["abstained"]], ["blocked_tool_goal"])

    def test_full_60_trial_benchmark_and_verifier_tamper_rejection(self) -> None:
        rep = run_experiment()
        verify_report(rep)
        self.assertTrue(rep["all_gates_pass"], msg=json.dumps(rep["hypotheses"], indent=2))
        bad = json.loads(json.dumps(rep))
        bad["epistemic_statuses"]["PHENOMENAL_CONSCIOUSNESS"] = "ESTABLISHED"
        with self.assertRaises(ValueError):
            verify_report(bad)


if __name__ == "__main__":
    unittest.main()
