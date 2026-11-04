import unittest

from e13.contract import ContractError, canonical_json

from .e14g_audit import fit_counts, predictions
from .e14g_bank import oracle, sha, trace, windows
from .e14j_worker import render
from .e14n_bank import build, inventory
from .e14n_run import frozen, invoke, schedule, stage
from .e14n_worker import CANDIDATE_CAP, solve


class E14NPrescore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank, _, _ = frozen()

    def test_fresh_frozen_bank_and_held_out_shape(self):
        used = inventory()
        self.assertEqual(sum(map(len, used.values())), 19246)
        self.assertEqual(canonical_json(build()), canonical_json(self.bank))
        self.assertEqual(len(schedule(self.bank)), 72)
        for b in self.bank["blocks"]:
            f = b["family"]
            self.assertEqual((len(b["demos"]), len(b["probes"])), (32, 8))
            self.assertLessEqual(len(b["observations"]), 4)
            self.assertTrue(all(len(trace(f, x)) == 14 for x in b["probes"]))
            known = {trace(f, x) for x in b["demos"]}
            for raw in b["observations"]:
                events = trace(f, raw)
                self.assertNotIn(events, known)
                known.add(events)
            for raw in b["demos"] + b["observations"] + b["probes"]:
                digest = sha(canonical_json(raw))
                self.assertNotIn(digest, used[f])
                used[f].add(digest)
        self.assertEqual(sum(map(len, used.values())), 21568)

    def test_fixture_certificates_and_controls(self):
        for b in self.bank["blocks"]:
            f = b["family"]
            for world in b["worlds"]:
                condition = world["condition"]
                target = tuple(world["word"])
                if condition in ("natural", "matched", "no_trigger"):
                    continue
                w = b["observations"][0]
                output = oracle(f, target, w)
                self.assertTrue(any(output) if f == "S" else output is not None)
                inputs = [*b["demos"], w]
                known = predictions(f, inputs, target)
                for l in (5, 6):
                    self.assertNotIn(len(inputs), fit_counts(f, l, inputs, known).values())
                if condition == "outside":
                    covered = set().union(*(windows(trace(f, raw), 9) for raw in b["demos"]))
                    self.assertTrue(windows(trace(f, w), 9) <= covered)
                if condition == "ambiguous":
                    fits = [word for l in (7, 8, 9) for word in windows(trace(f, w), l)
                            if predictions(f, inputs, word) == known]
                    self.assertGreater(len(fits), 1)

    def test_toy_trigger_and_directed_completeness_in_sandbox(self):
        motif = (1, 2, 1, 1, 2, 2, 1)
        known = [{"input": render("G", motif[i:i+6]), "output": None} for i in (0, 1)] * 16
        packet = {"family": "G", "demos": known}
        for field in ("target", "probes", "condition"):
            with self.assertRaises(ContractError):
                solve(canonical_json({**packet, field: []}))
        with stage() as root:
            first, _ = invoke(root, packet)
            self.assertTrue(any(first["base"]))
            self.assertFalse(first["expansions"])
            raw = render("G", motif)
            new, _ = invoke(root, {"family": "G", "demos": [*known, {"input": raw, "output": 8}]})
        self.assertFalse(any(new["base"]))
        self.assertEqual(new["anchor"], 32)
        arms = new["expansions"]
        self.assertEqual(arms["directed"]["classes"], [[list(motif)], [], []])
        self.assertEqual(arms["directed"]["classes"], arms["enumerate"]["classes"])
        self.assertLess(arms["directed"]["attempted"], arms["enumerate"]["attempted"])

    def test_expansion_cap_covers_complete_symbolic_baseline(self):
        self.assertLessEqual(sum(3**l for l in (7, 8, 9)), CANDIDATE_CAP)
