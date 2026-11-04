import unittest
from fractions import Fraction

from e13.contract import ContractError, canonical_json

from .e14g_audit import fit_counts, predictions
from .e14g_bank import sha, trace
from .e14j_worker import render
from .e14l_bank import build, inventory
from .e14l_run import frozen, invoke, schedule, stage
from .e14l_worker import MODES, select, solve


class E14LPrescore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank, _, _ = frozen()

    def test_frozen_bank_is_new_and_reproducible(self):
        used = inventory()
        self.assertEqual(sum(map(len, used.values())), 14926)
        self.assertEqual(canonical_json(build()), canonical_json(self.bank))
        self.assertEqual(len(schedule(self.bank)), 72)
        for block in self.bank["blocks"]:
            f = block["family"]
            self.assertEqual((len(block["demos"]), len(block["probes"])), (32, 8))
            self.assertTrue(all(len(trace(f, x)) == 14 for x in block["probes"]))
            for raw in [*block["demos"], *block["probes"]]:
                digest = sha(canonical_json(raw))
                self.assertNotIn(digest, used[f])
                used[f].add(digest)
        self.assertEqual(sum(map(len, used.values())), 17006)

    def test_shift_has_invisible_positive_probes_and_live_models(self):
        for block in self.bank["blocks"]:
            if block["condition"] != "outside":
                continue
            f, motif = block["family"], tuple(block["words"][0])
            demos, probes = block["demos"], block["probes"]
            labels = predictions(f, demos, motif)
            actual = predictions(f, probes, motif)
            positive = [i for i, y in enumerate(actual) if (any(y) if f == "S" else y is not None)]
            self.assertEqual(len(positive), 4)
            for l in (5, 6):
                live = [w for w, n in fit_counts(f, l, demos, labels).items() if n == len(demos)]
                self.assertTrue(live)
                for word in live:
                    pred = predictions(f, probes, word)
                    self.assertTrue(all(not any(pred[i]) if f == "S" else pred[i] is None for i in positive))

    def test_cost_rank_and_gate_differ(self):
        offers = [(Fraction(1, 5), Fraction(1, 10), 12), (Fraction(1, 3), Fraction(1, 4), 5)]
        self.assertEqual(select("minimax", offers), 0)
        self.assertEqual(select("value", offers), 1)
        self.assertIsNone(select("gate", offers))
        self.assertEqual(select("gate", [(Fraction(1, 2), Fraction(1, 2), 12)]), 0)

    def test_sandbox_wire_shared_pool(self):
        packet = {"family": "G", "seed": 19, "mode": "minimax",
                  "demos": [{"input": render("G", (1,)), "output": None}] * 32}
        for forbidden in ("target", "probes", "certificate", "condition"):
            with self.assertRaises(ContractError):
                solve(canonical_json({**packet, forbidden: []}))
        with stage() as root:
            results = [invoke(root, {**packet, "mode": mode})[0] for mode in MODES]
        self.assertTrue(all(row["offers"] == results[0]["offers"] for row in results))
        self.assertLessEqual(len(results[0]["offers"]), 8)
