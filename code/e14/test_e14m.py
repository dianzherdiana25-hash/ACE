import unittest

from e13.contract import ContractError, canonical_json

from .e14g_audit import predictions
from .e14g_bank import sha, trace, windows
from .e14j_worker import render
from .e14m_bank import build, inventory
from .e14m_run import frozen, invoke, schedule, stage
from .e14m_worker import CAP, QUERY_LENGTH, negative_paths, solve


class E14MPrescore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank, _, _ = frozen()

    def test_public_bank_is_new_and_reproducible(self):
        used = inventory()
        self.assertEqual(sum(map(len, used.values())), 17006)
        self.assertEqual(canonical_json(build()), canonical_json(self.bank))
        self.assertEqual(len(schedule(self.bank)), 72)
        for b in self.bank["blocks"]:
            f = b["family"]
            self.assertEqual((len(b["demos"]), len(b["probes"])), (32, 8))
            self.assertTrue(all(len(trace(f, x)) == 14 for x in b["probes"]))
            for raw in [*b["demos"], *b["probes"]]:
                digest = sha(canonical_json(raw))
                self.assertNotIn(digest, used[f])
                used[f].add(digest)
        self.assertEqual(sum(map(len, used.values())), 19246)

    def test_reachable_and_rare_certificates_and_matched_labels(self):
        for b in self.bank["blocks"]:
            f, demos = b["family"], b["demos"]
            main = b["worlds"][0]
            if main["condition"] == "natural":
                continue
            target = tuple(main["word"])
            sixes = set().union(*(windows(trace(f, raw), 6) for raw in demos))
            self.assertTrue(all(len(trace(f, x)) < 7 for x in demos))
            if main["condition"] == "rare":
                self.assertNotIn(target[:6], sixes)
                self.assertNotIn(target[1:], sixes)
            else:
                self.assertTrue(any(target in windows(q, 7) for q in negative_paths(sixes)))
                other = tuple(b["worlds"][1]["word"])
                self.assertEqual(predictions(f, demos, target), predictions(f, demos, other))

    def test_sandbox_wire_and_falsification_certificate(self):
        raw = (1, 2, 1, 2, 2, 1, 1, 2, 1)
        sixes = sorted(windows(raw, 6))
        known = [{"input": render("G", sixes[i % len(sixes)]), "output": None} for i in range(32)]
        packet = {"family": "G", "seed": 5, "mode": "falsify", "demos": known}
        for field in ("target", "probes", "condition"):
            with self.assertRaises(ContractError):
                solve(canonical_json({**packet, field: []}))
        with stage() as root:
            a, _ = invoke(root, packet)
            b, _ = invoke(root, {**packet, "mode": "adjudicate"})
        self.assertEqual(a["offers"], b["offers"])
        self.assertLessEqual(len(a["offers"]), CAP)
        chosen = a["offers"][a["choice"]]
        self.assertTrue(chosen["blank_consensus"])
        events = trace("G", chosen["input"])
        self.assertEqual(len(events), QUERY_LENGTH)
        self.assertTrue(windows(events, 6) <= set(sixes))

    def test_negative_walk_has_no_invented_six_windows(self):
        sixes = windows((0, 1, 1, 0, 2, 1, 0, 0, 2), 6)
        paths = negative_paths(sixes)
        self.assertTrue(paths)
        self.assertTrue(all(len(q) == QUERY_LENGTH and windows(q, 6) <= sixes for q in paths))
