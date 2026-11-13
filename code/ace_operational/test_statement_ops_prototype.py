"""Tests for the discovery v-next statement-motion
prototype (sandbox). Run from the repo root:
PYTHONPATH=code python3 code/ace_operational/
test_statement_ops_prototype.py
"""
import unittest

from ace_operational.statement_ops_prototype import (
    PRICING_ADAPTER, admitted_variants, apply_motion,
    augmented_variants, build_order_task_sandbox,
    discover_motion_keys, enumerate_motion_variants,
    motion_key_fixes, motion_variants, solve_with_variants,
    solved_by, substrate_variants)


class TestMotionEnumeration(unittest.TestCase):
    def setUp(self):
        self.task = build_order_task_sandbox(70000)
        self.assertIsNotNone(self.task)

    def test_repair_motion_is_enumerated(self):
        # The inverse of the constructed defect — move
        # the Add AugAssign to just before the Return —
        # must be among the enumerated motions, and its
        # text must behave identically to the reference
        # on the full case grid.
        variants = dict()
        for key, text in enumerate_motion_variants(
                self.task["buggy_code"]):
            variants.setdefault(key, text)
        repair_key = ("move_stmt",
                      ("augassign", "t", "Add", "t"),
                      ("return",))
        self.assertIn(repair_key, variants)
        repaired = variants[repair_key]
        cases = [tuple(c) for c in
                 self.task["shown_cases"]] + \
            [tuple(c) for c in self.task["holdout_cases"]]
        passed = PRICING_ADAPTER.passes(
            repaired, cases,
            self.task["shown_truth"] +
            self.task["holdout_truth"])
        self.assertEqual(passed, len(cases))

    def test_no_noop_and_change_only(self):
        code = self.task["buggy_code"]
        for _, text in enumerate_motion_variants(code):
            self.assertNotEqual(text, code)

    def test_use_before_def_motion_is_filtered(self):
        # Moving the opening assignment below a use of
        # its target would put a use before the only
        # definition: never enumerated.
        code = ("def total(subtotal, member):\n"
                "    t = subtotal\n"
                "    t += t * 12 // 100\n"
                "    return t\n")
        for key, _ in enumerate_motion_variants(code):
            self.assertNotEqual(
                key[1], ("assign", "t", "subtotal"))

    def test_motion_never_lands_after_return(self):
        for _, text in enumerate_motion_variants(
                self.task["buggy_code"]):
            lines = [ln.strip() for ln in
                     text.splitlines() if ln.strip()]
            self.assertTrue(lines[-1].startswith("return"))

    def test_keys_are_deterministic(self):
        first = [k for k, _ in enumerate_motion_variants(
            self.task["buggy_code"])]
        second = [k for k, _ in enumerate_motion_variants(
            self.task["buggy_code"])]
        self.assertEqual(first, second)


class TestApplyMotion(unittest.TestCase):
    def test_round_trip_on_fresh_program(self):
        task = build_order_task_sandbox(70001)
        self.assertIsNotNone(task)
        variants = enumerate_motion_variants(
            task["buggy_code"])
        self.assertTrue(variants)
        for key, text in variants:
            self.assertEqual(apply_motion(
                task["buggy_code"], key), text)

    def test_unknown_key_returns_none(self):
        task = build_order_task_sandbox(70001)
        bogus = ("move_stmt", ("augassign", "nope",
                                "Add", "nope"), ("end",))
        self.assertIsNone(apply_motion(
            task["buggy_code"], bogus))


class TestSolverArms(unittest.TestCase):
    def test_augmented_solves_a_discriminating_task(self):
        # Find (deterministically) a sandbox task whose
        # shown set discriminates the defect and whose
        # substrate arm fails; the motion arm must
        # solve it on holdout.
        found = None
        for seed in range(70000, 70060):
            task = build_order_task_sandbox(seed)
            if task is None:
                continue
            budget = PRICING_ADAPTER.make_budget(task)
            if budget.score(task["buggy_code"]) >= \
                    len(task["shown_cases"]):
                continue
            if solved_by(task, PRICING_ADAPTER,
                         substrate_variants):
                continue
            found = task
            break
        self.assertIsNotNone(found)
        self.assertTrue(solved_by(found, PRICING_ADAPTER,
                                  augmented_variants))

    def test_substrate_variants_are_frozen_bound(self):
        # The baseline provider must be exactly the
        # frozen adapter's (substrate v1 digest in the
        # catalog id is the freeze's identity).
        self.assertTrue(PRICING_ADAPTER
                        .baseline_catalog_id()
                        .endswith("658b9022681bcb9e658b7b3f1"
                                  "c85fd3bc8e106718dca8b5ff"
                                  "1fd6b8cffd6bd21"))


class TestDiscoveryPrototype(unittest.TestCase):
    def test_admission_finds_the_repair_key(self):
        pool = []
        for seed in range(70000, 70020):
            task = build_order_task_sandbox(seed)
            if task is not None:
                pool.append(task)
        self.assertGreaterEqual(len(pool), 8)
        admitted = discover_motion_keys(
            pool[:8], PRICING_ADAPTER)
        repair_key = ("move_stmt",
                      ("augassign", "t", "Add", "t"),
                      ("return",))
        self.assertIn(repair_key, admitted)
        # The admitted key re-locates by fingerprint on
        # a fresh program (transfer mechanics work).
        fresh = build_order_task_sandbox(70050)
        self.assertIsNotNone(fresh)
        moved = admitted_variants(admitted)(
            fresh["buggy_code"])
        self.assertGreater(len(moved), len(
            substrate_variants(fresh["buggy_code"])))


if __name__ == "__main__":
    unittest.main()
