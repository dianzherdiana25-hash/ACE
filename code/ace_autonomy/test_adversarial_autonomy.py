"""Comprehensive Fase 3 adversarial, durability, budget, escrow, and ACE integration tests.

Tests all 12 PR #67 remediations plus Red Team vectors RT-01..RT-13 without
@expectedFailure.
"""
from __future__ import annotations

import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from .core import Autonomy
from .errors import IntegrityError, PolicyError


def _cold_start_worker(workspace_str: str, root_str: str, goal: dict, out_q) -> None:
    with Autonomy(workspace_str, root_str) as engine:
        gid = engine.enqueue(goal)
        res = engine.run_one(gid)
        out_q.put((gid, res["status"] if res else None))


def _external_crash_worker(workspace_str: str, root_str: str, gid: str) -> None:
    def die_mid_external(op: str, payload: dict) -> dict:
        os._exit(23)

    with Autonomy(workspace_str, root_str, external_handler=die_mid_external) as engine:
        engine.run_one(gid)


class AdversarialAutonomyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "checkout"
        self.root.mkdir()
        (self.root / "ace.py").write_text("# test checkout\n", encoding="utf-8")
        (self.root / "README.md").write_text("trusted readme content\n", encoding="utf-8")
        (self.root / "code/ace_runtime").mkdir(parents=True)
        (self.root / "code/ace_runtime/engine.py").write_text("# fixed engine\n", encoding="utf-8")
        self.ws = Path(self.tmp.name) / "workspace"

    def test_cold_start_four_process_race(self) -> None:
        goal = {
            "schema": "ace.goal.v01",
            "name": "cold start race",
            "steps": [{"tool": "inspect_file", "path": "README.md"}],
        }
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        procs = [
            ctx.Process(target=_cold_start_worker, args=(str(self.ws), str(self.root), goal, q))
            for _ in range(4)
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=20)
        self.assertTrue(all(p.exitcode == 0 for p in procs))
        items = [q.get(timeout=5) for _ in range(4)]
        statuses = [st for _, st in items]
        self.assertEqual(statuses.count("SUCCEEDED"), 1)
        self.assertEqual(statuses.count(None), 3)

    def test_ancestor_symlink_and_fifo_rejected_without_blocking(self) -> None:
        # RT-03: symlinked workspace or source_root rejected immediately
        sym_ws = Path(self.tmp.name) / "sym_ws"
        real_target = Path(self.tmp.name) / "real_target"
        real_target.mkdir()
        sym_ws.symlink_to(real_target)
        with self.assertRaises(PolicyError):
            Autonomy(sym_ws, self.root)

        # RT-08: named pipe (FIFO) inside checkout rejected immediately via O_NONBLOCK + S_ISREG
        fifo_path = self.root / "blocking.fifo"
        os.mkfifo(fifo_path)
        with Autonomy(self.ws, self.root) as engine:
            gid = engine.enqueue({
                "schema": "ace.goal.v1",
                "name": "fifo probe",
                "steps": [{"tool": "inspect_file", "path": "blocking.fifo"}],
            })
            start = time.monotonic()
            rep = engine.run_one(gid)
            elapsed = time.monotonic() - start
            self.assertLess(elapsed, 2.0)
            self.assertEqual(rep["status"], "FAILED")
            self.assertIn("non-regular", rep["results"][0]["message"])

    def test_strict_type_validation_rejects_boolean_as_int(self) -> None:
        # RT-11 / RT-13: bool is a subclass of int in Python; must be rejected!
        with Autonomy(self.ws, self.root) as engine:
            with self.assertRaises(PolicyError):
                engine.enqueue({
                    "schema": "ace.goal.v1",
                    "name": "bool budget trick",
                    "budget": {"max_steps": True},
                    "steps": [{"tool": "inspect_file", "path": "README.md"}],
                })

    def test_wall_and_cpu_budget_exhaustion(self) -> None:
        with Autonomy(self.ws, self.root) as engine:
            gid_wall = engine.enqueue({
                "schema": "ace.goal.v1",
                "name": "tight wall budget",
                "budget": {"wall_seconds": 0.02, "max_steps": 2, "max_retries_per_step": 0},
                "steps": [
                    {"tool": "inspect_file", "path": "README.md"},
                    {"tool": "inspect_file", "path": "ace.py"},
                ],
            })
            orig = engine._dispatch

            def slow_dispatch(action):
                time.sleep(0.05)
                return orig(action)

            with patch.object(engine, "_dispatch", side_effect=slow_dispatch):
                rep = engine.run_one(gid_wall)
            self.assertEqual(rep["status"], "BUDGET_EXHAUSTED")
            self.assertIsNone(engine.run_one(gid_wall))

            gid_cpu = engine.enqueue({
                "schema": "ace.goal.v1",
                "name": "tight cpu budget",
                "budget": {"cpu_seconds": 0.01, "max_steps": 2, "max_retries_per_step": 0},
                "steps": [
                    {"tool": "inspect_file", "path": "README.md"},
                    {"tool": "inspect_file", "path": "ace.py"},
                ],
            })

            def burn_cpu(action):
                acc = 0
                for i in range(400_000):
                    acc ^= (i * 2654435761) & 0xFFFFFFFF
                assert acc >= 0
                return orig(action)

            with patch.object(engine, "_dispatch", side_effect=burn_cpu):
                rep_cpu = engine.run_one(gid_cpu)
            self.assertEqual(rep_cpu["status"], "BUDGET_EXHAUSTED")

    def test_external_action_crash_halts_uncertain_without_retry_and_reconciles(self) -> None:
        calls: list[str] = []

        def recorder(op: str, payload: dict) -> dict:
            calls.append(op)
            return {"receipt_id": "ext-rcpt-001", "conclusive": True}

        goal = {
            "schema": "ace.goal.v1",
            "name": "escrowed external call",
            "policy": {"authorized_tools": ["external_action", "inspect_file"]},
            "steps": [
                {"tool": "external_action", "operation": "publish_draft", "payload": {"ref": "b1"}},
                {"tool": "inspect_file", "path": "README.md"},
            ],
        }
        with Autonomy(self.ws, self.root, external_handler=recorder) as engine:
            gid = engine.enqueue(goal)

        # Spawn worker that dies with os._exit(23) AFTER escrow is committed as DISPATCHED
        ctx = multiprocessing.get_context("spawn")
        p = ctx.Process(target=_external_crash_worker, args=(str(self.ws), str(self.root), gid))
        p.start()
        p.join(timeout=20)
        self.assertEqual(p.exitcode, 23)

        # Reopen with live handler: MUST NOT retry external_action; MUST transition to HALT_UNCERTAIN!
        with Autonomy(self.ws, self.root, external_handler=recorder) as engine:
            rep = engine.run_one(gid)
            self.assertEqual(rep["status"], "HALT_UNCERTAIN")
            self.assertEqual(calls, [])
            # Subsequent run_one does nothing while halted
            self.assertIsNone(engine.run_one(gid))
            # Explicit operator reconciliation resumes step 2 cleanly
            rec = engine.reconcile_external(
                gid,
                0,
                resolution="CONFIRMED_COMPLETED",
                external_receipt_id="operator-verified-rcpt-99",
            )
            self.assertEqual(rec["status"], "RUNNING")
            final_rep = engine.run_one(gid)
            self.assertEqual(final_rep["status"], "SUCCEEDED")
            self.assertEqual(calls, [])

    def test_tail_rollback_and_db_swap_detected_by_external_anchor(self) -> None:
        anchor_file = Path(self.tmp.name) / "external_anchor" / "chain_head.json"
        with Autonomy(self.ws, self.root, anchor_path=anchor_file) as engine:
            gid = engine.enqueue({
                "schema": "ace.goal.v01",
                "name": "rollback target",
                "steps": [{"tool": "inspect_file", "path": "README.md"}],
            })
            # Snapshot valid DB at seq=1 before step 1 runs!
            snap_bytes = (self.ws / "goals.sqlite3").read_bytes()
            self.assertEqual(engine.run_one(gid)["status"], "SUCCEEDED")

        # RT-07: Restore valid older DB prefix (seq=1) while anchor is at seq=2!
        for suffix in ("-wal", "-shm"):
            wal = self.ws / f"goals.sqlite3{suffix}"
            if wal.exists():
                wal.unlink()
        (self.ws / "goals.sqlite3").write_bytes(snap_bytes)
        with self.assertRaises(IntegrityError):
            Autonomy(self.ws, self.root, anchor_path=anchor_file)

        # RT-01: Delete goals.sqlite3 completely so a fresh DB with new UUID is created
        (self.ws / "goals.sqlite3").unlink()
        with self.assertRaises(IntegrityError):
            Autonomy(self.ws, self.root, anchor_path=anchor_file)

    def test_integrity_error_never_swallowed_and_fake_tool_receipt_rejected(self) -> None:
        with Autonomy(self.ws, self.root) as engine:
            gid = engine.enqueue({
                "schema": "ace.goal.v01",
                "name": "spoofed receipt test",
                "steps": [{"tool": "inspect_file", "path": "README.md"}],
            })
            fake_evidence = {
                "tool": "inspect_file",
                "path": "README.md",
                "bytes": 999,
                "sha256": "f" * 64,
            }
            with patch.object(engine, "_dispatch", return_value=fake_evidence):
                with self.assertRaises(IntegrityError):
                    engine.run_one(gid)
            self.assertEqual(engine.report(gid)["status"], "QUEUED")

    def test_staged_for_review_and_abstain_and_planner(self) -> None:
        with Autonomy(self.ws, self.root) as engine:
            gid_stage = engine.enqueue({
                "schema": "ace.goal.v1",
                "name": "stage patch for review",
                "objective": {
                    "kind": "stage_candidate_for_review",
                    "inspect_paths": ["README.md"],
                    "candidates": [
                        {
                            "rel_path": "proposal_01.json",
                            "content": '{"hypothesis":"bounded"}',
                            "kind": "config_patch",
                        }
                    ],
                },
            })
            history = engine.run_until_stopped(gid_stage)
            self.assertEqual(history[-1]["status"], "STAGED_FOR_REVIEW")
            caps = engine.registry.list_capabilities()
            self.assertTrue(any(c["status"] == "STAGED_CANDIDATE_UNEXECUTED" for c in caps))

            gid_abs = engine.enqueue({
                "schema": "ace.goal.v1",
                "name": "abstain when unidentifiable",
                "objective": {
                    "kind": "abstain_insufficient_evidence",
                    "inspect_paths": ["README.md"],
                    "reason": "observational equivalence prevents disambiguating terminal flip",
                },
            })
            hist_abs = engine.run_until_stopped(gid_abs)
            self.assertEqual(hist_abs[-1]["status"], "ABSTAINED")


class RealFullACEAutonomyIntegrationTests(unittest.TestCase):
    def test_full_ace_runtime_task_lifecycle_and_cli_demo(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "autonomy_ws"
            # Generate deterministic parity task for real ACE Runtime (63 strings len 0..5 => 63 prefix-tree nodes)
            train = [
                [w, (w.count("a") % 2 == 0)]
                for n in range(0, 6)
                for w in [
                    "".join("b" if (mask >> j) & 1 else "a" for j in range(n))
                    for mask in range(1 << n)
                ]
            ]
            val = [
                [("a" * k) + ("b" * (6 + (k % 5))), (k % 2 == 0)]
                for k in range(1, 33)
            ]
            term = [
                [("ab" * (8 + k)) + ("a" if k % 2 else "bb"), (((8 + k) + (1 if k % 2 else 0)) % 2 == 0)]
                for k in range(1, 33)
            ]
            task_spec = {
                "name": "autonomy_even_a_task",
                "train": train,
                "validation": val,
            }
            with Autonomy(ws, repo_root) as engine:
                gid = engine.enqueue({
                    "schema": "ace.goal.v1",
                    "name": "full ace learning cycle",
                    "steps": [
                        {"tool": "verify_upstream_sources"},
                        {"tool": "ace_enqueue_task", "task": task_spec},
                        {"tool": "ace_run_tasks", "max_tasks": 2},
                        {"tool": "ace_status"},
                    ],
                })
                hist = engine.run_until_stopped(gid)
                self.assertEqual(hist[-1]["status"], "SUCCEEDED")
                enq_tid = hist[-1]["results"][1]["evidence"]["task_id"]

                gid_eval = engine.enqueue({
                    "schema": "ace.goal.v1",
                    "name": "predict and evaluate learned task",
                    "steps": [
                        {"tool": "ace_predict", "task_id": enq_tid, "inputs": ["aa", "aba", "bbbb"]},
                        {"tool": "ace_evaluate", "task_id": enq_tid, "examples": term},
                        {"tool": "ace_report", "task_id": enq_tid},
                        {"tool": "run_trusted_suite", "suite": "ace_runtime.test_cli"},
                    ],
                })
                hist_eval = engine.run_until_stopped(gid_eval)
                self.assertEqual(hist_eval[-1]["status"], "SUCCEEDED")
                self.assertEqual(hist_eval[-1]["results"][0]["evidence"]["predictions"], [True, True, True])
                self.assertEqual(hist_eval[-1]["results"][1]["evidence"]["correct"], 32)

            # Verify CLI launcher autonomy.py demo works end-to-end
            cli_ws = Path(tmp) / "cli_ws"
            proc = subprocess.run(
                [sys.executable, str(repo_root / "autonomy.py"), "--workspace", str(cli_ws), "demo"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            demo_out = json.loads(proc.stdout)
            self.assertEqual(demo_out["final_report"]["status"], "SUCCEEDED")
            self.assertGreaterEqual(demo_out["status"]["capabilities_registered"], 2)


if __name__ == "__main__":
    unittest.main()
