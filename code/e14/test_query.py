"""Check the label boundary and the public counterexample fixtures."""

import json
import unittest
from collections import Counter
from types import SimpleNamespace
from unittest.mock import patch

from e13.contract import canonical_json
from e13.dsl import compile_ast
from e13.evaluator.selection import input_key
from e13.patterns import pattern_ast

from .query_bank import REGIMES, _used_public, bank, bank_digest
from .query_pilot import OneLabel, _coverage_certificate, deterministic
from .query_selector import choose_query


class QueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = bank()

    def test_selector_only_accepts_typed_unlabelled_inputs_and_chooses_disagreement(self):
        rise = compile_ast(canonical_json(pattern_ast("S", (0,))))
        fall = compile_ast(canonical_json(pattern_ast("S", (2,))))
        a, b = (SimpleNamespace(program=program, status="fit") for program in (rise, fall))
        pool = (b"[2,2]", b"[1,2]")
        result = choose_query(a, b, pool, seed=5)
        self.assertEqual((result.index, result.disagreements, result.reason),
                         (1, (1,), "disagreement"))
        self.assertEqual(choose_query(a, a, pool, seed=5).reason, "agreement")
        with self.assertRaises(ValueError):
            choose_query(a, b, (b'{"input":[1,2],"label":[1]}',), seed=5)

    def test_budget_fallback_never_uses_partial_disagreement(self):
        rise = compile_ast(canonical_json(pattern_ast("S", (0,))))
        fall = compile_ast(canonical_json(pattern_ast("S", (2,))))
        a, b = (SimpleNamespace(program=program, status="fit") for program in (rise, fall))
        pool = (b"[2,2]", b"[1,2]")
        with patch("e14.query_selector.QUERY_STEPS", 1):
            result = choose_query(a, b, pool, seed=5)
        self.assertEqual((result.reason, result.disagreements), ("query_budget_exhausted", ()))

    def test_oracle_only_reveals_one_label_per_arm(self):
        oracle = OneLabel(self.cases[0])
        self.assertFalse(oracle.used)
        result = oracle.reveal(0)
        self.assertEqual(canonical_json(result["input"]), self.cases[0].pool[0])
        self.assertTrue(oracle.used)
        with self.assertRaisesRegex(ValueError, "budget"):
            oracle.reveal(1)

    def test_freshness_balance_and_out_of_basis_witnesses(self):
        self.assertEqual(bank_digest(self.cases), bank_digest(bank()))
        self.assertEqual(Counter((c.episode.family, c.episode.regime) for c in self.cases),
                         {(f, r): 3 for f in ("S", "G") for r in REGIMES})
        seen = _used_public()
        for case in self.cases:
            ep = case.episode
            values = [demo["input"] for demo in json.loads(ep.fit_request)["target"]]
            values += [json.loads(raw) for raw in case.pool]
            values += [json.loads(p.input) for p in ep.in_distribution + ep.extrapolation]
            self.assertEqual(len(values), 18)
            for value in values:
                key = input_key(ep.family, value)
                self.assertNotIn(key, seen[ep.family])
                seen[ep.family].add(key)
            if ep.regime == "out_of_basis":
                self.assertEqual(_coverage_certificate(case)["distinguishes"],
                                 [{"counter_definitions": 0, "order_words": 0}] * 4)

    def test_replay_preserves_configured_limits(self):
        self.assertEqual(deterministic({"limits": {"query_cpu_us": 100},
                                        "fit": {"cpu_us": 80, "status": "fit"}}),
                         {"limits": {"query_cpu_us": 100}, "fit": {"status": "fit"}})

    def test_serialized_disagreement_list_matches_in_memory_tuple(self):
        self.assertEqual(deterministic({"disagreements": (1, 3)}),
                         deterministic({"disagreements": [1, 3]}))
