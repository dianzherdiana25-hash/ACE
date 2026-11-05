"""Public R6-v3 falsification and accounting tests. No private holdout."""
from dataclasses import replace
import unittest

from .planning import (Meter, World, geometric_lower_bound_certificate,
                       heuristic, metric_heuristic, search, simulate,
                       forced_key_order_certificate, generate)
from .study_v2 import independent_optimal_cost
from .study_v3 import (SEEDS, FAMILIES, CONDITIONS, METHODS, make_world, run)


class TopologyShiftTests(unittest.TestCase):
    def test_seed_and_family_contract(self):
        self.assertEqual(len(SEEDS), 24)
        self.assertEqual(len(set(SEEDS)), len(SEEDS))
        self.assertTrue(set(SEEDS).isdisjoint(range(9500, 9524)))
        for bad in (0, 9500, SEEDS[-1]+1):
            with self.assertRaises(ValueError):
                make_world(bad, 'paired_control', 'static')
        with self.assertRaises(ValueError):
            make_world(SEEDS[0], 'hidden', 'static')

    def test_worlds_paired_with_genuinely_nonlocal_edges(self):
        for seed in SEEDS:
            control = make_world(seed, 'paired_control', 'static')
            portal = make_world(seed, 'nonlocal_portals', 'static')
            self.assertEqual(control.keys, portal.keys)
            self.assertEqual(control.locks, ())
            self.assertEqual(portal.locks, ())
            self.assertEqual(control.width, portal.width)
            self.assertEqual(control.height, portal.height)
            self.assertEqual(control.weights, tuple(w for w in portal.weights if w in control.weights))
            self.assertGreater(len(portal.weights), len(control.weights))
            self.assertTrue(geometric_lower_bound_certificate(control))
            self.assertFalse(geometric_lower_bound_certificate(portal))
            self.assertIsNotNone(independent_optimal_cost(portal))

    def test_independent_oracle_and_metric_a_star_static_all_seeds(self):
        for seed in SEEDS:
            for family in FAMILIES:
                w = make_world(seed, family, 'static')
                optimum = independent_optimal_cost(w)
                self.assertEqual(search(w,(0,0),frozenset(),'dijkstra',Meter(100000)).cost, optimum)
                self.assertEqual(search(w,(0,0),frozenset(),'astar_metric',Meter(100000)).cost, optimum)
                self.assertEqual(simulate(w, 'robust', 1800)['cost'], optimum)

    def test_metric_a_star_matches_oracle_with_known_blocked_edge(self):
        for seed in SEEDS:
            for family in FAMILIES:
                w = make_world(seed, family, 'neutral_closure')
                blocked = frozenset((w.shock,))
                optimum = independent_optimal_cost(w, blocked)
                result = search(w, (0,0), blocked, 'astar_metric', Meter(100000))
                self.assertEqual(result.cost, optimum, (seed, family))

    def test_portal_manhattan_failure_counterexample(self):
        w = make_world(12114, 'nonlocal_portals', 'static')
        old = simulate(w,'astar',1800)
        safe = simulate(w,'astar_metric',1800)
        self.assertEqual(independent_optimal_cost(w),26)
        self.assertEqual(old['cost'],34)
        self.assertEqual(safe['cost'],26)
        self.assertTrue(old['success'] and safe['success'])
        self.assertGreater(safe['metric_edge_scans'],0)

    def test_metric_heuristic_under_true_remaining_cost(self):
        for seed in SEEDS[:8]:
            for family in FAMILIES:
                w=make_world(seed,family,'static')
                for pos in (0, w.keys[0], w.keys[-1], w.goal):
                    for mask in (0, w.all_keys, 1):
                        meter=Meter(10000)
                        h=metric_heuristic(w,pos,mask,None,meter)
                        truth=search(w,(pos,mask),frozenset(),'dijkstra',Meter(10000)).cost
                        if truth is not None:
                            self.assertLessEqual(h,truth,(seed,family,pos,mask,h,truth))

    def test_world_shock_hidden_before_attempt(self):
        for seed in SEEDS[:8]:
            a = make_world(seed,'nonlocal_portals','static')
            b = make_world(seed,'nonlocal_portals','neutral_closure')
            self.assertEqual(a.adjacency,b.adjacency)
            self.assertEqual(a.weights,b.weights)
            for mode in ('astar','astar_metric','dijkstra'):
                x=search(a,(0,0),frozenset(),mode,Meter(2000))
                y=search(b,(0,0),frozenset(),mode,Meter(2000))
                self.assertEqual(x,y,(seed,mode))

    def test_budget_across_searches_and_replans(self):
        for seed in SEEDS[:10]:
            for family in FAMILIES:
                for condition in CONDITIONS:
                    w=make_world(seed,family,condition)
                    for budget in (1,10,60,180):
                        for method in ('astar_metric','robust','hier_replan'):
                            r=simulate(w,method,budget)
                            self.assertLessEqual(r['expanded'],budget)
                            self.assertNotEqual(r['status'],'illegal_transition')
                            self.assertLessEqual(r['failed_actions'],1)

    def test_metric_accounting_is_nonnegative_and_replayable(self):
        w=make_world(SEEDS[0],'nonlocal_portals','neutral_closure')
        a=simulate(w,'astar_metric',1800)
        b=simulate(w,'astar_metric',1800)
        self.assertEqual(a,b)
        self.assertGreater(a['metric_edge_scans'],0)
        self.assertGreater(a['metric_heap_pops'],0)
        self.assertGreater(a['metric_sources'],0)
        self.assertLessEqual(a['metric_sources'],w.width*w.height)

    def test_comparison_has_identical_world_for_each_method(self):
        r=run(n=1,budgets=(60,))
        self.assertEqual(len(r['rows']),len(FAMILIES)*len(CONDITIONS)*len(METHODS))
        groups={}
        for row in r['rows']:
            groups.setdefault((row['family'],row['condition']),set()).add(row['offline_lower_bound'])
        self.assertTrue(all(len(group)==1 for group in groups.values()))
        self.assertEqual(r,run(n=1,budgets=(60,)))
        with self.assertRaises(ValueError):
            run(n=25)
        with self.assertRaises(ValueError):
            run(n=1,budgets=(180,60))

    def test_nonlocal_gate_bypass_invalidates_order_certificate(self):
        w=generate(9501,'ood',False)
        self.assertTrue(forced_key_order_certificate(w))
        # Cost is deliberately high enough to preserve geometric metric, but
        # column-0 -> column-2 portal jumps over boundary-1 lock.
        u, v = w.keys[0], w.keys[2]
        self.assertNotIn(v, w.adjacency[u])
        adj=[set(neighbors) for neighbors in w.adjacency]
        adj[u].add(v)
        adj[v].add(u)
        portal=replace(w,adjacency=tuple(tuple(sorted(x)) for x in adj),
                       weights=w.weights+((min(u,v),max(u,v),10),))
        self.assertFalse(forced_key_order_certificate(portal))
        self.assertTrue(geometric_lower_bound_certificate(portal))

    def test_old_manhattan_heuristic_can_overestimate(self):
        # Direct cheap portal 0->distant key invalidates Manhattan as a metric.
        w=make_world(12114,'nonlocal_portals','static')
        a, b, _ = next((a, b, cost) for a, b, cost in w.weights
                       if cost < abs(a % w.width - b % w.width) + abs(a // w.width - b // w.width))
        original = heuristic(w, a, 0, b)
        safe = metric_heuristic(w, a, 0, b, Meter(100000))
        self.assertGreater(original, safe)
        self.assertEqual(safe, 1)


if __name__=='__main__':
    unittest.main()
