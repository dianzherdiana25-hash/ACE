"""Equivalence tests for parse-once / compile-once (PR stacked on #178).

The candidate must be search-set preserving: identical candidate
sets in identical order, identical scores, identical solve outputs.
The baseline reference lives in `parse_once_bench` (unshared parse
path + plain Budget + the pre-candidate solve loop).
"""
from __future__ import annotations

import unittest

from ace_operational import pilot_abc
from ace_operational.curriculum_lab import generate_task
from ace_operational.parse_once_bench import (
    solve_reference,
    variants_unshared,
    _plain_budget,
    _public,
)
from ace_operational.profiling_observer import (
    Collector,
    PhaseAggregator,
    instrumented_solver,
)
from ace_operational.reasoning_lab import Budget
import tempfile
from pathlib import Path


def _corpus(levels=(1, 2, 3), seeds=range(1, 10)):
    tasks = []
    for family in ("pricing", "shipping"):
        for level in levels:
            for seed in seeds:
                try:
                    tasks.append(generate_task(family, level, seed=seed))
                except Exception:
                    continue
    return tasks


class VariantsEquivalenceTests(unittest.TestCase):
    def test_shared_tree_variants_equal_unshared(self):
        tasks = _corpus()
        self.assertTrue(tasks)
        checked = 0
        for task in tasks:
            for code in (task["buggy_code"], task["reference_code"]):
                self.assertEqual(
                    variants_unshared(code, task["spec"]),
                    pilot_abc.variants_by_group(code, task["spec"]),
                    "shared parse changed the candidate set or order")
                checked += 1
        self.assertGreater(checked, 20)

    def test_group_functions_do_not_mutate_the_shared_tree(self):
        import ast
        task = _corpus(seeds=range(1, 4))[0]
        tree = ast.parse(task["buggy_code"])
        first = {name: fn(task["buggy_code"], task["spec"], tree=tree)
                 for name, fn in pilot_abc.GROUP_FN.items()}
        second = {name: fn(task["buggy_code"], task["spec"], tree=tree)
                  for name, fn in pilot_abc.GROUP_FN.items()}
        self.assertEqual(first, second,
                         "a group function mutated the shared tree")


class CachingBudgetTests(unittest.TestCase):
    def test_scores_identical_to_plain_budget(self):
        for task in _corpus(seeds=range(1, 6)):
            shown = [tuple(c) for c in task["shown_cases"]]
            by_case = {tuple(c): e for c, e in
                       zip(task["cases"], task["expected"])}
            kw = dict(entrypoint=task["entrypoint"], shown_cases=shown,
                      shown_expected=[by_case[c] for c in shown])
            plain = Budget(200, **kw)
            caching = pilot_abc.CachingBudget(200, **kw)
            codes = [task["buggy_code"], task["reference_code"],
                     "def broken(:\n", task["buggy_code"]]
            groups = pilot_abc.variants_by_group(task["buggy_code"],
                                                 task["spec"])
            for group in groups.values():
                codes.extend(group[:3])
            for code in codes:
                self.assertEqual(plain.score(code), caching.score(code))
            self.assertEqual(plain.used, caching.used)
            # compile-once really happened: exactly one code object
            # per distinct compilable source.
            compilable = set()
            for c in set(codes):
                try:
                    compile(c, "<cand>", "exec")
                    compilable.add(c)
                except Exception:
                    pass
            self.assertEqual(len(caching._compiled), len(compilable))


class SolveEquivalenceTests(unittest.TestCase):
    def test_candidate_solve_equals_reference_solve(self):
        tasks = _corpus(levels=(1, 2, 3, 4), seeds=range(1, 13))
        self.assertGreater(len(tasks), 30)
        for task in tasks:
            public = _public(task)
            expected = solve_reference(
                public, _plain_budget(task, 200), pilot_abc.BASE_CONFIG)
            got = pilot_abc.solve_with_config(
                public, pilot_abc._budget_for(task, 200),
                pilot_abc.BASE_CONFIG)
            self.assertEqual(expected, got,
                             f"solve diverged on {task['task_id']}")

    def test_evaluate_config_totals_match_reference(self):
        tasks = _corpus(levels=(1, 2), seeds=range(1, 7))
        got = pilot_abc.evaluate_config(pilot_abc.BASE_CONFIG, tasks, 200)
        solved = 0
        for task in tasks:
            result = solve_reference(
                _public(task), _plain_budget(task, 200),
                pilot_abc.BASE_CONFIG)
            from ace_operational.curriculum_lab import verify_candidate
            outcome = verify_candidate(task, result["code"])
            solved += 1 if outcome["passed"] == outcome["total"] else 0
        self.assertEqual(got["solved"], solved)
        self.assertEqual(got["total"], len(tasks))


class ProfilingCompatibilityTests(unittest.TestCase):
    def test_instrumented_solver_still_wraps_candidate(self):
        task = _corpus(seeds=range(1, 4))[0]
        with tempfile.TemporaryDirectory() as td:
            collector = Collector(Path(td), "run-x")
            agg = PhaseAggregator(collector, "job-x")
            from ace_operational.profiling_observer import ProfilingBudget
            shown = [tuple(c) for c in task["shown_cases"]]
            by_case = {tuple(c): e for c, e in
                       zip(task["cases"], task["expected"])}
            budget = ProfilingBudget(
                200, entrypoint=task["entrypoint"], shown_cases=shown,
                shown_expected=[by_case[c] for c in shown],
                aggregator=agg)
            with instrumented_solver(agg):
                result = pilot_abc.solve_with_config(
                    _public(task), budget, pilot_abc.BASE_CONFIG)
            self.assertIn("transform_serialize", agg.totals)
            self.assertIn("enumeration", agg.totals)
            plain = solve_reference(
                _public(task), _plain_budget(task, 200),
                pilot_abc.BASE_CONFIG)
            self.assertEqual(result["code"], plain["code"])
            self.assertEqual(result["shown_score"], plain["shown_score"])


if __name__ == "__main__":
    unittest.main()
