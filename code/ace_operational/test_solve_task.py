"""A/B/C v3 build step 1 (PR #147): the lifted
`solve_task` solver — uncapped behaviour solves through
the adapter like the old nested loop, and the
score-call budget actually binds. Trace-hook tests
(midday track (a)): the optional `trace` keyword
records each improving step's provenance without
changing the returned code."""
import unittest

from ace_operational.grid_adapter import GRID_ADAPTER
from ace_operational.grid_generalization import build_universe
from ace_operational.operator_discovery import (
    discover_for_task, solve_task)
from ace_operational.pricing_adapter import PricingAdapter, \
    build_pricing_task


class TestSolveTask(unittest.TestCase):

    def setUp(self):
        self.adapter = PricingAdapter()
        self.task = build_pricing_task(seed=42, level=1)

    def test_uncapped_solves_single_defect(self):
        solved = solve_task(self.task, self.adapter)
        cases = [tuple(c) for c in self.task["holdout_cases"]]
        passed = self.adapter.passes(
            solved, cases, self.task["holdout_truth"])
        self.assertEqual(passed, len(cases))

    def test_budget_cap_binds(self):
        capped = solve_task(self.task, self.adapter,
                            max_score_calls=1)
        self.assertIsInstance(capped, str)
        # One scoring call = only the start was scored;
        # nothing could be selected over it.
        self.assertEqual(capped, self.task["buggy_code"])

    def test_zero_cap_returns_start(self):
        out = solve_task(self.task, self.adapter,
                         max_score_calls=0)
        self.assertEqual(out, self.task["buggy_code"])

    def test_trace_records_key_provenance(self):
        # First v4-protocol pool task whose discovered key
        # is the improving step: the trace must carry
        # ("key", key) and the traced code must equal the
        # untraced code (behaviour-identical).
        universe = build_universe()
        tasks = universe["tasks"]
        new_only = [t for t in tasks
                    if t["subset"] == "new_only"]
        singles = [t for t in new_only
                   if len(t["defects"]) == 1]
        pool, per_class = [], {}
        for task in singles:
            cls = task["defects"][0]
            per_class[cls] = per_class.get(cls, 0) + 1
            if per_class[cls] <= 3:
                pool.append(task)
        found = None
        for task in pool:
            keys = discover_for_task(task, adapter=GRID_ADAPTER)
            if not keys:
                continue
            trace: list = []
            traced = solve_task(task, GRID_ADAPTER, (keys[0],),
                                (), trace=trace)
            plain = solve_task(task, GRID_ADAPTER, (keys[0],), ())
            if traced == plain and any(
                    kind == "key" for kind, _ in trace):
                found = (task, keys[0], trace, traced)
                break
        self.assertIsNotNone(
            found, "no pool task exercised key provenance")
        task, key, trace, traced = found
        self.assertEqual(trace[0], ("key", key))
        cases = [tuple(c) for c in task["holdout_cases"]]
        passed = GRID_ADAPTER.passes(
            traced, cases, task["holdout_truth"])
        self.assertEqual(passed, len(cases))

    def test_trace_none_is_behaviour_identical(self):
        # The hook's off-state: same code with and
        # without a trace list on a task the key fixes.
        universe = build_universe()
        tasks = universe["tasks"]
        new_only = [t for t in tasks
                    if t["subset"] == "new_only"]
        singles = [t for t in new_only
                   if len(t["defects"]) == 1]
        pool, per_class = [], {}
        for task in singles:
            cls = task["defects"][0]
            per_class[cls] = per_class.get(cls, 0) + 1
            if per_class[cls] <= 3:
                pool.append(task)
        task = pool[0]
        keys = discover_for_task(task, adapter=GRID_ADAPTER)
        self.assertTrue(keys)
        trace: list = []
        traced = solve_task(task, GRID_ADAPTER, (keys[0],),
                            (), trace=trace)
        plain = solve_task(task, GRID_ADAPTER, (keys[0],), ())
        self.assertEqual(traced, plain)
        self.assertGreaterEqual(len(trace), 1)

    def test_guard_rescues_base_when_enriched_fills_frontier(self):
        # Synthetic task where 4 ENRICHED extra_keys score 2 (filling
        # the 4-slot frontier and raising best_score to 2), while the
        # BASE variant scores 1 and leads to the score-3 solution in
        # round 2. Without guard=True, BASE is pruned and the solver
        # stalls at score 2; with guard=True, BASE is preserved and
        # solves 3/3.
        start = (
            "def f(x):\n"
            "    a = 10\n"
            "    b = 20\n"
            "    c = 30\n"
            "    d = 40\n"
            "    return x\n"
        )
        base_step = start.replace("return x", "return x + 1")
        base_win = start.replace("return x", "return x + 2")

        from ace_operational.operator_discovery import enumerate_variants
        int_keys = [
            k for k, _ in enumerate_variants(start)
            if k[0] == "int_constant"
        ][:4]
        self.assertEqual(len(int_keys), 4)

        class _Budget:
            def score(self, code):
                if "return x + 2" in code:
                    return 3
                if "return x + 1" in code:
                    return 1
                if code == start:
                    return 0
                return 2  # ENRICHED dead-end distractors

        class _Adapter:
            family_id = "synthetic_lg_test"

            def make_budget(self, task):
                return _Budget()

            def passes(self, code, cases, truth):
                return 3 if "return x + 2" in code else 0

            def baseline_variants(self, code):
                if code == start:
                    return [base_step]
                if code == base_step:
                    return [base_win]
                return []

        task = {
            "buggy_code": start,
            "shown_cases": [1, 2, 3],
            "shown_truth": [3, 4, 5],
            "holdout_cases": [1, 2, 3],
            "holdout_truth": [3, 4, 5],
            "defects": ["synthetic"],
            "task_id": "lg-test-1",
        }
        adapter = _Adapter()

        # Unguarded stalls on ENRICHED dead-ends (score 2 < 3)
        unguarded = solve_task(task, adapter, tuple(int_keys), (), guard=False)
        self.assertNotEqual(unguarded, base_win)
        self.assertEqual(
            solve_task(task, adapter, tuple(int_keys), ()),
            unguarded,
        )

        # Guarded triggers once in round 1 and recovers base_win
        stats: dict[str, int] = {}
        guarded = solve_task(
            task, adapter, tuple(int_keys), (),
            guard=True, guard_stats=stats,
        )
        self.assertEqual(guarded, base_win)
        self.assertEqual(stats.get("triggers"), 1)


if __name__ == "__main__":
    unittest.main()
