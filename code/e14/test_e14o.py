import unittest

from e13.contract import ContractError, canonical_json

from .e14g_audit import predictions
from .e14g_bank import sha, trace, windows
from .e14j_worker import render
from .e14o_bank import build, inventory
from .e14o_run import frozen, invoke, schedule, stage
from .e14o_worker import solve


class E14OPrescore(unittest.TestCase):
    def test_fresh_bank_and_matched_demos(self):
        bank, _, _ = frozen()
        self.assertEqual(canonical_json(bank), canonical_json(build()))
        self.assertEqual(len(schedule(bank)), 48)
        used = inventory()
        self.assertEqual(sum(map(len, used.values())), 21568)
        for b in bank["blocks"]:
            f = b["family"]
            for raw in b["demos"] + b["probes"]:
                digest = sha(canonical_json(raw))
                self.assertNotIn(digest, used[f])
                used[f].add(digest)
            self.assertTrue(all(len(trace(f,x)) == 14 for x in b["probes"]))
            if len(b["worlds"]) == 2:
                a, c = [tuple(w["word"]) for w in b["worlds"]]
                self.assertEqual(predictions(f,b["demos"],a), predictions(f,b["demos"],c))
        self.assertEqual(sum(map(len,used.values())), 23168)

    def test_toy_trigger_and_active_recovery(self):
        motif = (1,2,1,1,2,2,1)
        witness = (2,1,*motif)
        sixes = sorted(windows(witness,6))
        known = [{"input":render("G",sixes[i % len(sixes)]),"output":None} for i in range(32)]
        packet = {"family":"G","mode":"active","seed":19,"demos":known}
        with self.assertRaises(ContractError):
            solve(canonical_json({**packet,"target":list(motif)}))
        with stage() as root:
            before, _ = invoke(root,packet)
            self.assertFalse(before["trigger"])
            self.assertTrue(before["offers"][before["choice"]]["blank_consensus"])
            packet["demos"] = [*known,{"input":render("G",witness),"output":10}]
            active, _ = invoke(root,packet)
            passive, _ = invoke(root,{**packet,"mode":"passive"})
        self.assertTrue(active["trigger"])
        self.assertEqual(active["classes"],passive["classes"])
        self.assertIsNotNone(active["choice"])
        self.assertIsNone(passive["choice"])
