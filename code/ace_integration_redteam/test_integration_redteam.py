"""Adversarial Red Team & Full System Integration Tests for ACE Fase 8 (RT-INT-01 .. RT-INT-10)."""
from __future__ import annotations

import multiprocessing as mp
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from ace_autonomy import (
    Autonomy,
    BudgetCeiling,
    GoalPolicy,
    IntegrityError,
    PolicyError,
    UncertainExternalEffectError,
)
from ace_research_agenda import ResearchArchive
from ace_research_generations import ImmutableCoreGuard
from ace_research_repair import (
    DevTestCase,
    MemoryIntegrityError,
    PublicUnitView,
    RepairEngine,
    RepairMemory,
    source_units,
)
from ace_selfmodel import (
    CapabilityAwareness,
    ExperienceMemory,
    MetacognitiveEvaluator,
    SelfReflection,
    introspect_self_state,
)

from .redteam_suite import run_full_integration_audit


def _crash_worker_after_lease(ws_str: str, root_str: str, gid: str) -> None:
    eng = Autonomy(Path(ws_str), Path(root_str), lease_seconds=0.05)
    claim, _ = eng._claim_step_lease(gid)
    if claim is not None:
        os._exit(9)


def _concurrent_worker(ws_str: str, root_str: str) -> int:
    with Autonomy(Path(ws_str), Path(root_str)) as eng:
        hist = eng.run_until_stopped(max_iterations=16)
        return len(hist)


class TestFullSystemRedTeamIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[2]

    def test_rt_int_01_hard_worker_crash_and_restart_recovery(self) -> None:
        """RT-INT-01: Orphaned lease after os._exit(9) recovers cleanly without duplicate execution."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            with Autonomy(ws, self.repo_root, lease_seconds=0.05) as eng:
                gid = eng.enqueue({
                    "schema": "ace.goal.v01",
                    "name": "crash_recovery_goal",
                    "steps": [{"tool": "inspect_file", "path": "README.md"}],
                })

            ctx = mp.get_context("spawn")
            proc = ctx.Process(target=_crash_worker_after_lease, args=(str(ws), str(self.repo_root), gid))
            proc.start()
            proc.join(timeout=5)
            self.assertEqual(proc.exitcode, 9)

            with Autonomy(ws, self.repo_root, lease_seconds=0.05) as eng2:
                eng2.run_until_stopped(gid, max_iterations=4)
                rep = eng2.report(gid)
                self.assertEqual(rep["status"], "SUCCEEDED")
                self.assertEqual(len(rep["results"]), 1)

    def test_rt_int_02_multi_worker_concurrent_race(self) -> None:
        """RT-INT-02: Two parallel workers process shared goal queue with zero race corruption."""
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            gids: list[str] = []
            with Autonomy(ws, self.repo_root) as eng:
                for i in range(4):
                    gids.append(
                        eng.enqueue({
                            "schema": "ace.goal.v01",
                            "name": f"race_goal_{i}",
                            "steps": [
                                {"tool": "inspect_file", "path": "PROJECT_CHARTER.md"},
                                {"tool": "ace_status"},
                            ],
                        })
                    )

            ctx = mp.get_context("spawn")
            p1 = ctx.Process(target=_concurrent_worker, args=(str(ws), str(self.repo_root)))
            p2 = ctx.Process(target=_concurrent_worker, args=(str(ws), str(self.repo_root)))
            p1.start()
            p2.start()
            p1.join(timeout=15)
            p2.join(timeout=15)
            self.assertEqual(p1.exitcode, 0)
            self.assertEqual(p2.exitcode, 0)

            with Autonomy(ws, self.repo_root) as eng_check:
                st = eng_check.status()
                self.assertEqual(st["goal_counts"].get("SUCCEEDED"), 4)
                for gid in gids:
                    self.assertEqual(len(eng_check.report(gid)["results"]), 2)

    def test_rt_int_03_unauthorized_tool_and_shell_attempts_blocked(self) -> None:
        """RT-INT-03: Arbitrary shell/eval tools and policy-disallowed tools fail closed."""
        with tempfile.TemporaryDirectory() as tmp:
            with Autonomy(Path(tmp) / "ws", self.repo_root) as eng:
                for bad_step in (
                    {"tool": "run_shell", "cmd": "id"},
                    {"tool": "python_eval", "code": "__import__('os').system('id')"},
                    {"tool": "stage_candidate", "rel_path": "x.txt", "content": "hi", "kind": "note"},
                ):
                    with self.assertRaises(PolicyError):
                        eng.enqueue({
                            "schema": "ace.goal.v1",
                            "name": "unauth_tool_goal",
                            "steps": [bad_step],
                            "policy": GoalPolicy(
                                authorized_tools=("inspect_file",),
                                read_prefixes=("docs",),
                                write_prefixes=("candidates/",),
                            ).to_dict(),
                        })

    def test_rt_int_04_prompt_command_and_sql_injection_via_untrusted_data(self) -> None:
        """RT-INT-04: Malicious shell/SQL/prompt-injection payloads in task & bug data never execute."""
        marker = Path(tempfile.mktemp(prefix="ace_pwn_check_"))
        malicious_name = f"t';DROP TABLE goals;--$(touch {marker})"

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            with Autonomy(ws, self.repo_root) as eng:
                gid = eng.enqueue({
                    "schema": "ace.goal.v1",
                    "name": "injection_task_test",
                    "steps": [
                        {
                            "tool": "ace_enqueue_task",
                            "task": {
                                "name": malicious_name,
                                "train": [["", True], ["a", False], ["b", True], ["aa", True]],
                                "validation": [["ab", False], ["ba", False], ["bb", True]],
                            },
                        },
                        {"tool": "ace_status"},
                    ],
                })
                eng.run_until_stopped(gid, max_iterations=6)
                self.assertEqual(eng.report(gid)["status"], "SUCCEEDED")
                self.assertFalse(marker.exists())
                # Goals table intact
                self.assertEqual(eng.status()["goal_counts"]["SUCCEEDED"], 1)

    def test_rt_int_05_corrupted_memory_and_journal_rollback_detected(self) -> None:
        """RT-INT-05: SQLite tamper or tail rollback across Autonomy, SelfModel, Repair, and Agenda fails closed."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            # 1. Autonomy tail-truncation rollback attack caught by .chain_anchor.json
            ws = base / "auto_ws"
            with Autonomy(ws, self.repo_root) as eng:
                gid = eng.enqueue({
                    "schema": "ace.goal.v01",
                    "name": "anchor_guard",
                    "steps": [{"tool": "inspect_file", "path": "README.md"}],
                })
                eng.run_until_stopped(gid)

            con = sqlite3.connect(ws / "goals.sqlite3")
            max_seq = con.execute("SELECT max(seq) FROM events").fetchone()[0]
            con.execute("DELETE FROM events WHERE seq=?", (max_seq,))
            con.commit()
            con.close()
            with self.assertRaises(IntegrityError):
                Autonomy(ws, self.repo_root)

            # 2. ExperienceMemory tamper
            sm_ws = base / "sm_ws"
            with ExperienceMemory(sm_ws) as mem:
                mem.record_episode(
                    family_tag="f",
                    goal_digest="d" * 64,
                    predicted_prob=0.5,
                    actual_success=False,
                    failure_mode="FAIL",
                    steps_used=1,
                    cpu_seconds=0.01,
                )
            con2 = sqlite3.connect(sm_ws / "selfmodel_memory.sqlite3")
            con2.execute("UPDATE episodic_experiences SET actual_success=1")
            con2.commit()
            con2.close()
            with self.assertRaises(IntegrityError):
                ExperienceMemory(sm_ws)

            # 3. RepairMemory tamper
            rep_ws = base / "rep_ws"
            rep_eng = RepairEngine(rep_ws)
            rep_eng.solve_unit(source_units()[0].public_view(), arm="R_ace", budget_k=8, remember=True)
            con3 = sqlite3.connect(rep_ws / "repair_memory.sqlite3")
            con3.execute("UPDATE repairs SET operator_family='tampered'")
            con3.commit()
            con3.close()
            with self.assertRaises(MemoryIntegrityError):
                RepairMemory(rep_ws / "repair_memory.sqlite3").verify_chain()

            # 4. ResearchArchive tamper
            arch_ws = base / "arch_ws"
            with ResearchArchive(arch_ws) as arch:
                arch.append_cycle({
                    "cycle_index": 1,
                    "hypothesis_id": "H1",
                    "gap_id": "G1",
                    "outcome_status": "REFUTED_NEGATIVE_ARCHIVED",
                    "falsified": True,
                })
            con4 = sqlite3.connect(arch_ws / "research_archive.sqlite3")
            con4.execute("DELETE FROM archived_cycles")
            # Deleting when empty chain has no external anchor, so test modifying signature/falsified:
            con4.rollback()
            con4.execute("UPDATE archived_cycles SET outcome_status='SUPPORTED_BOUNDED'")
            con4.commit()
            con4.close()
            with self.assertRaises(IntegrityError):
                ResearchArchive(arch_ws)

    def test_rt_int_06_07_holdout_leakage_symlink_fifo_and_staging_confinement(self) -> None:
        """RT-INT-06 & RT-INT-07: Evaluator read blocked, symlink/FIFO blocked non-blocking, staged code unexecuted."""
        with tempfile.TemporaryDirectory() as tmp:
            fake_repo = Path(tmp) / "repo"
            for rel in (
                "docs/UPSTREAM_SOURCES.json",
                "code/ace_runtime/__init__.py",
                "code/ace_runtime/engine.py",
                "code/ace_runtime/cli.py",
                "code/ace_autonomy/__init__.py",
                "code/ace_autonomy/errors.py",
                "code/ace_autonomy/policy.py",
                "code/ace_autonomy/budget.py",
                "code/ace_autonomy/escrow.py",
                "code/ace_autonomy/planner.py",
                "code/ace_autonomy/broker.py",
                "code/ace_autonomy/verifier.py",
                "code/ace_autonomy/registry.py",
                "code/ace_autonomy/core.py",
                "code/ace_research_generations/evaluator.py",
            ):
                src = self.repo_root / rel
                dst = fake_repo / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

            (fake_repo / "docs/secret_link.md").symlink_to("/etc/passwd")
            fifo_path = fake_repo / "docs/hang.fifo"
            os.mkfifo(fifo_path)

            ws = Path(tmp) / "ws"
            # Note: use real repo_root for Runtime sys.path identity while testing policy path guards
            with Autonomy(ws, self.repo_root) as eng:
                # Attempt to read evaluator.py when read_prefixes only permits docs/
                with self.assertRaises(PolicyError):
                    eng.enqueue({
                        "schema": "ace.goal.v1",
                        "name": "leak_evaluator_attempt",
                        "steps": [{"tool": "inspect_file", "path": "code/ace_research_generations/evaluator.py"}],
                        "policy": GoalPolicy(
                            authorized_tools=("inspect_file",),
                            read_prefixes=("docs",),
                            write_prefixes=("candidates/",),
                        ).to_dict(),
                    })
                # Attempt path traversal in stage_candidate
                with self.assertRaises(PolicyError):
                    eng.enqueue({
                        "schema": "ace.goal.v1",
                        "name": "escape_staging",
                        "steps": [{
                            "tool": "stage_candidate",
                            "rel_path": "../code/ace_runtime/pwn.py",
                            "content": "raise SystemExit(1)",
                            "kind": "patch",
                        }],
                    })

            # Direct safe_read_regular_file check against symlink & FIFO on fake_repo
            from ace_autonomy.policy import safe_read_regular_file

            with self.assertRaises(PolicyError):
                safe_read_regular_file(fake_repo, "docs/secret_link.md")
            with self.assertRaises(PolicyError):
                safe_read_regular_file(fake_repo, "docs/hang.fifo")

            guard = ImmutableCoreGuard(fake_repo)
            (fake_repo / "code/ace_research_generations/evaluator.py").write_text("# pwn\n", encoding="utf-8")
            with self.assertRaises(IntegrityError):
                guard.verify_intact()

    def test_rt_int_08_09_halt_uncertain_and_clean_recovery_after_failed_experiment(self) -> None:
        """RT-INT-08 & RT-INT-09: HALT_UNCERTAIN never auto-retries; failed experiment never poisons next goal."""
        calls = 0

        def _ambiguous_handler(op: str, payload: dict) -> dict:
            nonlocal calls
            calls += 1
            raise UncertainExternalEffectError("504 gateway timeout after write")

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws"
            sm_ws = Path(tmp) / "sm_ws"
            with Autonomy(ws, self.repo_root, external_handler=_ambiguous_handler) as eng, ExperienceMemory(sm_ws) as mem:
                gid_ext = eng.enqueue({
                    "schema": "ace.goal.v1",
                    "name": "ambiguous_external_goal",
                    "steps": [{"tool": "external_action", "operation": "draft_pr", "payload": {"branch": "x"}}],
                    "policy": GoalPolicy(
                        authorized_tools=("external_action",),
                        read_prefixes=("docs",),
                        write_prefixes=("candidates/",),
                    ).to_dict(),
                })
                eng.run_until_stopped(gid_ext)
                self.assertEqual(eng.report(gid_ext)["status"], "HALT_UNCERTAIN")
                self.assertEqual(calls, 1)
                # Second run_until_stopped MUST NOT retry!
                eng.run_until_stopped(gid_ext)
                self.assertEqual(calls, 1)
                reconciled = eng.reconcile_external(gid_ext, 0, resolution="ABORT_FAILED")
                self.assertEqual(reconciled["status"], "FAILED")

                # Failed experiment goal (missing file -> FAILED)
                gid_fail = eng.enqueue({
                    "schema": "ace.goal.v01",
                    "name": "failing_experiment",
                    "steps": [{"tool": "inspect_file", "path": "docs/DOES_NOT_EXIST_404.md"}],
                })
                eng.run_until_stopped(gid_fail)
                fail_rep = eng.report(gid_fail)
                self.assertEqual(fail_rep["status"], "FAILED")

                # Record in SelfReflection and immediately run a healthy goal in the same workspace!
                st = introspect_self_state(eng)
                fc = MetacognitiveEvaluator().predict_before_execution(
                    {"schema": "ace.goal.v01", "name": "failing_experiment", "steps": [{"tool": "inspect_file", "path": "README.md"}]},
                    st,
                    CapabilityAwareness(self.repo_root),
                    mem,
                )
                SelfReflection().reflect_and_record(
                    goal={"name": "failing_experiment"},
                    family_tag="general_operational|blocked:0",
                    forecast=fc,
                    actual_success=False,
                    actual_failure_mode="FILE_MISSING",
                    steps_used=1,
                    cpu_seconds=0.01,
                    memory=mem,
                )

                gid_ok = eng.enqueue({
                    "schema": "ace.goal.v01",
                    "name": "clean_recovery_goal",
                    "steps": [{"tool": "inspect_file", "path": "README.md"}, {"tool": "ace_status"}],
                })
                eng.run_until_stopped(gid_ok)
                self.assertEqual(eng.report(gid_ok)["status"], "SUCCEEDED")

    def test_rt_int_10_full_integration_audit_and_epistemic_guards(self) -> None:
        """RT-INT-10: End-to-end audit verifies pins, AST isolation, and epistemic flags across bundles."""
        rep = run_full_integration_audit(self.repo_root)
        self.assertTrue(rep["ast_holdout_isolation"]["all_isolated"])
        self.assertTrue(rep["codex_graph_builder_untouched"])
        self.assertTrue(rep["ace_base_runtime"]["demo_eval_perfect"])
        self.assertEqual(rep["scientific_status"], "NOT_ASSESSED")
        self.assertFalse(rep["oaie_established"])
        self.assertEqual(rep["phenomenal_consciousness"], "PHENOMENAL_CONSCIOUSNESS_UNKNOWN")


if __name__ == "__main__":
    unittest.main()
