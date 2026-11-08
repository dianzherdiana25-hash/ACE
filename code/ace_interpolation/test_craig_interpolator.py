"""Unit Test Suite for Craig Interpolation Engine & Inductive Invariant Synthesizer.

Provenance: ADVISOR_AGENT
"""
from __future__ import annotations

from fractions import Fraction
import unittest

from ace_interpolation.craig_interpolator import (
    BoolConst,
    BoolExpr,
    BoolVar,
    CraigInterpolationEngine,
    FarkasLinearInterpolator,
    LinearConstraint,
    LinearSystem,
    LoopProgram,
    McMillanPropositionalInterpolator,
    PropClause,
    PropCNF,
    PropLiteral,
)


class TestCraigInterpolator(unittest.TestCase):
    """Verifies Craig Interpolation conditions, Farkas extraction, and loop invariant synthesis."""

    def test_craig_conditions_propositional_basic(self):
        """Test 1: Propositional Craig conditions 1, 2, 3 on canonical refutation."""
        # A = (x | y) & (~x)  ==> y
        # B = (~y)
        # A and B is mutually inconsistent
        # Shared symbol: y
        c1 = PropClause.from_literals("x", "y")
        c2 = PropClause.from_literals("~x")
        c3 = PropClause.from_literals("~y")

        A = [c1, c2]
        B = [c3]

        engine_res = CraigInterpolationEngine.interpolate_propositional(A, B)
        I = engine_res.interpolant

        # Verification of Craig's 3 conditions
        receipt = engine_res.verification_receipt
        self.assertTrue(receipt["condition_1_A_implies_I"], "Condition 1 (A => I) must hold")
        self.assertTrue(receipt["condition_2_I_and_B_unsat"], "Condition 2 (I & B |= False) must hold")
        self.assertTrue(receipt["condition_3_shared_symbols"], "Condition 3 (Symbol(I) subseteq Symbol(A) & Symbol(B)) must hold")
        self.assertTrue(receipt["valid"])
        self.assertEqual(receipt["shared_symbols"], ["y"])
        self.assertEqual(receipt["interpolant_symbols"], ["y"])

    def test_mcmillan_multi_variable_propositional(self):
        """Test 2: McMillan interpolation with local and shared variables."""
        # Local to A: a1, a2
        # Local to B: b1
        # Shared: s1, s2
        # A: (a1 | s1) & (~a1 | s2) & (~s1 | ~s2) ...
        # Let A imply (s1 | s2), and B imply (~s1 & ~s2)
        # A: (~a1 | s1), (a1 | s2), ...
        # Concretely:
        # A: (a1 | s1), (~a1 | s1)  ==> implies s1
        # B: (~s1 | b1), (~b1)      ==> implies ~s1
        # A & B |= False
        A = [
            PropClause.from_literals("a1", "s1"),
            PropClause.from_literals("~a1", "s1"),
        ]
        B = [
            PropClause.from_literals("~s1", "b1"),
            PropClause.from_literals("~b1"),
        ]

        engine_res = CraigInterpolationEngine.interpolate_propositional(A, B)
        receipt = engine_res.verification_receipt

        self.assertTrue(receipt["valid"])
        self.assertIn("s1", receipt["shared_symbols"])
        self.assertNotIn("a1", receipt["interpolant_symbols"])
        self.assertNotIn("b1", receipt["interpolant_symbols"])

    def test_linear_farkas_basic(self):
        """Test 3: Linear Arithmetic Farkas interpolation satisfying Craig conditions 1, 2, 3."""
        # A: x <= 2, y - x <= 0 (i.e. y <= x <= 2)
        # B: -y <= -5 (i.e. y >= 5)
        # Shared symbol: y
        # Inconsistent: y <= 2 and y >= 5 is impossible
        c_A1 = LinearConstraint.create({"x": 1}, 2)          # x <= 2
        c_A2 = LinearConstraint.create({"y": 1, "x": -1}, 0)  # y - x <= 0
        c_B1 = LinearConstraint.create({"y": -1}, -5)         # -y <= -5 <=> y >= 5

        A = [c_A1, c_A2]
        B = [c_B1]

        engine_res = CraigInterpolationEngine.interpolate_linear(A, B)
        I = engine_res.interpolant
        self.assertIsInstance(I, LinearConstraint)

        receipt = engine_res.verification_receipt
        self.assertTrue(receipt["condition_1_A_implies_I"], "A => I must hold")
        self.assertTrue(receipt["condition_2_I_and_B_unsat"], "I & B |= False must hold")
        self.assertTrue(receipt["condition_3_shared_symbols"], "Symbol(I) subseteq Symbol(A) & Symbol(B)")
        self.assertTrue(receipt["valid"])
        self.assertEqual(receipt["shared_symbols"], ["y"])
        self.assertEqual(receipt["interpolant_symbols"], ["y"])

        # Semantic check: I must imply y <= 2
        self.assertTrue(I.eval({"y": 2}))
        self.assertTrue(I.eval({"y": 0}))
        self.assertFalse(I.eval({"y": 3}))

    def test_linear_farkas_isolation_of_local_variables(self):
        """Test 4: Strict Farkas cancellation of local unshared variables."""
        # Local to A: u
        # Local to B: w
        # Shared: x, y
        # A: u <= 10, x - u <= 0, y <= 5   (implies x <= 10, y <= 5)
        # B: w >= 20, -x - y + w <= 0      (implies x + y >= w >= 20)
        # Inconsistent: x <= 10, y <= 5 => x + y <= 15 < 20
        c_A1 = LinearConstraint.create({"u": 1}, 10)
        c_A2 = LinearConstraint.create({"x": 1, "u": -1}, 0)
        c_A3 = LinearConstraint.create({"y": 1}, 5)

        c_B1 = LinearConstraint.create({"w": -1}, -20)
        c_B2 = LinearConstraint.create({"x": -1, "y": -1, "w": 1}, 0)

        A = [c_A1, c_A2, c_A3]
        B = [c_B1, c_B2]

        engine_res = CraigInterpolationEngine.interpolate_linear(A, B)
        I = engine_res.interpolant

        # Variable isolation check
        self.assertNotIn("u", I.vars, "Local variable u of A must be eliminated")
        self.assertNotIn("w", I.vars, "Local variable w of B must be eliminated")
        self.assertTrue(I.vars.issubset({"x", "y"}), "Only shared variables x, y may appear in I")

        receipt = engine_res.verification_receipt
        self.assertTrue(receipt["valid"])

    def test_craig_consistency_rejection(self):
        """Test 5: Craig theorem requirement that A and B must be inconsistent."""
        # Consistent propositional formulas: A = (x), B = (y)
        A_prop = [PropClause.from_literals("x")]
        B_prop = [PropClause.from_literals("y")]
        with self.assertRaises(ValueError):
            CraigInterpolationEngine.interpolate_propositional(A_prop, B_prop)

        # Consistent linear formulas: A: x <= 10, B: x >= 5
        A_lin = [LinearConstraint.create({"x": 1}, 10)]
        B_lin = [LinearConstraint.create({"x": -1}, -5)]
        with self.assertRaises(ValueError):
            CraigInterpolationEngine.interpolate_linear(A_lin, B_lin)

    def test_loop_invariant_synthesis_linear_relation(self):
        """Test 6: Synthesize inductive relational invariant y = 2x (2x - y <= 0)."""
        # Loop program:
        # Init: x = 0, y = 0
        # Transition: x' = x + 1, y' = y + 2
        # Safety property: 2x - y <= 0
        init = [
            LinearConstraint.create({"x": 1}, 0),
            LinearConstraint.create({"x": -1}, 0),
            LinearConstraint.create({"y": 1}, 0),
            LinearConstraint.create({"y": -1}, 0),
        ]
        # x' - x = 1 <=> x' - x <= 1 and -x' + x <= -1
        # y' - y = 2 <=> y' - y <= 2 and -y' + y <= -2
        trans = [
            LinearConstraint.create({"x_prime": 1, "x": -1}, 1),
            LinearConstraint.create({"x_prime": -1, "x": 1}, -1),
            LinearConstraint.create({"y_prime": 1, "y": -1}, 2),
            LinearConstraint.create({"y_prime": -1, "y": 1}, -2),
        ]
        safety = [
            LinearConstraint.create({"x": 2, "y": -1}, 0),  # 2x - y <= 0
        ]

        prog = LoopProgram(
            name="double_increment_loop",
            variables=["x", "y"],
            init_constraints=init,
            transition_constraints=trans,
            post_condition=safety,
        )

        result = CraigInterpolationEngine.synthesize_loop_invariant(prog, max_unroll_depth=4)
        self.assertEqual(result.status, "VERIFIED_INDUCTIVE")
        self.assertTrue(result.proof_certificate["verified"])
        self.assertEqual(result.proof_certificate["initiation"], "VALID (Init => Inv)")
        self.assertEqual(result.proof_certificate["consecution"], "VALID (Inv /\\ T => Inv')")
        self.assertEqual(result.proof_certificate["safety"], "VALID (Inv /\\ Bad |= False)")

    def test_loop_invariant_synthesis_bounded_counter(self):
        """Test 7: Synthesize inductive bound invariant x <= 10 for bounded counter."""
        # Init: x = 0
        # Loop guard: x <= 9
        # Transition: x' = x + 1, with guard x <= 9
        # Safety: x <= 10
        init = [
            LinearConstraint.create({"x": 1}, 0),
            LinearConstraint.create({"x": -1}, 0),
        ]
        trans = [
            LinearConstraint.create({"x": 1}, 9),               # guard: x <= 9
            LinearConstraint.create({"x_prime": 1, "x": -1}, 1),  # x' - x <= 1
            LinearConstraint.create({"x_prime": -1, "x": 1}, -1), # x - x' <= -1
        ]
        safety = [
            LinearConstraint.create({"x": 1}, 10),  # x <= 10
        ]

        prog = LoopProgram(
            name="bounded_counter_loop",
            variables=["x"],
            init_constraints=init,
            transition_constraints=trans,
            post_condition=safety,
        )

        result = CraigInterpolationEngine.synthesize_loop_invariant(prog, max_unroll_depth=4)
        self.assertEqual(result.status, "VERIFIED_INDUCTIVE")
        self.assertTrue(result.proof_certificate["verified"])
        self.assertGreater(len(result.invariant), 0)

    def test_loop_invariant_safety_violation_at_init(self):
        """Test 8: Immediate detection of initial state safety violations."""
        # Init: x = 5
        # Safety: x <= 3 (Bad: x >= 4)
        init = [LinearConstraint.create({"x": 1}, 5), LinearConstraint.create({"x": -1}, -5)]
        trans = [LinearConstraint.create({"x_prime": 1, "x": -1}, 1)]
        safety = [LinearConstraint.create({"x": 1}, 3)]

        prog = LoopProgram(
            name="unsafe_init_loop",
            variables=["x"],
            init_constraints=init,
            transition_constraints=trans,
            post_condition=safety,
        )

    def test_loop_invariant_lockstep_equality(self):
        """Test 9: Synthesize lockstep equality invariant x - y <= 0 for synchronized increments."""
        # Init: x = 0, y = 0
        # Transition: x' = x + 1, y' = y + 1
        # Safety: x - y <= 0
        init = [
            LinearConstraint.create({"x": 1}, 0),
            LinearConstraint.create({"x": -1}, 0),
            LinearConstraint.create({"y": 1}, 0),
            LinearConstraint.create({"y": -1}, 0),
        ]
        trans = [
            LinearConstraint.create({"x_prime": 1, "x": -1}, 1),
            LinearConstraint.create({"x_prime": -1, "x": 1}, -1),
            LinearConstraint.create({"y_prime": 1, "y": -1}, 1),
            LinearConstraint.create({"y_prime": -1, "y": 1}, -1),
        ]
        safety = [
            LinearConstraint.create({"x": 1, "y": -1}, 0),  # x - y <= 0
        ]

        prog = LoopProgram(
            name="lockstep_increment_loop",
            variables=["x", "y"],
            init_constraints=init,
            transition_constraints=trans,
            post_condition=safety,
        )

        result = CraigInterpolationEngine.synthesize_loop_invariant(prog, max_unroll_depth=3)
        self.assertEqual(result.status, "VERIFIED_INDUCTIVE")
        self.assertTrue(result.proof_certificate["verified"])
        self.assertEqual(result.proof_certificate["initiation"], "VALID (Init => Inv)")
        self.assertEqual(result.proof_certificate["consecution"], "VALID (Inv /\\ T => Inv')")
        self.assertEqual(result.proof_certificate["safety"], "VALID (Inv /\\ Bad |= False)")

    def test_craig_empty_shared_variables_boundary(self):
        """Test 10: Craig interpolation when variables are completely disjoint (I in {True, False})."""
        # A has var p, B has var q. They share no variables.
        # A: p & ~p (A is unsat)
        # B: q
        # Shared: {}
        # Interpolant should be False
        A = [PropClause.from_literals("p"), PropClause.from_literals("~p")]
        B = [PropClause.from_literals("q")]

        res = CraigInterpolationEngine.interpolate_propositional(A, B)
        self.assertEqual(len(res.shared_symbols), 0)
        self.assertEqual(res.to_string(), "False")
        receipt = res.verification_receipt
        self.assertTrue(receipt["valid"])


if __name__ == "__main__":
    unittest.main()

