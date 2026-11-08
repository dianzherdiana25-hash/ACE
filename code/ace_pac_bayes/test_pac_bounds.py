"""Unit tests for PAC-Bayesian Generalization Bound Estimation."""
from __future__ import annotations

import math
import random
import unittest
from ace_pac_bayes.pac_bounds import (
    PACBayesCertifier,
    ProgramEnsembleDistribution,
    binary_kl,
    catoni_bound,
    invert_binary_kl,
    mcallester_bound,
    seeger_maurer_bound,
)


class TestPACBayesBounds(unittest.TestCase):
    def test_binary_kl_properties(self):
        # 1. Identity: kl(p || p) = 0
        self.assertAlmostEqual(binary_kl(0.5, 0.5), 0.0, places=6)
        self.assertAlmostEqual(binary_kl(0.2, 0.2), 0.0, places=6)
        self.assertAlmostEqual(binary_kl(0.0, 0.0), 0.0, places=6)

        # 2. Analytical check: kl(0 || 0.5) = -ln(0.5) = ln(2)
        self.assertAlmostEqual(binary_kl(0.0, 0.5), math.log(2.0), places=5)

        # 3. Non-negativity & monotonicity
        self.assertGreater(binary_kl(0.1, 0.5), binary_kl(0.1, 0.2))
        self.assertGreaterEqual(binary_kl(0.8, 0.2), 0.0)

    def test_invert_binary_kl(self):
        # 1. Epsilon = 0 returns q
        self.assertAlmostEqual(invert_binary_kl(0.2, 0.0), 0.2, places=6)

        # 2. Analytical inversion for q = 0: kl(0 || p) = -ln(1 - p) = eps ==> p = 1 - exp(-eps)
        eps = 0.5
        expected_p = 1.0 - math.exp(-eps)
        p_root = invert_binary_kl(0.0, eps)
        self.assertAlmostEqual(p_root, expected_p, places=5)

        # 3. For any q and eps, kl(q || p_root) should be within tol of eps
        for q in [0.05, 0.1, 0.3, 0.6]:
            root = invert_binary_kl(q, 0.4)
            self.assertGreaterEqual(root, q)
            self.assertAlmostEqual(binary_kl(q, root), 0.4, places=4)

    def test_mcallester_and_seeger_maurer_bounds(self):
        m = 100
        kl = 1.5
        delta = 0.05

        for r_hat in [0.0, 0.05, 0.1, 0.25]:
            b_mc = mcallester_bound(r_hat, kl, m, delta)
            b_seeger = seeger_maurer_bound(r_hat, kl, m, delta)
            b_catoni = catoni_bound(r_hat, kl, m, delta)

            # Basic sanity: bound in [r_hat, 1.0]
            self.assertGreaterEqual(b_mc, r_hat)
            self.assertLessEqual(b_mc, 1.0)
            self.assertGreaterEqual(b_seeger, r_hat)
            self.assertLessEqual(b_seeger, 1.0)

            # Known theorem: Seeger-Maurer bound is uniformly tighter than or equal to McAllester
            self.assertLessEqual(b_seeger, b_mc + 1e-6)

        # Monotonicity with sample size m: bound tightens as m increases
        b_m100 = seeger_maurer_bound(0.05, 1.0, 100, 0.05)
        b_m500 = seeger_maurer_bound(0.05, 1.0, 500, 0.05)
        b_m2000 = seeger_maurer_bound(0.05, 1.0, 2000, 0.05)
        self.assertGreater(b_m100, b_m500)
        self.assertGreater(b_m500, b_m2000)

    def test_program_ensemble_distribution_and_certificate(self):
        # 4 synthesized program candidates
        # Target concept: x is divisible by 3 and x > 10
        target = lambda x: (x % 3 == 0) and (x > 10)

        prog_good = target
        prog_close = lambda x: x % 3 == 0
        prog_coarse = lambda x: x > 10
        prog_bad = lambda x: x % 2 == 0

        programs = [prog_good, prog_close, prog_coarse, prog_bad]
        # Prior penalizing program complexity (MDL): 2^-depth
        prior = [0.4, 0.3, 0.2, 0.1]

        ensemble = ProgramEnsembleDistribution(
            program_ids=["good", "close", "coarse", "bad"],
            programs=programs,
            prior_weights=prior,
        )

        # Training dataset of 150 points
        rng = random.Random(42)
        train_data = [(x, target(x)) for x in [rng.randint(1, 100) for _ in range(150)]]

        certifier = PACBayesCertifier(delta=0.05)
        cert = certifier.certify(ensemble, train_data, temperature=0.5)

        # Verified properties
        self.assertTrue(cert["seeger_strictly_tighter"])
        self.assertLess(cert["empirical_risk_R_hat"], 0.05)
        # Certified population risk bound should be tight (< 0.20 on m=150)
        self.assertLess(cert["certified_bound"], 0.20)
        self.assertGreaterEqual(cert["certified_bound"], cert["empirical_risk_R_hat"])

    def test_soundness_against_true_population_risk(self):
        """Empirically verifies that true population risk exceeds the PAC-Bayes bound
        with frequency <= delta = 0.05 across random sample draws.
        """
        target = lambda x: (x % 4 == 0)
        candidates = [
            lambda x: x % 4 == 0,      # Perfect
            lambda x: x % 2 == 0,      # Slightly noisy
            lambda x: x > 50,          # Suboptimal
        ]

        prior = [0.5, 0.3, 0.2]
        delta = 0.05
        m_train = 120

        # Construct a large ground-truth population of 5000 items
        rng = random.Random(999)
        population = [(x, target(x)) for x in range(1, 5001)]

        # True population risk for each program
        true_indiv_risks = [
            sum(0.0 if p(x) == y else 1.0 for x, y in population) / len(population)
            for p in candidates
        ]

        violations = 0
        num_trials = 25

        for trial in range(num_trials):
            trial_train = [population[rng.randint(0, len(population) - 1)] for _ in range(m_train)]
            ens = ProgramEnsembleDistribution(["c1", "c2", "c3"], candidates, prior)

            certifier = PACBayesCertifier(delta=delta)
            cert = certifier.certify(ens, trial_train, temperature=0.2)

            true_q_risk = ens.compute_expected_empirical_risk(true_indiv_risks)
            if true_q_risk > cert["certified_bound"]:
                violations += 1

        # Violation rate must be <= delta (at most 1 or 2 out of 25)
        self.assertLessEqual(violations, math.ceil(num_trials * delta) + 1)


if __name__ == "__main__":
    unittest.main()
