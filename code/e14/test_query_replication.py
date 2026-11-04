"""Verify the fresh input split without looking at candidate results."""

import json
import random
import unittest
from collections import Counter
from unittest.mock import patch

from e13.evaluator.selection import input_key

from .query_bank import _used_public, bank as pilot_bank, bank_digest
from .query_replication import POOL_SEED, _pool, bank


class QueryReplicationTests(unittest.TestCase):
    def test_pool_draw_has_no_oracle_access(self):
        with patch("e14.query_replication.oracle", side_effect=AssertionError("oracle access")):
            values = _pool("S", random.Random(POOL_SEED), set())
        self.assertEqual(len(set(values)), 8)

    def test_roles_are_disjoint_and_fresh_against_the_prior_pilot(self):
        used = _used_public()
        for case in (*pilot_bank(), *bank()):
            ep = case.episode
            for raw in [*(json.dumps(d["input"]).encode() for d in json.loads(ep.fit_request)["target"]),
                        *case.pool, *(p.input for p in ep.in_distribution + ep.extrapolation)]:
                key = input_key(ep.family, json.loads(raw))
                self.assertNotIn(key, used[ep.family])
                used[ep.family].add(key)
        cases = bank()
        self.assertEqual(Counter(c.episode.family for c in cases), {"S": 6, "G": 6})
        self.assertEqual(bank_digest(cases), bank_digest(bank()))
