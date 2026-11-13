"""Differential tests for the per-round generation context.

Gate 1 of the candidate's promotion (gates fixed in PR #183's
report): the context path must produce exactly the variants the
no-context path produces — same set, same order — and identical
solve outputs, with the shared context never mutated by the group
functions that read it.
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ace_operational import pilot_abc  # noqa: E402
from ace_operational.gen_context_bench import (  # noqa: E402
    solve_no_context, variants_no_context)


def _tasks(levels=(1, 2, 3, 4), seeds=(1, 2, 3)):
    return pilot_abc.generate_universe(
        families=["pricing", "shipping"], levels=list(levels),
        seeds=list(seeds))


class GenerationContextTests(unittest.TestCase):

    def test_context_contents_match_independent_computation(self):
        for task in _tasks(seeds=(1,)):
            tree = ast.parse(task["buggy_code"])
            ctx = pilot_abc._round_context(tree, task["spec"])
            self.assertEqual(ctx["numbers"],
                             pilot_abc._spec_numbers(task["spec"]))
            self.assertEqual(
                ctx["compares"],
                [n for n in ast.walk(tree) if isinstance(n, ast.Compare)])
            self.assertEqual(
                ctx["augassigns"],
                [n for n in ast.walk(tree)
                 if isinstance(n, ast.AugAssign)])

    def test_group_functions_identical_with_and_without_context(self):
        for task in _tasks():
            code, spec = task["buggy_code"], task["spec"]
            tree = ast.parse(code)
            ctx = pilot_abc._round_context(tree, spec)
            for name, fn in pilot_abc.GROUP_FN.items():
                with_ctx = fn(code, spec, tree=tree, ctx=ctx)
                without = fn(code, spec, tree=tree)
                self.assertEqual(with_ctx, without,
                                 f"{name} on {task['task_id']}")
                also_bare = fn(code, spec)
                self.assertEqual(with_ctx, also_bare)

    def test_context_is_not_mutated_by_groups(self):
        for task in _tasks(seeds=(1, 2)):
            tree = ast.parse(task["buggy_code"])
            ctx = pilot_abc._round_context(tree, task["spec"])
            snapshot = (set(ctx["numbers"]), list(ctx["compares"]),
                        list(ctx["augassigns"]))
            for fn in pilot_abc.GROUP_FN.values():
                fn(task["buggy_code"], task["spec"], tree=tree, ctx=ctx)
            self.assertEqual(ctx["numbers"], snapshot[0])
            self.assertEqual(ctx["compares"], snapshot[1])
            self.assertEqual(ctx["augassigns"], snapshot[2])

    def test_variants_by_group_matches_no_context_reference(self):
        for task in _tasks():
            self.assertEqual(
                pilot_abc.variants_by_group(task["buggy_code"],
                                            task["spec"]),
                variants_no_context(task["buggy_code"], task["spec"]))

    def test_solve_outputs_identical(self):
        for task in _tasks(seeds=(1, 2, 3, 4, 5)):
            public = pilot_abc._public(task)
            cand = pilot_abc.solve_with_config(
                public, pilot_abc._budget_for(task, 200),
                pilot_abc.BASE_CONFIG)
            base = solve_no_context(
                public, pilot_abc._budget_for(task, 200),
                pilot_abc.BASE_CONFIG)
            self.assertEqual(cand, base, task["task_id"])

    def test_broken_code_raises_in_both_paths(self):
        code = "def f(x):\n    return x *\n"
        with self.assertRaises(SyntaxError):
            pilot_abc.variants_by_group(code, "spec 10")
        with self.assertRaises(SyntaxError):
            variants_no_context(code, "spec 10")


if __name__ == "__main__":
    unittest.main()
