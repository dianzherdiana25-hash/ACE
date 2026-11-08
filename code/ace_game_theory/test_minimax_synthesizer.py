"""Unit tests for Game-Theoretic Minimax Adversarial Synthesis (No-Regret Co-Evolution)."""
from __future__ import annotations

import unittest
from ace_game_theory.minimax_synthesizer import (
    HedgePlayer,
    MinimaxCoEvolution,
    TwoPlayerGameMatrix,
    compute_nash_gap,
)


class TestMinimaxSynthesizer(unittest.TestCase):
    def test_game_matrix_and_duality_gap(self):
        # 2x2 matrix
        matrix = [
            [1.0, 0.0],
            [0.0, 1.0],
        ]
        game = TwoPlayerGameMatrix(matrix)

        # Expected payoff of uniform [0.5, 0.5] vs [0.5, 0.5]
        p_unif = [0.5, 0.5]
        q_unif = [0.5, 0.5]
        payoff = game.expected_payoff(p_unif, q_unif)
        self.assertAlmostEqual(payoff, 0.5)

        # Duality gap at Nash equilibrium is 0
        gap = compute_nash_gap(matrix, p_unif, q_unif)
        self.assertAlmostEqual(gap, 0.0)

        # Suboptimal strategy has positive gap
        p_pure = [1.0, 0.0]
        q_pure = [1.0, 0.0]
        gap_pure = compute_nash_gap(matrix, p_pure, q_pure)
        self.assertGreater(gap_pure, 0.0)

    def test_minimax_convergence_on_matching_pennies(self):
        # Matching Pennies game: unique Nash equilibrium is (0.5, 0.5) with V* = 0.5
        matrix = [
            [1.0, 0.0],
            [0.0, 1.0],
        ]
        game = TwoPlayerGameMatrix(matrix)
        engine = MinimaxCoEvolution(game)

        result = engine.solve(rounds=300)

        self.assertTrue(result["is_epsilon_nash"])
        self.assertLess(result["duality_gap"], 0.08)
        self.assertAlmostEqual(result["game_value_V"], 0.5, delta=0.08)

        # Mixed strategies should be close to 0.5
        p_bar = result["synthesizer_mixed_strategy"]
        q_bar = result["adversary_mixed_strategy"]
        self.assertAlmostEqual(p_bar[0], 0.5, delta=0.08)
        self.assertAlmostEqual(q_bar[0], 0.5, delta=0.08)

    def test_sublinear_regret_and_gap_decay(self):
        # Asymmetric 3x3 game matrix where initial uniform distribution is non-equilibrium
        matrix = [
            [1.0, 0.2, 0.8],
            [0.1, 0.9, 0.4],
            [0.7, 0.3, 0.6],
        ]
        game = TwoPlayerGameMatrix(matrix)
        engine = MinimaxCoEvolution(game)

        # As rounds increase from 20 to 300, duality gap strictly decreases (rate O(1/sqrt(T)))
        res_short = engine.solve(rounds=20)
        res_long = engine.solve(rounds=300)

        self.assertGreater(res_short["duality_gap"], res_long["duality_gap"])
        self.assertLess(res_long["duality_gap"], 0.05)
        self.assertTrue(res_long["is_epsilon_nash"])

    def test_program_synthesis_adversarial_red_teaming(self):
        # Candidate programs:
        # P0: fails on negative
        # P1: fails on zero
        # P2: fails on large numbers
        # P3: robust program (succeeds on all categories)
        programs = [
            lambda x: 1 if x > 0 else 0,              # Fails on negative
            lambda x: 1 if x != 0 else 0,             # Fails on zero
            lambda x: 1 if abs(x) < 50 else 0,        # Fails on large
            lambda x: 1,                              # Always succeeds
        ]

        # Adversary input generators:
        test_inputs = [
            10,    # Regular
            -5,    # Negative
            0,     # Zero
            100,   # Large
        ]

        # Target ground truth oracle is constant 1
        def oracle_loss(prog, x):
            pred = prog(x)
            return 0.0 if pred == 1 else 1.0

        engine = MinimaxCoEvolution.from_programs_and_inputs(
            programs=programs,
            adversarial_inputs=test_inputs,
            oracle_evaluator=oracle_loss,
        )

        result = engine.solve(rounds=200)

        p_weights = result["synthesizer_mixed_strategy"]
        # The robust program (P3) should have the dominant mass
        self.assertGreater(p_weights[3], p_weights[0])
        self.assertGreater(p_weights[3], p_weights[1])
        self.assertGreater(p_weights[3], p_weights[2])
        # Minimax robust loss should be near zero because P3 has zero loss on all inputs
        self.assertLess(result["game_value_V"], 0.15)


if __name__ == "__main__":
    unittest.main()
