"""Check routing evidence and fresh evaluator data before the pilot."""

import json
import unittest
from collections import Counter

from e13.contract import canonical_json
from e13.evaluator.order_challenge import _fixture
from e13.evaluator.selection import input_key, public_inputs

from .isolated import fit_isolated
from .pilot_bank import REGIMES, bank, bank_sha256


class RoutingTests(unittest.TestCase):
    def test_order_switch_uses_visible_counterexample_in_both_families(self):
        for family in ("S", "G"):
            raw = _fixture(family).fixture.fit_request
            fit = fit_isolated(raw, policy="adaptive")
            self.assertEqual(fit.trace["diagnosis"], "counter_inconsistent")
            self.assertEqual(fit.trace["route"], "order")
            self.assertEqual(fit.trace["order_matches"], fit.trace["demo_count"])

    def test_small_budget_does_not_claim_counter_inconsistency(self):
        request = json.loads(_fixture("S").fixture.fit_request)
        request["fuel"] = 1
        fit = fit_isolated(canonical_json(request), policy="adaptive")
        self.assertEqual(fit.trace["diagnosis"], "counter_budget_exhausted")
        self.assertEqual(fit.status, "fuel_exhausted")

    def test_bank_is_balanced_and_has_no_exact_input_overlap(self):
        episodes = bank()
        self.assertEqual(bank_sha256(episodes), bank_sha256(bank()))
        self.assertEqual(Counter((e.family, e.regime) for e in episodes),
                         {(f, r): 3 for f in ("S", "G") for r in REGIMES})
        seen = public_inputs()
        for family in ("S", "G"):
            previous = _fixture(family).fixture
            seen[family].update(input_key(family, json.loads(p.input))
                                for p in previous.in_distribution + previous.extrapolation)
            seen[family].update(input_key(family, d["input"])
                                for d in json.loads(previous.fit_request)["target"])
        for episode in episodes:
            visible = json.loads(episode.fit_request)
            probes = episode.in_distribution + episode.extrapolation
            cases = [demo["input"] for demo in visible["target"]] + [json.loads(p.input) for p in probes]
            for value in cases:
                key = input_key(episode.family, value)
                self.assertNotIn(key, seen[episode.family])
                seen[episode.family].add(key)
