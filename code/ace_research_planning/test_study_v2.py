"""R6-v2 independent correctness, non-leakage, and experimental guard checks."""
import dataclasses
import unittest

from .planning import World, Meter, forced_key_order_certificate, structural_route, search, generate, simulate, oracle_cost
from .study_v2 import SEEDS, METHODS, neutral_surprise, independent_optimal_cost, world_for, run


class StudyV2Tests(unittest.TestCase):
    def test_reference_matches_original_search_under_shocks(self):
        for family, seed in (("dev2", 2000), ("dev2", 2002), ("transfer2", 9500), ("transfer2", 9501)):
            for condition in ("static", "neutral", "policy_targeted"):
                w = world_for(family, seed, condition)
                blocked = frozenset((w.shock,)) if w.shock else frozenset()
                self.assertEqual(independent_optimal_cost(w, blocked), oracle_cost(w, blocked))

    def test_certificate_is_sufficient_for_generated_forced_order(self):
        for seed in SEEDS["dev2"][:12]:
            w = world_for("dev2", seed, "static")
            self.assertTrue(forced_key_order_certificate(w))
            r = simulate(w, "structural", 10000)
            self.assertTrue(r["success"])
            self.assertEqual(r["cost"], independent_optimal_cost(w))
            self.assertTrue(all(x == "certified_subgoal" for x in r["strategy_trace"]))

    def test_free_order_fails_certificate(self):
        for seed in SEEDS["transfer2"]:
            w = world_for("transfer2", seed, "static")
            if w.locks == ():
                self.assertFalse(forced_key_order_certificate(w))

    def test_certificate_fail_closed_under_partial_locks(self):
        w = world_for("dev2", 2000, "static")
        self.assertFalse(forced_key_order_certificate(dataclasses.replace(w, locks=())))
        self.assertFalse(forced_key_order_certificate(dataclasses.replace(w, keys=tuple(reversed(w.keys)))))

    def test_neutral_edge_independent_of_agent_route(self):
        w = world_for("transfer2", 9500, "static")
        shocked1 = neutral_surprise(w, 9500)
        shocked2 = neutral_surprise(w, 9500)
        self.assertEqual(shocked1, shocked2)
        self.assertIn(shocked1.shock, [tuple(sorted((u,v))) for u,v,_ in w.weights])
        self.assertIsNotNone(independent_optimal_cost(shocked1, frozenset((shocked1.shock,))))
        without = dataclasses.replace(shocked1, shock=None)
        self.assertEqual(search(shocked1, (0,0), frozenset(), "astar", Meter(10000)),
                         search(without, (0,0), frozenset(), "astar", Meter(10000)))

    def test_new_method_conserves_same_global_node_budget(self):
        for fam, seed in (("dev2",2001), ("transfer2", 9500), ("transfer2",9501)):
            for b in (1, 10, 30, 60, 120):
                for c in ("static", "neutral"):
                    out = simulate(world_for(fam, seed, c), "structural", b)
                    self.assertLessEqual(out["expanded"], b)
                    self.assertFalse(out["status"] == "illegal_transition")

    def test_expensive_global_search_gated_under_small_limit(self):
        w = world_for("transfer2", 9500, "static")  # free-order OOD
        self.assertEqual(w.locks, ())
        r, decision = structural_route(w, (0, 0), frozenset(), Meter(60))
        self.assertEqual(decision, "hierarchical_fallback")
        self.assertTrue(r.route is not None or r.cost is None)

    def test_protocol_shape_replay_and_disjoint(self):
        self.assertFalse(set(SEEDS['dev2']) & set(SEEDS['transfer2']))
        self.assertEqual(len(METHODS), len(set(METHODS)))
        a=run(n=1, budgets=(60,))
        b=run(n=1, budgets=(60,))
        self.assertEqual(a,b)
        self.assertEqual(len(a['rows']), 2*1*3*1*len(METHODS))
        self.assertTrue(all(r['expanded'] <= r['budget'] for r in a['rows']))


if __name__ == "__main__":
    unittest.main()
