"""Tests for oracle semantics, demonstrability, and the public bank boundary."""

import json
import unittest
from collections import Counter
from dataclasses import replace

from e13.contract import canonical_json
from e13.evaluator import oracle
from e13.evaluator.bank import GROUPS, _chain, bank_digest, development_bank, structural_relation
from e13.split_audit import audit_splits


class BankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.episodes, cls.blocks, cls.witnesses = development_bank()

    def test_oracles_on_state_and_cycle_examples(self):
        self.assertEqual(oracle.symbols("repeat_run", [2, 2, 2, 1, 1]), (0, 1, 0, 0))
        self.assertEqual(oracle.symbols("rise_start", [1, 2, 3, 2, 3]), (1, 0, 0, 1))
        self.assertEqual(oracle.symbols("down_parity", [3, 2, 4, 1]), (1, 1, 0))
        self.assertEqual(oracle.graph("repeat_once", _chain([0, 0, 1], [4, 2, 3])), 9)
        self.assertIsNone(oracle.graph("repeat_odd", _chain([0, 0, 0])))
        self.assertEqual(oracle.graph("edge_even", _chain([])), 0)
        graph = {"nodes": 2, "start": 0, "goal": 1, "edges": [[0, 0, 1, 0], [0, 1, 0, 3]]}
        self.assertEqual(oracle.graph("edge_even", graph), 3)
        self.assertEqual(oracle.graph("edge_min_three", graph), 3)
        self.assertIsNone(oracle.graph("switch_at_least_two", graph))

    def test_bank_is_balanced_and_reproducible(self):
        self.assertEqual(Counter((e.family, e.regime) for e in self.episodes), {
            (family, regime): 6 for family in ("S", "G") for regime in ("related", "unrelated")
        })
        self.assertEqual(len(self.blocks), 12)
        self.assertEqual(len({json.loads(e.fit_request)["task_id"] for e in self.episodes}), 24)
        self.assertEqual(bank_digest(self.episodes), bank_digest(development_bank()[0]))
        self.assertNotEqual(bank_digest(self.episodes), bank_digest(development_bank(1305)[0]))

    def test_fit_payload_excludes_routing_and_every_probe(self):
        for episode in self.episodes:
            request = json.loads(episode.fit_request)
            self.assertEqual(set(request), {"version", "family", "task_id", "seed",
                                            "fuel", "source", "target"})
            demos = {canonical_json(demo["input"]) for role in ("source", "target")
                     for demo in request[role]}
            probes = [probe.input for probe in episode.in_distribution + episode.extrapolation]
            self.assertEqual(len(probes), 12)
            self.assertEqual(len(set(probes)), 12)
            self.assertFalse(demos.intersection(probes))

    def test_demos_distinguish_each_rule_from_its_public_competitors(self):
        for episode in self.episodes:
            reference = oracle.symbols if episode.family == "S" else oracle.graph
            names = [name for group in GROUPS[episode.family] for name, _ in group]
            request = json.loads(episode.fit_request)
            for role, intended in (("source", episode.source_rule), ("target", episode.target_rule)):
                fitting = [rule for rule in names if all(
                    canonical_json(reference(rule, demo["input"])) == canonical_json(demo["output"])
                    for demo in request[role]
                )]
                self.assertEqual(fitting, [intended])

    def test_structural_rules_and_split_rejection(self):
        self.assertEqual(structural_relation(("outer", ("pair", "x")),
                                             ("outer", ("pair", "x"))), (0, True))
        self.assertEqual(structural_relation(("outer", ("pair", "x")),
                                             ("other", ("pair", "x"))), (1 / 6, True))
        self.assertEqual(structural_relation(("outer", ("pair", "x")),
                                             ("outer", ("pair", "y"))), (1 / 6, False))
        first, second, *_ = self.blocks
        for bad, message in (
            (replace(first, split="selection"), "rule shape overlap"),
            (replace(first, split="selection", shape=("different",)), "probe behavior overlap"),
            (replace(second, split="selection", tasks=first.tasks), "task payload overlap"),
            (replace(second, split="selection", inputs=first.inputs), "task input overlap"),
        ):
            with self.assertRaisesRegex(ValueError, message):
                audit_splits((first, bad), self.witnesses)


if __name__ == "__main__":
    unittest.main()
