import unittest

from e13.contract import ContractError, canonical_json

from .e14g_audit import fit_counts, predictions
from .e14g_bank import oracle, sha, trace
from .e14j_bank import build, inventory, nonoverlap
from .e14j_run import frozen, invoke, schedule, stage
from .e14j_worker import merit, render, solve


class E14JPrescore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank, _, _ = frozen()

    def test_public_bank_is_new_and_reproducible(self):
        self.assertEqual(canonical_json(self.bank), canonical_json(build()))
        self.assertEqual(len(schedule(self.bank)), 72)
        used = inventory()
        self.assertEqual(sum(map(len, used.values())), 10702)
        for block in self.bank["blocks"]:
            family = block["family"]
            for role, n in (("demos", 32), ("pool", 8), ("probes", 8)):
                self.assertEqual(len(block[role]), n)
                for raw in block[role]:
                    digest = sha(canonical_json(raw))
                    self.assertNotIn(digest, used[family])
                    used[family].add(digest)
            self.assertTrue(all(len(trace(family, q)) in (5, 6) for q in block["pool"]))
            self.assertTrue(all(len(trace(family, p)) >= 8 for p in block["probes"]))
        self.assertEqual(sum(map(len, used.values())), 13006)

    def test_structural_label_bounds_and_mirror(self):
        for block in self.bank["blocks"]:
            kind = block["condition"]
            if kind == "natural":
                continue
            family, demos = block["family"], block["demos"]
            short, long = map(tuple, block["words"])
            labels = predictions(family, demos, short)
            self.assertEqual(labels, predictions(family, demos, long))
            candidates = []
            for length in (5, 6):
                fits = fit_counts(family, length, demos, labels)
                candidates.append([w for w, score in fits.items() if score == 32])
            bound = {"single": 1, "sequence": 2, "beyond": 3}[kind]
            self.assertEqual(len(candidates[0]), bound)
            self.assertGreaterEqual(len(candidates[1]), bound)
            self.assertTrue(nonoverlap(candidates[0]))
            self.assertTrue(all(oracle(family, short, raw) == oracle(family, long, raw) for raw in block["pool"]))
            for word in candidates[0]:
                raw = render(family, word)
                self.assertTrue(oracle(family, word, raw) != oracle(family, long, raw))
                self.assertNotIn(trace(family, raw), [trace(family, x) for x in demos])

    def test_merit_prioritizes_guaranteed_disagreement(self):
        short = (0, 0, 1, 2, 2)
        other = (1, 1, 1, 1, 0)
        long = (2, *short)
        self.assertEqual(merit("S", render("S", short), {5: [short], 6: [long]}), (0, 1))
        self.assertEqual(merit("S", render("S", short), {5: [short, other], 6: [long]}), (0.5, 0.25))

    def test_wire_hides_target_and_probe_and_bounds_offers(self):
        packet = {"family": "G", "mode": "guided", "seed": 21, "pool": [],
                  "demos": [{"input": render("G", (1,)), "output": None}] * 32}
        for field in ("target", "probes", "labels"):
            with self.assertRaises(ContractError):
                solve(canonical_json({**packet, field: []}))
        with stage() as root:
            row, _ = invoke(root, packet)
        self.assertLessEqual(len(row["offers"]), 8)
        self.assertTrue(all(len(trace("G", q["input"])) in (5, 6) for q in row["offers"]))
