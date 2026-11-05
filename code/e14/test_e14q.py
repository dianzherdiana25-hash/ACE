import unittest

from e13.contract import ContractError, canonical_json, input_value

from .e14g_bank import sha
from .e14p_graph import minimum, paths
from .e14q_run import build, frozen, inventory, invoke, stage
from .e14q_worker import solve


class E14QPrescore(unittest.TestCase):
    def test_bank_fresh_and_each_probe_is_specific(self):
        bank,_,_ = frozen()
        self.assertEqual(canonical_json(bank),canonical_json(build()))
        known=inventory()
        initial=len(known)
        for block in bank["blocks"]:
            words=list(map(tuple,block["words"]))
            for raw in block["probes"]:
                digest=sha(canonical_json(raw))
                self.assertNotIn(digest,known)
                known.add(digest)
                self.assertEqual(sum(minimum(paths(raw),w) is not None for w in words),1)
        self.assertEqual(len(known)-initial,96)

    def test_worker_packs_legal_distinguishable_costs(self):
        words=[[1,1,1,1,1,2,2],[1,1,1,1,2,2,2],[1,1,1,2,2,1,2],[1,1,1,2,2,2,1]]
        packet={"words":words,"mode":"packed","seed":1}
        with self.assertRaises(ContractError):
            solve(canonical_json({**packet,"target":0}))
        with stage() as root:
            row,_=invoke(root,packet)
        offer=row["offers"][row["choice"]]
        input_value("G",offer["graph"])
        self.assertLessEqual(len(row["offers"]),8)
        self.assertEqual(len(set(offer["predicted"])),4)
        self.assertEqual(len(paths(offer["graph"])),3)
