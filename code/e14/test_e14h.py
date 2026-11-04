import unittest
from collections import Counter

from e13.contract import canonical_json

from .e14g_bank import sha
from .e14g_run import HISTORY, REPO, frozen
from .e14h_route import build, choose_grammar, inputs, load_bank, prior_index, read, schedule


class E14HPrescore(unittest.TestCase):
    def test_router_is_conservative(self):
        for short, long, expected in ((32, 32, 5), (32, 30, 5), (30, 32, 6),
                                      (30, 31, 5), (0, 32, 6), (0, 0, 5)):
            self.assertEqual(choose_grammar(short, long), expected)

    def test_frozen_new_bank_regenerates(self):
        bank, _, _, _ = load_bank()
        previous, _, _ = frozen()
        history = read(REPO / HISTORY)
        self.assertEqual(canonical_json(bank), canonical_json(build(previous, history)))
        used = prior_index(previous, history)
        cells = Counter((b["distribution"], b["family"], b["length"]) for b in bank["blocks"])
        self.assertEqual(len(cells), 8)
        self.assertEqual(set(cells.values()), {6})
        self.assertEqual(len(schedule(bank)), 72)
        self.assertEqual(sum(len(x) for x in used.values()), 6646)
        for b in bank["blocks"]:
            for raw in inputs(b):
                digest = sha(canonical_json(raw))
                self.assertNotIn(digest, used[b["family"]])
                used[b["family"]].add(digest)
        self.assertEqual(sum(len(x) for x in used.values()), 8950)
