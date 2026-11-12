"""OMEGA-10 tests for the Environment and Curriculum Co-Evolution lab.

The test list follows the OMEGA-10 line of the execution programme:
trivial-task gaming, invalid problem, reference solution leakage,
generated benchmark inflation, task-family transfer — plus split
integrity and curriculum scheduling.
"""
from __future__ import annotations

import unittest

from ace_operational.curriculum_lab import (
    CurriculumScheduler,
    InvalidTaskError,
    LeakageError,
    SplitIntegrityError,
    _run_cases,
    assert_split_integrity,
    audit_benchmark,
    check_identifiability,
    generate_task,
    public_bundle,
    split_of,
    validate_task,
    verify_candidate,
)


def generate_set(family="pricing", levels=(1, 2, 3, 4), seeds=range(8)):
    tasks = []
    for level in levels:
        for seed in seeds:
            try:
                tasks.append(generate_task(family, level, seed=seed))
            except InvalidTaskError:
                pass
    return tasks


class GenerationValidityTests(unittest.TestCase):
    def test_generated_tasks_are_valid_and_honest(self):
        for family in ("pricing", "shipping"):
            tasks = generate_set(family)
            self.assertTrue(tasks, f"no tasks generated for {family}")
            for task in tasks:
                validate_task(task)  # must not raise
                buggy = verify_candidate(task, task["buggy_code"])
                self.assertLess(buggy["passed"], buggy["total"])
                reference = verify_candidate(task, task["reference_code"])
                self.assertEqual(reference["passed"], reference["total"])

    def test_invalid_problem_is_rejected(self):
        task = generate_task("pricing", 1, seed=3)
        task["buggy_code"] = task["reference_code"]  # "buggy" that is solved
        with self.assertRaises(InvalidTaskError):
            validate_task(task)

    def test_trivial_task_gaming_is_rejected(self):
        # A gaming generator emits defect-free code labeled as a task.
        task = generate_task("pricing", 1, seed=5)
        gamed = dict(task, buggy_code=task["reference_code"], defects=[])
        with self.assertRaises(InvalidTaskError):
            validate_task(gamed)

    def test_difficulty_mislabel_is_rejected(self):
        task = generate_task("pricing", 1, seed=2)
        task["level"] = 4  # inflate the label, keep the easy defects
        with self.assertRaises(InvalidTaskError):
            validate_task(task)


class IdentifiabilityTests(unittest.TestCase):
    """The Phase 2 amendment: shown sets must defeat every partial fix."""

    def test_all_generated_tasks_are_identifiable(self):
        for family in ("pricing", "shipping"):
            for task in generate_set(family):
                self.assertTrue(check_identifiability(task), task["task_id"])

    def test_residual_shape_tasks_now_defeat_the_trap(self):
        found = 0
        for seed in range(1, 31):
            try:
                task = generate_task("pricing", 3, seed=seed)
            except InvalidTaskError:
                continue
            if sorted(d["name"] for d in task["defects"]) != [
                    "member_basis", "tax_basis"]:
                continue
            found += 1
            self.assertTrue(check_identifiability(task))
        self.assertGreater(found, 0)

    def test_weak_shown_set_is_rejected_by_the_validator(self):
        for seed in range(1, 31):
            try:
                task = generate_task("pricing", 3, seed=seed)
            except InvalidTaskError:
                continue
            if sorted(d["name"] for d in task["defects"]) != [
                    "member_basis", "tax_basis"]:
                continue
            buggy_out = _run_cases(task["buggy_code"], task["entrypoint"],
                                   [tuple(c) for c in task["cases"]])
            exposing = [c for c, b, e in zip(task["cases"], buggy_out,
                                             task["expected"]) if b != e]
            weakened = dict(task, shown_cases=[list(c) for c in exposing[:1]])
            with self.assertRaises(InvalidTaskError):
                validate_task(weakened)
            return
        self.skipTest("no residual-shape task in seeds 1..30")


class GridFamilyTests(unittest.TestCase):
    """The third family (Phase 2, director agenda): grid navigation."""

    def test_grid_tasks_generate_valid_and_identifiable(self):
        made = 0
        for level in (1, 2, 3, 4):
            for seed in range(1, 13):
                try:
                    task = generate_task("grid", level, seed=seed)
                except InvalidTaskError:
                    continue  # honest rejection is a valid outcome
                made += 1
                validate_task(task)
                self.assertTrue(check_identifiability(task))
                self.assertEqual(task["entrypoint"], "navigate")
        self.assertGreater(made, 30)

    def test_grid_reference_semantics(self):
        task = generate_task("grid", 1, seed=1)
        grid = ((".....", ".###.", ".#.#.", ".###.", "....."),)
        cases = [(grid[0], 0, 0, 2, 2),   # walled-in centre: unreachable
                 (grid[0], 2, 0, 2, 0),   # start == goal
                 (grid[0], 0, 0, 0, 4)]   # straight corridor along row 0
        self.assertEqual(
            _run_cases(task["reference_code"], "navigate", cases),
            [-1, 0, 4])


class LeakageTests(unittest.TestCase):
    def test_public_bundle_is_clean(self):
        for task in generate_set("pricing", levels=(1, 4), seeds=range(3)):
            bundle = public_bundle(task)
            self.assertNotIn("reference_code", bundle)
            self.assertNotIn("defects", bundle)

    def test_reference_solution_leakage_is_detected(self):
        task = generate_task("pricing", 1, seed=1)
        poisoned = dict(task, spec=task["spec"] + " " + task["reference_code"])
        with self.assertRaises(LeakageError):
            public_bundle(poisoned)

    def test_holdout_answers_are_not_in_the_bundle(self):
        task = generate_task("shipping", 2, seed=4)
        bundle = public_bundle(task)
        shown = {tuple(c) for c in task["shown_cases"]}
        self.assertEqual(len(bundle["shown_cases"]), len(task["shown_cases"]))
        self.assertGreaterEqual(len(shown), 1)
        self.assertLess(len(shown), len(task["cases"]))


class SplitAndAuditTests(unittest.TestCase):
    def test_split_is_deterministic(self):
        task = generate_task("pricing", 2, seed=6)
        self.assertEqual(split_of(task), split_of(dict(task)))

    def test_renamed_duplicate_shares_the_split(self):
        task = generate_task("pricing", 1, seed=7)
        renamed = dict(task)
        renamed["buggy_code"] = task["buggy_code"].replace("subtotal", "jumlah")
        renamed["reference_code"] = task["reference_code"].replace("subtotal", "jumlah")
        self.assertEqual(split_of(task), split_of(renamed))
        assert_split_integrity([task, renamed])  # same split: no straddle

    def test_straddling_cluster_is_detected(self):
        task = generate_task("pricing", 1, seed=7)
        tasks = [task]
        # Force the integrity check to see the same normalized form under
        # both splits by pairing the task with a same-form twin whose
        # digest lands in the other split: emulate by direct construction.
        twin = dict(task)
        twin["buggy_code"] = task["buggy_code"] + "\n# padding\n"
        # padding changes the AST? no: comments are not in the AST, so the
        # normalized form is identical while split_of uses that same form —
        # a straddle is then impossible by construction; the check exists
        # for tasks whose split was assigned externally. Simulate that:
        import ace_operational.curriculum_lab as lab
        original = lab.split_of
        try:
            lab.split_of = lambda t: "train" if t is task else "holdout"
            with self.assertRaises(SplitIntegrityError):
                lab.assert_split_integrity([task, twin])
        finally:
            lab.split_of = original
        self.assertTrue(tasks)

    def test_benchmark_audit_flags_inflation(self):
        healthy = generate_set("pricing", levels=(1, 2), seeds=range(4))
        report = audit_benchmark(healthy)
        self.assertFalse(report["inflated"], report)
        inflated = []
        for task in healthy[:4]:
            fake = dict(task, task_id=f"fake-{task['task_id']}",
                        buggy_code=task["reference_code"])
            inflated.append(fake)
        report = audit_benchmark(inflated)
        self.assertTrue(report["inflated"])

    def test_benchmark_audit_flags_mislabels(self):
        task = generate_task("pricing", 1, seed=9)
        bad = dict(task, level=3)
        report = audit_benchmark([bad])
        self.assertTrue(any("labeled L3" in p for p in report["problems"]))


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.tasks = generate_set("pricing") + generate_set("shipping")
        self.scheduler = CurriculumScheduler(batch_size=6)

    def test_frontier_stays_until_mastery(self):
        self.assertEqual(self.scheduler.frontier("pricing"), 1)
        self.scheduler.record_result("pricing", 1, 0.4)
        self.assertEqual(self.scheduler.frontier("pricing"), 1)
        self.scheduler.record_result("pricing", 1, 0.9)
        self.assertEqual(self.scheduler.frontier("pricing"), 2)

    def test_train_mode_never_serves_holdout(self):
        batch = self.scheduler.next_batch(self.tasks, family="pricing",
                                          mode="train")
        self.assertTrue(batch["task_ids"])
        self.assertTrue(all(s == "train" for s in batch["splits"]))
        eval_batch = self.scheduler.next_batch(self.tasks, family="pricing",
                                               mode="eval")
        self.assertLessEqual(len(eval_batch["task_ids"]), 6)

    def test_batch_is_frontier_heavy_and_bounded(self):
        self.scheduler.record_result("pricing", 1, 0.95)
        batch = self.scheduler.next_batch(self.tasks, family="pricing")
        self.assertLessEqual(len(batch["task_ids"]), 6)
        self.assertIn(2, batch["levels"])  # the new frontier is served

    def test_task_family_transfer_probe(self):
        batch = self.scheduler.next_batch(
            self.tasks, family="pricing", transfer_family="shipping")
        by_id = {t["task_id"]: t for t in self.tasks}
        families = {by_id[tid]["family"] for tid in batch["task_ids"]}
        self.assertEqual(families, {"pricing", "shipping"})


if __name__ == "__main__":
    unittest.main()
