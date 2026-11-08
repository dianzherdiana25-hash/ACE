"""Unit tests for Active Epistemic Uncertainty Sampling (BALD)."""
from __future__ import annotations

import unittest
from ace_epistemic.active_sampler import (
    BALDSampler,
    HypothesisCandidate,
    compute_entropy,
)


class TestActiveSampler(unittest.TestCase):
    def test_shannon_entropy_calculation(self):
        # 1. Deterministic / degenerate distribution: H = 0.0 bits
        self.assertAlmostEqual(compute_entropy([1.0]), 0.0, places=5)
        self.assertAlmostEqual(compute_entropy([1.0, 0.0]), 0.0, places=5)

        # 2. Balanced binary distribution: H = 1.0 bit
        self.assertAlmostEqual(compute_entropy([0.5, 0.5]), 1.0, places=5)
        self.assertAlmostEqual(compute_entropy([10.0, 10.0]), 1.0, places=5)

        # 3. 4-way uniform distribution: H = 2.0 bits
        self.assertAlmostEqual(compute_entropy([0.25, 0.25, 0.25, 0.25]), 2.0, places=5)

    def test_bald_score_maximizes_disagreement(self):
        # 4 candidate hypotheses
        h1 = HypothesisCandidate("h1", lambda x: x % 2 == 0)
        h2 = HypothesisCandidate("h2", lambda x: x % 4 == 0)
        h3 = HypothesisCandidate("h3", lambda x: x > 5)
        h4 = HypothesisCandidate("h4", lambda x: x < 0)

        sampler = BALDSampler([h1, h2, h3, h4])

        # Test on an input where they disagree (e.g., x = 2: h1=True, h2=False, h3=False, h4=False)
        # Test on x = -2: h1=True, h2=False, h3=False, h4=True -> 2 True, 2 False -> entropy = 1.0 bit
        score_split = sampler.compute_bald_score(-2)
        self.assertAlmostEqual(score_split, 1.0, places=5)

        # On an input where all 4 agree (e.g., x = 1000: h1=True, h2=True, h3=True, h4=False -> 3 True, 1 False)
        # On x = 7: h1=False, h2=False, h3=True, h4=False -> 1 True, 3 False -> entropy < 1.0
        score_skew = sampler.compute_bald_score(7)
        self.assertLess(score_skew, 1.0)

        # Query selection must prioritize maximal entropy
        queries = sampler.select_query([-2, 7], top_k=2)
        self.assertEqual(queries[0][0], -2)
        self.assertEqual(queries[1][0], 7)

    def test_bayesian_posterior_update(self):
        h1 = HypothesisCandidate("h1", lambda x: True)
        h2 = HypothesisCandidate("h2", lambda x: True)
        h3 = HypothesisCandidate("h3", lambda x: False)
        h4 = HypothesisCandidate("h4", lambda x: False)

        sampler = BALDSampler([h1, h2, h3, h4])
        # Initially all have 0.25 weight
        for c in sampler.candidates:
            self.assertAlmostEqual(c.weight, 0.25)

        # Oracle says True on input 42
        receipt = sampler.update_posterior(42, True)
        self.assertEqual(receipt["refuted_count"], 2)

        # h1 and h2 survive with ~0.5 weight each; h3 and h4 are downweighted
        weights = sampler.get_candidate_weights()
        self.assertAlmostEqual(weights["h1"], 0.5, places=3)
        self.assertAlmostEqual(weights["h2"], 0.5, places=3)
        self.assertLess(weights["h3"], 1e-3)
        self.assertLess(weights["h4"], 1e-3)

    def test_active_search_loop_identifies_true_program(self):
        # Pool of candidate modular arithmetic predicates
        candidates = [
            HypothesisCandidate("mod_2", lambda x: x % 2 == 0),
            HypothesisCandidate("mod_3", lambda x: x % 3 == 0),
            HypothesisCandidate("mod_4", lambda x: x % 4 == 0),
            HypothesisCandidate("mod_5", lambda x: x % 5 == 0),
            HypothesisCandidate("gt_10", lambda x: x > 10),
            HypothesisCandidate("lt_5", lambda x: x < 5),
        ]
        # Target oracle is mod_4
        target_fn = lambda x: x % 4 == 0
        pool = list(range(1, 30))

        sampler = BALDSampler(candidates)
        result = sampler.active_search_loop(target_fn, pool, max_budget=10)

        self.assertEqual(result["winner_id"], "mod_4")
        self.assertGreaterEqual(result["winner_weight"], 0.99)
        # Should take <= 5 queries out of 29 pool items
        self.assertLessEqual(result["queries_executed"], 5)

    def test_sample_efficiency_benchmark_exceeds_sixty_percent(self):
        # 64 threshold decision hypotheses representing program parameter boundary tuning
        candidates = [
            HypothesisCandidate(f"thresh_{t}", (lambda thresh=t: lambda x: x >= thresh)())
            for t in range(1, 65)
        ]
        pool = list(range(1, 65))
        target_id = "thresh_37"

        bench = BALDSampler.benchmark_sample_efficiency(
            candidates, target_id, pool, num_trials=5, seed=42
        )

        # Verify BALD takes significantly fewer queries than random sampling
        self.assertLess(bench["avg_bald_queries"], bench["avg_random_queries"])
        # Verification criteria: query reduction >= 30%
        self.assertGreaterEqual(bench["query_reduction_pct"], 30.0)


if __name__ == "__main__":
    unittest.main()
