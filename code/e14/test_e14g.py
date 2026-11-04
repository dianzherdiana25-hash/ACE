"""Prescore fixtures for generation, custody and checkpoint integrity."""

import copy
import gzip
import json
import unittest
from collections import Counter
from itertools import product
from unittest.mock import patch

from e13.contract import ContractError, canonical_json, input_value

from .e14g_bank import alphabet, build, oracle, sha, trace, windows
from .e14g_isolation import validate_boundary
from .e14g_run import HISTORY, REPO, frozen, pick
from .e14g_worker import solve


class E14GPrescore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history = json.loads(gzip.decompress((REPO / HISTORY).read_bytes()))
        cls.bank, _, _ = frozen()

    def test_exact_regeneration_and_no_reuse(self):
        self.assertEqual(canonical_json(build(self.history)), canonical_json(self.bank))
        self.assertEqual(self.bank["historical_index_sha256"],
                         "946e9eb79e1c5654076629fdbe1864120c88fd083a545ecb8de0d2d117fcf344")
        seen = {family: set(items) for family, items in self.history.items()}
        new = 0
        for block in self.bank["blocks"]:
            family = block["family"]
            for role, size in (("demos", 32), ("pool", 8), ("probes", 8)):
                self.assertEqual(len(block[role]), size)
                for raw in block[role]:
                    input_value(family, raw)
                    digest = sha(canonical_json(raw))
                    self.assertNotIn(digest, seen[family])
                    seen[family].add(digest)
                    new += 1
        self.assertEqual(new, 2304)

    def test_natural_preallocated_before_motifs(self):
        from . import e14g_bank
        original = e14g_bank.SEEDS
        with patch.object(e14g_bank, "SEEDS", {**original, "motifs": 121907}):
            alternative = build(self.history)

        def natural_inputs(bank):
            return [{key: value for key, value in block.items() if key != "words"}
                    for block in bank["blocks"] if block["distribution"] == "natural"]
        self.assertEqual(natural_inputs(self.bank), natural_inputs(alternative))

    def test_blocks_and_mirrors(self):
        blocks = self.bank["blocks"]
        cells = Counter((b["distribution"], b["family"], b["length"]) for b in blocks)
        self.assertEqual(len(cells), 8)
        self.assertEqual(set(cells.values()), {6})
        for block in blocks:
            self.assertEqual(len(block["words"]), 1 if block["distribution"] == "natural" else 2)
        self.assertEqual(sum(len(block["words"]) for block in blocks), 72)

    def test_opportunity_is_constructed_by_negative_cover_and_witnesses(self):
        for b in self.bank["blocks"]:
            if b["distribution"] != "opportunity":
                continue
            family, length = b["family"], b["length"]
            twins = {tuple(word) for word in b["words"]}
            covered = set().union(*(windows(trace(family, raw), length) for raw in b["demos"]))
            self.assertEqual(covered, set(product(alphabet(family), repeat=length)) - twins)
            distinct = [len({str(oracle(family, word, raw)) for word in twins}) == 2 for raw in b["pool"]]
            self.assertEqual(sum(distinct), 2)
            self.assertEqual(len({len(trace(family, raw)) for raw in b["pool"]}), 1)
            for word in twins:
                labels = [oracle(family, word, raw) for raw in b["probes"]]
                self.assertEqual(sum(any(v) if family == "S" else v is not None for v in labels), 4)

    def test_out_of_basis_ceiling(self):
        for b in self.bank["blocks"]:
            if b["distribution"] != "opportunity" or b["length"] != 6:
                continue
            family = b["family"]
            for target in b["words"]:
                expected = [oracle(family, tuple(target), raw) for raw in b["probes"]]
                for blind in product(alphabet(family), repeat=5):
                    self.assertLessEqual(sum(oracle(family, blind, raw) == y
                                             for raw, y in zip(b["probes"], expected, strict=True)), 4)

    def test_no_disagreement_keeps_fixed_tie(self):
        self.assertEqual(pick([[2]] * 8, [[0, 0]] * 8, "S"), {"gini": 0, "minimax": 0, "static": 0})

    def test_worker_rejects_extra_wire_fields_and_labels(self):
        data = {"family": "S", "operation": "select", "demos": [{"input": [0], "output": []}] * 32,
                "inputs": [[0]] * 8}
        self.assertEqual(solve(canonical_json(data), 5)["partitions"], [[243]] * 8)
        with self.assertRaises(ContractError):
            solve(canonical_json({**data, "probe_labels": [[]] * 8}), 5)
        tampered = copy.deepcopy(data)
        tampered["inputs"][0] = {"input": [0], "output": []}
        with self.assertRaises(ContractError):
            solve(canonical_json(tampered), 5)

    def test_native_isolation(self):
        self.assertTrue(all(validate_boundary()["checks"].values()))
