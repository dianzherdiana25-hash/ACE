import unittest

from e13.contract import ContractError, canonical_json, input_value

from .e14g_bank import sha
from .e14p_bank import build, inventory
from .e14p_graph import minimum, paths
from .e14p_run import frozen, regimes, schedule, stage, target_call
from .e14p_worker import graph_features, solve


class E14PPrescore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank,_,_ = frozen()

    def test_bank_fresh_and_has_real_branching_choices(self):
        used = inventory()
        self.assertEqual(sum(map(len,used.values())),23168)
        self.assertEqual(canonical_json(self.bank),canonical_json(build()))
        self.assertEqual(len(schedule(self.bank)),12)
        for b in self.bank["blocks"]:
            for family, raws in (("S", b["source_demos"]+b["source_observations"]),
                                ("G", b["target_demos"]+b["probes"]+[b["calibration"]]+
                                 ([b["neutral"]] if b["neutral"] else []))):
                for raw in raws:
                    digest=sha(canonical_json(raw))
                    self.assertNotIn(digest,used[family])
                    used[family].add(digest)
                    input_value(family,raw)
                    if family=="G":
                        self.assertEqual(len(paths(raw)),4)
            for mode,(truth,calibration) in regimes(b).items():
                self.assertEqual(sum(minimum(paths(raw),truth) is not None for raw in b["probes"]),4)
                self.assertEqual(minimum(paths(calibration),truth) is not None,mode=="aligned")
        self.assertEqual(sum(map(len,used.values())),23754)

    def test_worker_matches_independent_weighted_oracle(self):
        b=self.bank["blocks"][0]
        truth,_=regimes(b)["aligned"]
        found=False
        for raw in b["probes"]:
            route=paths(raw)
            self.assertEqual(graph_features(raw).get(truth),minimum(route,truth))
            costs={cost for events,cost in route if any(events[i:i+len(truth)]==truth
                                                        for i in range(len(events)-len(truth)+1))}
            found|=len(costs)>1
        self.assertTrue(found)

    def test_cold_successor_only_accepts_typed_artifact(self):
        b=self.bank["blocks"][0]
        rows=[{"input":x,"output":None} for x in b["target_demos"]]
        packet={"demos":rows,"artifact":None}
        for bad in ({**packet,"source_demos":[]},{**packet,"artifact":{"code":"print(0)"}}):
            with self.assertRaises(ContractError):
                solve(canonical_json(bad))
        with stage() as root:
            cold,_=target_call(root,packet)
        self.assertFalse(cold["artifact_used"])
        self.assertTrue(cold["selected"])
