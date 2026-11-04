"""Prescoring structural tests for corrected E1.4c-v2 query pool design."""
import json
import unittest
from collections import Counter
from unittest.mock import patch

from e13.contract import canonical_json
from e13.evaluator.selection import input_key
from .cross_episode_bank_v2 import bank, bank_digest, preallocate_pools
from .cross_episode_candidate import fit, choose


class PoolIndependenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pairs = bank()

    def test_pools_preallocated_are_rule_independent(self):
        # The input is a coordinate-only inventory. Changing the hidden word
        # assignment must not alter preallocated pool bytes or draw order.
        original, _ = preallocate_pools({"S": [("related", (0,0,0,0), (0,0,0,1))],
                                         "G": []})
        changed, _ = preallocate_pools({"S": [("unrelated", (2,2,2,2), (0,0,0,0))],
                                        "G": [("related", (1,1,1,1), (2,2,2,2))]})
        self.assertEqual(original, changed)
        self.assertEqual(len(original), 24)

    def test_generator_does_not_call_oracle_during_pools(self):
        with patch("e14.cross_episode_bank_v2.oracle", side_effect=AssertionError("oracle!")):
            values, _ = preallocate_pools({})
        self.assertEqual({len(pool) for pool in values.values()}, {8})

    def test_all_roles_unique_and_previous_input_free(self):
        from .cross_episode_bank_v2 import _prior_inputs
        seen = _prior_inputs()
        self.assertEqual(Counter(x.family for x,_ in self.pairs), {"S":6,"G":6})
        for pair in self.pairs:
            for t in pair:
                for value in [*(x["input"] for x in t.demos), *t.pool,
                              *(x["input"] for x in t.probes)]:
                    key = input_key(t.family, value)
                    self.assertNotIn(key, seen[t.family])
                    seen[t.family].add(key)
        self.assertEqual(bank_digest(self.pairs), bank_digest(bank()))

    def test_source_target_same_motifs_but_different_bank_than_v1(self):
        from .cross_episode_bank import bank as v1bank
        older=v1bank()
        self.assertEqual([[(t.family,t.role,t.regime,t.word) for t in p] for p in older],
                         [[(t.family,t.role,t.regime,t.word) for t in p] for p in self.pairs])
        for old,new in zip(older,self.pairs):
            for a,b in zip(old,new):
                self.assertNotEqual(a.pool,b.pool)

if __name__=="__main__":unittest.main()
