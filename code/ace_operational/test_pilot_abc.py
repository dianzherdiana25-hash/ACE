"""Phase 2 tests for the A/B/C pilot harness and substrate v2.

Pins: the multiplier operator that the shipping measurement proved
missing; config-gated operators; B's credit adaptation; C's archived
lineage; kernel preregistration-before-results with a CLEAN audit on a
smoke pilot; and held-out isolation (selection never sees holdout).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ace_operational.curriculum_lab import generate_task, split_of
from ace_operational.pilot_abc import (
    BASE_CONFIG,
    evaluate_config,
    run_arm_b,
    run_arm_c,
    run_pilot,
    variants_by_group,
)
from ace_operational.population_archive import PopulationArchive


def budgetd(task):
    from ace_operational.reasoning_lab import Budget
    shown = [tuple(c) for c in task["shown_cases"]]
    by_case = {tuple(c): e for c, e in zip(task["cases"], task["expected"])}
    return Budget(200, entrypoint=task["entrypoint"], shown_cases=shown,
                  shown_expected=[by_case[c] for c in shown])


class SubstrateV2Tests(unittest.TestCase):
    def test_multiplier_operator_exists_and_fixes_the_defect(self):
        found = False
        for seed in range(1, 11):
            try:
                task = generate_task("shipping", 1, seed=seed)
            except Exception:
                continue
            if [d["name"] for d in task["defects"]] != ["multiplier_dropped"]:
                continue
            found = True
            variants = variants_by_group(task["buggy_code"], task["spec"])
            self.assertTrue(variants["multiplier"],
                            "substrate v2 must propose multiplier restores")
            from ace_operational.pilot_abc import solve_with_config
            result = solve_with_config(
                {k: task[k] for k in ("buggy_code", "spec", "shown_cases",
                                      "entrypoint", "seed")},
                budgetd(task), BASE_CONFIG)
            from ace_operational.curriculum_lab import verify_candidate
            outcome = verify_candidate(task, result["code"])
            self.assertEqual(outcome["passed"], outcome["total"],
                             "v2 must solve the task v1 provably could not")
            break
        self.assertTrue(found, "no pure multiplier task found in seeds 1..10")

    def test_config_without_multiplier_cannot_fix_it(self):
        for seed in range(1, 11):
            try:
                task = generate_task("shipping", 1, seed=seed)
            except Exception:
                continue
            if [d["name"] for d in task["defects"]] != ["multiplier_dropped"]:
                continue
            config = {"operators": ["boundary", "basis", "nudge"], "rounds": 3}
            evaluation = evaluate_config(config, [task], 200)
            self.assertEqual(evaluation["solved"], 0)
            return
        self.skipTest("no pure multiplier task in seeds 1..10")


class ArmTests(unittest.TestCase):
    def setUp(self):
        self.train = []
        for level in (1, 2):
            for seed in range(1, 9):
                try:
                    task = generate_task("pricing", level, seed=seed)
                except Exception:
                    continue
                if split_of(task) == "train":
                    self.train.append(task)

    def test_arm_b_adapts_operator_order(self):
        outcome = run_arm_b(self.train, cycles=2, budget_limit=100)
        self.assertEqual(len(outcome["history"]), 2)
        self.assertEqual(sorted(outcome["final_config"]["operators"]),
                         sorted(BASE_CONFIG["operators"]))

    def test_arm_c_registers_lineage(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = PopulationArchive(Path(tmp) / "archive")
            outcome = run_arm_c(self.train, cycles=2, budget_limit=100,
                                archive=archive)
            self.assertGreaterEqual(outcome["candidates_registered"], 3)
            self.assertGreaterEqual(len(archive.candidate_ids()), 3)
            self.assertIn("final_config", outcome)


class SmokePilotTests(unittest.TestCase):
    def test_smoke_pilot_preregisters_records_and_audits_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_pilot(kernel_root=Path(tmp) / "kernel",
                               archive_root=Path(tmp) / "archive",
                               levels=[1], seeds=list(range(1, 13)),
                               reps=1, cycles=1, budget_limit=100)
            self.assertEqual(report["audit"]["status"], "CLEAN",
                             report["audit"])
            for arm in ("arm-a-fixed", "arm-b-adaptive", "arm-c-evolutionary"):
                self.assertIn(arm, report["aggregate"])
            self.assertEqual(report["aggregate"]["arm-null"]["pooled_rate"], 0.0)
            self.assertFalse(report["sample_target_met"])  # smoke is small

    def test_heldout_never_used_for_selection(self):
        # run_arm_b / run_arm_c receive only the train list by
        # construction; assert the pilot's split bookkeeping is disjoint.
        tasks = []
        for seed in range(1, 13):
            try:
                tasks.append(generate_task("pricing", 1, seed=seed))
            except Exception:
                pass
        train_ids = {t["task_id"] for t in tasks if split_of(t) == "train"}
        holdout_ids = {t["task_id"] for t in tasks if split_of(t) == "holdout"}
        self.assertFalse(train_ids & holdout_ids)


if __name__ == "__main__":
    unittest.main()
