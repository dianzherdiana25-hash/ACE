"""Unit tests for Causal Invariant Graph Mining & Pearl do-calculus."""
from __future__ import annotations

import unittest
from ace_causal.causal_miner import (
    CausalInvariantMiner,
    StructuralCausalModel,
    is_d_separated,
)


class TestCausalMiner(unittest.TestCase):
    def test_pearl_d_separation_graphical_criterion(self):
        # 1. Chain: X -> M -> Y
        chain = {"X": ["M"], "M": ["Y"], "Y": []}
        # Unconditioned: connected
        self.assertFalse(is_d_separated(chain, "X", "Y", set()))
        # Conditioned on mediator M: d-separated
        self.assertTrue(is_d_separated(chain, "X", "Y", {"M"}))

        # 2. Fork (Common Cause / Confounder): X <- C -> Y
        fork = {"C": ["X", "Y"], "X": [], "Y": []}
        # Unconditioned: correlated (not d-separated)
        self.assertFalse(is_d_separated(fork, "X", "Y", set()))
        # Conditioned on confounder C: d-separated
        self.assertTrue(is_d_separated(fork, "X", "Y", {"C"}))

        # 3. Collider (V-structure): X -> Collider <- Y
        collider = {"X": ["C"], "Y": ["C"], "C": []}
        # Unconditioned: d-separated (independent causes)
        self.assertTrue(is_d_separated(collider, "X", "Y", set()))
        # Conditioned on collider C: conditioning unblocks path (not d-separated)!
        self.assertFalse(is_d_separated(collider, "X", "Y", {"C"}))

    def test_scm_observational_vs_interventional_do_calculus(self):
        # SCM with Confounder C, Cause X, Target Y, and Co-effect W:
        # C := U_c
        # X := 2*C + U_x
        # W := 4*C + U_w   (Co-effect of C, correlated with Y, but does NOT cause Y)
        # Y := 3*X + C + U_y
        scm = StructuralCausalModel()
        scm.add_variable("C", [], lambda env, u: u)
        scm.add_variable("X", ["C"], lambda env, u: 2.0 * env["C"] + u)
        scm.add_variable("W", ["C"], lambda env, u: 4.0 * env["C"] + u)
        scm.add_variable("Y", ["X", "C"], lambda env, u: 3.0 * env["X"] + env["C"] + u)

        # 1. Observational: W is correlated with Y
        miner = CausalInvariantMiner(scm)
        obs = scm.sample(n=300, seed=42)
        corr_wy = miner.compute_observational_correlation("W", "Y", obs)
        self.assertGreater(abs(corr_wy), 0.5)

        # 2. Pearl do-calculus: Intervene on W (do(W = 100))
        # Y must remain unchanged because W does NOT cause Y
        effect_w = miner.measure_interventional_effect("W", "Y", -10.0, 10.0, n_samples=300)
        self.assertLess(effect_w, 0.3)

        # 3. Intervene on X (do(X = 10) vs do(X = -10))
        # Y = 3*X + C -> delta should be ~ 3 * 20 = 60
        effect_x = miner.measure_interventional_effect("X", "Y", -10.0, 10.0, n_samples=300)
        self.assertGreater(effect_x, 50.0)

    def test_zero_false_discovery_under_confounders(self):
        # SCM:
        # Z is a common confounder
        # X is true causal parent of Y
        # W1, W2 are co-effects / spurious correlates
        scm = StructuralCausalModel()
        scm.add_variable("Z", [], lambda env, u: u)
        scm.add_variable("X", ["Z"], lambda env, u: 1.5 * env["Z"] + u)
        scm.add_variable("W1", ["Z"], lambda env, u: 3.0 * env["Z"] + u)
        scm.add_variable("W2", ["Z"], lambda env, u: -2.0 * env["Z"] + u)
        scm.add_variable("Y", ["X", "Z"], lambda env, u: 2.0 * env["X"] + 1.0 * env["Z"] + u)

        miner = CausalInvariantMiner(scm)
        candidates = ["X", "W1", "W2", "Z"]

        result = miner.discover_causal_parents("Y", candidates, causal_effect_threshold=1.0, n_samples=300)

        # True causal parents must be X and Z
        self.assertIn("X", result["causal_parents"])
        self.assertIn("Z", result["causal_parents"])

        # Spurious co-effects W1 and W2 must be rejected
        self.assertNotIn("W1", result["causal_parents"])
        self.assertNotIn("W2", result["causal_parents"])
        self.assertIn("W1", result["spurious_confounders"])
        self.assertIn("W2", result["spurious_confounders"])

        # Zero false discovery rate verified
        self.assertTrue(result["zero_false_discovery"])

    def test_invariant_prediction_across_environments(self):
        scm = StructuralCausalModel()
        scm.add_variable("Env_Noise", [], lambda env, u: u)
        scm.add_variable("X1", ["Env_Noise"], lambda env, u: 2.0 * env["Env_Noise"] + u)
        scm.add_variable("X2", ["Env_Noise"], lambda env, u: 3.0 * env["Env_Noise"] + u)
        scm.add_variable("Y", ["X1", "X2"], lambda env, u: env["X1"] + env["X2"] + 0.1 * u)

        miner = CausalInvariantMiner(scm)
        # Shifted environments: perturbing exogenous background
        environments = [
            {"Env_Noise": 0.0},
            {"Env_Noise": 5.0},
            {"Env_Noise": -5.0},
        ]

        inv_check = miner.verify_invariant_prediction(["X1", "X2"], "Y", environments, n_samples=200)
        self.assertTrue(inv_check["is_invariant"])
        self.assertLess(inv_check["environment_variance"], 0.2)


if __name__ == "__main__":
    unittest.main()
