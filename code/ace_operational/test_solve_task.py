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


if __name__ == "__main__":
    unittest.main()
