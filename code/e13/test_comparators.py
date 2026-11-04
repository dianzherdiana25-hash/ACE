"""Verify isolated closed comparators on both public I/O contracts."""

import json
import unittest

from .contract import canonical_json
from .evaluator.bank import development_bank
from .isolation import fit_isolated


class ComparatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        episodes = development_bank()[0]
        cls.samples = (episodes[0].fit_request, episodes[-1].fit_request)

    def test_closed_policies_ignore_source_and_return_bounded_valid_ast(self):
        for raw in self.samples:
            for policy in ("structured", "enumerative"):
                with self.subTest(policy=policy, family=json.loads(raw)["family"]):
                    request = json.loads(raw)
                    original = fit_isolated(raw, policy=policy)
                    request["source"] = request["target"]
                    request["task_id"] = "a" * 32
                    updated = fit_isolated(canonical_json(request), policy=policy)
                    self.assertEqual(original.program.ast, updated.program.ast)
                    self.assertEqual(original.steps, updated.steps)
                    self.assertIn(len(original.program.table), range(1, 5))

    def test_closed_policies_remain_valid_at_fuel_limit(self):
        for raw in self.samples:
            for policy in ("structured", "enumerative"):
                request = json.loads(raw)
                request["fuel"] = 1
                fit = fit_isolated(canonical_json(request), policy=policy)
                self.assertEqual(fit.status, "fuel_exhausted")
                self.assertEqual(fit.steps, 1)
                self.assertEqual(fit.program.family, request["family"])
