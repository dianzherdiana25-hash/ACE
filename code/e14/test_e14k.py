import random
import unittest

from e13.contract import ContractError, canonical_json, input_value

from .e14g_audit import fit_counts, predictions
from .e14g_bank import sha, trace, windows
from .e14j_bank import nonoverlap
from .e14j_worker import render
from .e14k_bank import build, prior_inputs
from .e14k_run import frozen, invoke, schedule, stage
from .e14k_worker import LONG, pack, solve


class E14KPrescore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank, _, _ = frozen()

    def test_fresh_reproducible_bank_and_separate_probe_lengths(self):
        used = prior_inputs()
        self.assertEqual(sum(map(len, used.values())), 13006)
        self.assertEqual(canonical_json(self.bank), canonical_json(build()))
        self.assertEqual(len(schedule(self.bank)), 72)
        for block in self.bank["blocks"]:
            family = block["family"]
            self.assertEqual((len(block["demos"]), len(block["probes"])), (32, 8))
            self.assertTrue(all(len(trace(family, raw)) == 14 for raw in block["probes"]))
            for raw in [*block["demos"], *block["probes"]]:
                digest = sha(canonical_json(raw))
                self.assertNotIn(digest, used[family])
                used[family].add(digest)
        self.assertEqual(sum(map(len, used.values())), 14926)

    def test_engineered_coverage_certificate_and_blank_bounds(self):
        for b in self.bank["blocks"]:
            if b["condition"] == "natural":
                continue
            f, demos = b["family"], b["demos"]
            short, long = map(tuple, b["words"])
            labels = predictions(f, demos, short)
            self.assertEqual(labels, predictions(f, demos, long))
            classes = []
            for length in (5, 6):
                classes.append([w for w, n in fit_counts(f, length, demos, labels).items() if n == 32])
            if b["condition"] == "packable":
                self.assertEqual(len(classes[0]), 3)
                self.assertGreaterEqual(len(classes[1]), 3)
                self.assertTrue(nonoverlap(classes[0]))
                certificate = tuple(b["certificate"])
                self.assertEqual(len(certificate), LONG)
                self.assertTrue(set(classes[0]) <= windows(certificate, 5))
                self.assertNotIn(long, windows(certificate, 6))
                input_value(f, render(f, certificate))
            else:
                self.assertEqual(len(classes[0]), 9)
                self.assertGreater(len(classes[1]), LONG-6+1)

    def test_packer_overlaps_and_respects_cap(self):
        motifs = ((1, 2, 1, 2, 2), (2, 2, 1, 1, 2), (2, 1, 2, 2, 2))
        events = pack(motifs, (1, 2), random.Random(41))
        self.assertEqual(len(events), LONG)
        self.assertTrue(set(motifs) <= windows(events, 5))

    def test_worker_wire_and_cost_limits(self):
        packet = {"family": "G", "mode": "compound", "seed": 91,
                  "demos": [{"input": render("G", (1,)), "output": None}] * 32}
        for field in ("target", "probes", "certificate"):
            with self.assertRaises(ContractError):
                solve(canonical_json({**packet, field: []}))
        with stage() as root:
            row, _ = invoke(root, packet)
        self.assertLessEqual(len(row["offers"]), 8)
        self.assertTrue(all(len(trace("G", q["input"])) == LONG for q in row["offers"]))
