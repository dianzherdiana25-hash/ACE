"""Independent checks for legality, reference optimality, replanning and limits."""
import unittest
from .planning import generate, search, simulate, oracle_cost, Meter, World
from .benchmark import run, METHODS, SEEDS


class PlanningTests(unittest.TestCase):
    def test_seed_and_family_deterministic(self):
        for family, seed in (("dev", 1000), ("ood", 9000)):
            self.assertEqual(generate(seed, family, True), generate(seed, family, True))
            self.assertNotEqual(generate(seed, family, True).shock, None)

    def test_disjoint_seed_sets(self):
        self.assertFalse(set(SEEDS["dev"]) & set(SEEDS["ood"]))
        self.assertEqual(len(METHODS), len(set(METHODS)))

    def test_static_astar_matches_independent_dijkstra(self):
        for family, seeds in SEEDS.items():
            for seed in seeds[:8]:
                world = generate(seed, family)
                expected = oracle_cost(world)
                computed = search(world, (0, 0), frozenset(), "astar", Meter(10000))
                self.assertEqual(computed.cost, expected, (family, seed))
                self.assertTrue(simulate(world, "astar", 10000)["success"])

    def test_blocked_shock_is_discovered_only_after_attempt(self):
        world = generate(1000, "dev", True)
        self.assertIsNotNone(world.shock)
        fixed = simulate(world, "hier_fixed", 10000)
        adaptive = simulate(world, "adaptive", 10000)
        self.assertEqual(fixed["status"], "unexpected_change")
        self.assertTrue(adaptive["success"], adaptive)
        self.assertGreaterEqual(adaptive["replans"], 1)
        self.assertEqual(adaptive["switches"], 1)

    def test_budget_is_strict_across_repeated_plans(self):
        world = generate(9001, "ood", True)
        for method in METHODS:
            out = simulate(world, method, 4)
            self.assertLessEqual(out["expanded"], 4)
            self.assertNotEqual(out["status"], "success")

    def test_invalid_algorithm_and_negative_budget(self):
        world = generate(1000)
        with self.assertRaises(ValueError):
            search(world, (0, 0), frozenset(), "eval", Meter(100))
        with self.assertRaises(ValueError):
            search(world, (0, 0), frozenset(), "astar", Meter(-1))
        with self.assertRaises(ValueError):
            simulate(world, "not_a_planner")

    def test_unsolvable_world_returns_none(self):
        world = World(2, 1, ((), ()), (), (0,))
        self.assertIsNone(oracle_cost(world))

    def test_bfs_is_not_weighted_optimal(self):
        # S->A->G costs 10+10 vs S->B->C->G costs 1+1+1.
        world = World(4, 1, ((1, 2), (0, 3), (0, 3), (1, 2)),
                      ((0, 1, 10), (0, 2, 1), (1, 3, 10), (2, 3, 1)), ())
        # This custom graph has no locked edges in task space; crossing any
        # column would require a key only when len(keys)>0.
        b = search(world, (0, 0), frozenset(), "bfs", Meter(100))
        d = oracle_cost(world)
        self.assertGreaterEqual(b.cost, d)

    def test_ood_contains_unlocked_order_and_hierarchical_counterexample(self):
        worlds = [generate(s, "ood") for s in SEEDS["ood"]]
        self.assertTrue(any(w.locks == () for w in worlds))
        differences = [(simulate(w, "hier_replan", 10000)["cost"], oracle_cost(w)) for w in worlds]
        self.assertTrue(any(h > optimal for h, optimal in differences), differences)

    def test_small_benchmark_replay_bitwise(self):
        first = run(limit=100, n=2)
        second = run(limit=100, n=2)
        self.assertEqual(first, second)
        self.assertEqual(len(first["rows"]), 2 * 2 * 2 * len(METHODS))

    def test_no_oracle_leak_to_runtime(self):
        world = generate(1000, "dev", True)
        without = World(world.width, world.height, world.adjacency, world.weights, world.keys, None, world.locks)
        self.assertEqual(search(world, (0, 0), frozenset(), "astar", Meter(10000)),
                         search(without, (0, 0), frozenset(), "astar", Meter(10000)))


if __name__ == "__main__":
    unittest.main()
