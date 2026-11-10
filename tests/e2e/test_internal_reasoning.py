"""E2E Test Suite: Internal Reasoning Distinguished from External AI (Requirement 5).

4-Tier Systematic Verification:
Tier 1: Feature Coverage (symbolic DPLL SAT, QF-LIA linear integer arithmetic solving)
Tier 2: Boundary & Corner Cases (arithmetic contradictions, empty clauses, Chvátal-Gomory GCD tightening)
Tier 3: Cross-Feature Interactions (formal verification with pre/post specifications, counterexample extraction)
Tier 4: Real-World Scenarios (internal mathematical proof vs external advisory string verification)
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

# Ensure ACE/code is on sys.path
_CODE_DIR = Path(__file__).resolve().parent.parent.parent / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from ace_smt.dpllt_solver import (
    Add,
    Assign,
    Const,
    DPLLTSolver,
    Ge,
    Gt,
    IfThenElse,
    Le,
    LinearConstraint,
    Literal,
    Lt,
    SMTResult,
    Sub,
    Var,
    VerificationResult,
    verify_program_satisfies_spec,
)


class TestInternalReasoningE2E(unittest.TestCase):
    """End-to-end verification of internal symbolic reasoning engine."""

    def setUp(self):
        self.solver = DPLLTSolver()

    # -------------------------------------------------------------------------
    # Tier 1: Feature Coverage (Happy Path)
    # -------------------------------------------------------------------------

    def test_tier1_pure_boolean_sat_satisfaction(self):
        """Verify DPLL solver finds a satisfying assignment for pure propositional CNF."""
        # Formula: (A \/ B) /\ (~A \/ B) /\ (A \/ ~B)
        # Unique satisfying assignment: A=True, B=True
        clauses = [
            [Literal("A", True), Literal("B", True)],
            [Literal("A", False), Literal("B", True)],
            [Literal("A", True), Literal("B", False)],
        ]
        result = self.solver.solve(clauses, theory_atoms={})
        self.assertTrue(result.is_sat)
        self.assertIsNotNone(result.boolean_assignment)
        self.assertTrue(result.boolean_assignment.get("A"))
        self.assertTrue(result.boolean_assignment.get("B"))

    def test_tier1_linear_integer_arithmetic_satisfaction_and_model(self):
        """Verify DPLL(T) solves consistent QF-LIA linear integer constraints and synthesizes concrete model."""
        # Constraints:
        # a1: x >= 2  <=>  -x <= -2
        # a2: y >= 3  <=>  -y <= -3
        # a3: x + y <= 10
        theory_atoms = {
            "a1": LinearConstraint.from_ge({"x": 1}, 2, "a1"),
            "a2": LinearConstraint.from_ge({"y": 1}, 3, "a2"),
            "a3": LinearConstraint.from_le({"x": 1, "y": 1}, 10, "a3"),
        }
        # CNF: a1 /\ a2 /\ a3
        clauses = [
            [Literal("a1", True)],
            [Literal("a2", True)],
            [Literal("a3", True)],
        ]
        result = self.solver.solve(clauses, theory_atoms)
        self.assertTrue(result.is_sat)
        self.assertIsNotNone(result.integer_model)
        x_val = result.integer_model["x"]
        y_val = result.integer_model["y"]
        self.assertGreaterEqual(x_val, 2)
        self.assertGreaterEqual(y_val, 3)
        self.assertLessEqual(x_val + y_val, 10)

    # -------------------------------------------------------------------------
    # Tier 2: Boundary & Corner Cases
    # -------------------------------------------------------------------------

    def test_tier2_infeasible_integer_bounds_return_unsat(self):
        """Verify conflicting integer bounds (x >= 5 and x <= 3) trigger UNSAT via Fourier-Motzkin elimination."""
        # a1: x >= 5  <=>  -x <= -5
        # a2: x <= 3  <=>   x <= 3
        theory_atoms = {
            "a1": LinearConstraint.from_ge({"x": 1}, 5, "a1"),
            "a2": LinearConstraint.from_le({"x": 1}, 3, "a2"),
        }
        clauses = [
            [Literal("a1", True)],
            [Literal("a2", True)],
        ]
        result = self.solver.solve(clauses, theory_atoms)
        self.assertFalse(result.is_sat)
        self.assertIsNone(result.integer_model)

    def test_tier2_propositional_contradiction_returns_unsat(self):
        """Verify contradictory unit clauses (A and ~A) immediately return UNSAT."""
        clauses = [
            [Literal("A", True)],
            [Literal("A", False)],
        ]
        result = self.solver.solve(clauses, theory_atoms={})
        self.assertFalse(result.is_sat)

    def test_tier2_chvatal_gomory_gcd_tightening(self):
        """Verify 2x + 4y <= 7 tightens to x + 2y <= 3 using Chvátal-Gomory integer reduction."""
        c = LinearConstraint.create({"x": 2, "y": 4}, 7, "atom_gcd")
        self.assertEqual(c.coeffs, {"x": 1, "y": 2})
        self.assertEqual(c.const, 3)  # floor(7 / 2) = 3

    # -------------------------------------------------------------------------
    # Tier 3: Cross-Feature Interactions
    # -------------------------------------------------------------------------

    def test_tier3_formal_program_verifier_proves_safe_specification(self):
        """Verify FormalProgramVerifier mathematically proves program correctness against postcondition."""
        # Program:
        # y = x + 1
        # if x >= 0:
        #     z = y + 1
        # else:
        #     z = y + 5
        # Precondition: x >= 0
        # Postcondition: z >= 2
        ast_prog = [
            Assign("y", Add(Var("x"), 1)),
            IfThenElse(
                Ge(Var("x"), 0),
                Assign("z", Add(Var("y"), 1)),
                Assign("z", Add(Var("y"), 5)),
            ),
        ]
        pre = Ge(Var("x"), 0)
        post = Ge(Var("z"), 2)

        res = verify_program_satisfies_spec(ast_prog, pre_cond=pre, post_cond=post)
        self.assertIsInstance(res, VerificationResult)
        self.assertTrue(res.is_valid, "Specification should be proven formally!")
        self.assertIsNone(res.counterexample)

    def test_tier3_formal_program_verifier_extracts_counterexample_when_spec_violated(self):
        """Verify FormalProgramVerifier generates a concrete counterexample when postcondition can fail."""
        # Program:
        # z = x - 5
        # Precondition: x <= 10
        # Postcondition: z >= 0   (Can be violated when x = 0, giving z = -5)
        ast_prog = [
            Assign("z", Sub(Var("x"), 5)),
        ]
        pre = Le(Var("x"), 10)
        post = Ge(Var("z"), 0)

        res = verify_program_satisfies_spec(ast_prog, pre_cond=pre, post_cond=post)
        self.assertIsInstance(res, VerificationResult)
        self.assertFalse(res.is_valid, "Specification should be violated!")
        self.assertIsNotNone(res.counterexample)

    # -------------------------------------------------------------------------
    # Tier 4: Real-World Scenarios
    # -------------------------------------------------------------------------

    def test_tier4_internal_reasoning_gate_rejects_unproven_candidate_claims(self):
        """Simulate internal reasoning validation: require SMT proof before accepting candidate mechanism."""
        # Simulated unverified external proposal: claims z = x - 2 satisfies z > 0 for all x >= 0.
        # The internal solver independently verifies this claim and disproves it (counterexample e.g. x = 0 or 1).
        check_ast = [
            Assign("z", Sub(Var("x"), 2)),
        ]
        pre = Ge(Var("x"), 0)
        post = Gt(Var("z"), 0)

        verification = verify_program_satisfies_spec(check_ast, pre_cond=pre, post_cond=post)
        self.assertFalse(verification.is_valid, "Unsound external AI claim must be disproven by internal reasoning!")
        self.assertIsNotNone(verification.counterexample)


if __name__ == "__main__":
    unittest.main()
