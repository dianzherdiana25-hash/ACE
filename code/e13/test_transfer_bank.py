"""Guard public diagnostic separation and replay inputs."""

import json
import unittest
from collections import Counter

from .contract import canonical_json, parse_fit_request
from .evaluator.bank import _chain, bank_digest
from .evaluator.transfer_bank import _exact_edges, transfer_bank


class TransferBankTests(unittest.TestCase):
    def test_balanced_development_bank_has_no_probe_in_fit(self):
        episodes = transfer_bank()
        self.assertEqual(Counter((e.family, e.regime) for e in episodes), {
            (family, regime): 2 for family in ("S", "G")
            for regime in ("capacity", "related", "unrelated")
        })
        self.assertEqual(bank_digest(episodes), bank_digest(transfer_bank()))
        for episode in episodes:
            parsed = parse_fit_request(episode.fit_request)
            self.assertEqual(parsed.family, episode.family)
            value = json.loads(episode.fit_request)
            demos = {canonical_json(demo["input"]) for role in ("source", "target")
                     for demo in value[role]}
            probes = [probe.input for probe in episode.in_distribution + episode.extrapolation]
            self.assertFalse(demos.intersection(probes))
            self.assertEqual(len(set(probes)), 8)

    def test_fixed_length_graph_reference_checks_exact_length_with_a_cycle(self):
        value = _chain([0, 1], [2, 3])
        value["edges"].append([0, 0, 2, 1])
        self.assertIsNone(_exact_edges(value, 1))
        self.assertEqual(_exact_edges(value, 2), 5)
        self.assertEqual(_exact_edges(value, 4), 7)
