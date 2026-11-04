import unittest

from e13.contract import ContractError, canonical_json

from .e14g_audit import fit_counts, predictions
from .e14g_bank import sha, trace
from .e14i_bank import build, distinct_inputs, history_index
from .e14i_run import choice, distances, frozen, invoke_selector, schedule, selector_mount
from .e14i_selector import solve


class E14IPrescore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank, _, _ = frozen()

    def test_bank_regenerates_and_has_no_cross_block_collisions(self):
        self.assertEqual(canonical_json(self.bank), canonical_json(build()))
        self.assertEqual(len(schedule(self.bank)), 72)
        seen = history_index()
        self.assertEqual(sum(map(len, seen.values())), 8950)
        fresh = 0
        for block in self.bank["blocks"]:
            for raw in distinct_inputs(block):
                digest = sha(canonical_json(raw))
                self.assertNotIn(digest, seen[block["family"]])
                seen[block["family"]].add(digest)
                fresh += 1
        self.assertEqual(fresh, 1752)

    def test_counterfactual_pool_and_exactly_two_compatible_words(self):
        cases = [b for b in self.bank["blocks"] if len(b["words"]) == 2]
        self.assertEqual(len(cases), 12)
        for b in cases:
            family = b["family"]
            short, long = map(tuple, b["words"])
            a, z = (b["pools"][k] for k in ("witness", "no_witness"))
            self.assertEqual(sum(x == y for x, y in zip(a, z, strict=True)), 6)
            self.assertEqual({len(trace(family, raw)) for raw in [*a, *z]}, {6})
            for samples, different in ((b["demos"], 0), (a, 2), (z, 0), (b["probes"], 4)):
                self.assertEqual(sum(x != y for x, y in zip(predictions(family, samples, short),
                                                           predictions(family, samples, long), strict=True)),
                                 different)
            known = predictions(family, b["demos"], short)
            for word in (short, long):
                scores = fit_counts(family, len(word), b["demos"], known)
                self.assertEqual([k for k, v in scores.items() if v == 32], [word])

    def test_total_variation_is_class_normalized(self):
        first = [([], 4), ([5], 4)]
        second = [([], 1), ([5], 1)]
        classes = {"5": {"fit_matches": 32, "candidates": 8, "histograms": [first] * 8},
                   "6": {"fit_matches": 32, "candidates": 2, "histograms": [second] * 8}}
        num, den = distances(classes)
        self.assertEqual((num, den), ([0] * 8, 32))
        self.assertEqual(choice(classes, num), (5, 0, None))
        classes["6"]["histograms"][4] = [([], 2)]
        num, den = distances(classes)
        self.assertEqual(num[4], den // 2)
        self.assertEqual(choice(classes, num)[2], 4)

    def test_selector_only_accepts_labeled_demos_and_unlabeled_inputs(self):
        data = {"family": "S", "demos": [{"input": [1], "output": []}] * 32, "inputs": [[1]] * 8}
        with self.assertRaises(ContractError):
            solve(canonical_json({**data, "target_word": [0] * 5}))
        with self.assertRaises(ContractError):
            solve(canonical_json({**data, "inputs": [{"input": [1], "output": []}] * 8}))
        with selector_mount() as root:
            classes, _ = invoke_selector(root, **{"family": "S", "demos": data["demos"], "pool": data["inputs"]})
        self.assertEqual(distances(classes)[0], [0] * 8)
