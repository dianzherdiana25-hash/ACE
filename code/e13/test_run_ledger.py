"""Exercise checkpoint recovery without touching confirmatory fixtures."""

import sqlite3
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from .evaluator.run_ledger import Arm, CandidateFailure, RunPlan, run_arms
from .evaluator.selection_budget import evaluate_arm
from .evaluator.transfer_bank import transfer_bank


class RunLedgerTests(unittest.TestCase):
    def plan(self):
        arms = tuple(Arm(family, "related", family, "fixture", 0, policy)
                     for family in ("S", "G") for policy in ("c_extend", "beam"))
        return RunPlan("1" * 64, "2" * 64, "3" * 64, "4" * 64, 131510, 8, arms)

    def test_public_worker_run_resumes_after_interrupt_without_repeating_committed_arms(self):
        plan = self.plan()
        fixtures = {e.family: e for e in transfer_bank() if e.regime == "related"}
        completed = []

        def evaluate(arm):
            row = evaluate_arm(fixtures[arm.family], arm.policy)
            completed.append(arm)
            return {"status": "scored", "correct": sum(s["correct"] for s in row["scores"].values()),
                    "total": sum(s["total"] for s in row["scores"].values()),
                    "ast_sha256": row["ast_sha256"]}

        def interrupt(arm):
            if completed:
                raise KeyboardInterrupt
            return evaluate(arm)

        with TemporaryDirectory() as directory:
            path = Path(directory) / "evaluator.sqlite"
            with self.assertRaises(KeyboardInterrupt):
                run_arms(path, plan, interrupt)
            self.assertEqual(len(completed), 1)
            resumed = run_arms(path, plan, evaluate)
            self.assertEqual(len(completed), 4)
            self.assertEqual(len(set(completed)), 4)
            self.assertEqual(resumed, run_arms(path, plan, evaluate))
            self.assertEqual(len(completed), 4)
            with sqlite3.connect(path) as database:
                self.assertEqual(database.execute("SELECT kind FROM interruption").fetchall(),
                                 [("KeyboardInterrupt",)])

    def test_plan_drift_is_rejected_and_attributed_failure_retains_denominator(self):
        plan = self.plan()

        def fail(_arm):
            raise CandidateFailure("invalid_ast")

        with TemporaryDirectory() as directory:
            path = Path(directory) / "evaluator.sqlite"
            rows = run_arms(path, plan, fail)
            self.assertTrue(all(r["correct"] == 0 and r["total"] == 8
                                and r["status"] == "candidate_failure" for r in rows))
            with self.assertRaisesRegex(ValueError, "does not match"):
                run_arms(path, replace(plan, bank_sha256="0" * 64), fail)

    def test_unclassified_worker_failure_holds_the_run_and_concurrent_open_is_rejected(self):
        plan = self.plan()

        def concurrent(_arm):
            return run_arms(path, plan, concurrent)

        with TemporaryDirectory() as directory:
            path = Path(directory) / "evaluator.sqlite"
            with self.assertRaisesRegex(RuntimeError, "already in use"):
                run_arms(path, plan, concurrent)
            with sqlite3.connect(path) as database:
                self.assertEqual(database.execute("SELECT count(*) FROM result").fetchone(), (0,))
                self.assertEqual(database.execute("SELECT kind FROM interruption").fetchall(),
                                 [("RuntimeError",)])
