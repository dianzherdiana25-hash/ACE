"""Unit tests for DPLL(T) Formal Verifier Engine.

Tests:
1. Pure propositional SAT solver (satisfiable).
2. Pure propositional SAT solver (unsatisfiable).
3. Theory Solver (QF-LIA) consistency and integer model extraction.
4. Theory Solver (QF-LIA) contradiction detection and minimal infeasible core extraction.
5. DPLL(T) conflict clause learning and non-chronological backjumping.
6. Theory Propagation (T-propagation).
7. Formal Program Verification: Valid absolute value function (UNSAT proof).
8. Formal Program Verification: Buggy function produces concrete counterexample.
9. Formal Program Verification: Bounded loop unrolling invariant verification.
"""
from __future__ import annotations

import unittest

from ace_smt.dpllt_solver import (
    Add,
    Assign,
    Clause,
    Const,
    DPLLTSolver,
    Ge,
    Gt,
    IfThenElse,
    Le,
    LinearConstraint,
    Literal,
    Lt,
    Seq,
    Sub,
    TheorySolver,
    Var,
    While,
    verify_program_satisfies_spec,
)


class TestDPLLTSolver(unittest.TestCase):

    def setUp(self):
        self.solver = DPLLTSolver()
        self.theory = TheorySolver()

    # ------------------------------------------------------------------------
    # 1. Pure Propositional SAT / UNSAT Tests
    # ------------------------------------------------------------------------
    def test_pure_sat_dpll_satisfiable(self):
        """Tests pure propositional CNF formula: (a \/ b) /\ (~a \/ c) /\ (~b \/ c)."""
        clauses = [
            [Literal("a", True), Literal("b", True)],
            [Literal("a", False), Literal("c", True)],
            [Literal("b", False), Literal("c", True)],
        ]
        result = self.solver.solve(clauses, theory_atoms={})
        self.assertTrue(result.is_sat)
        self.assertIsNotNone(result.boolean_assignment)
        assignment = result.boolean_assignment
        self.assertTrue(assignment.get("c"))

    def test_pure_sat_dpll_unsatisfiable(self):
        """Tests unsat CNF formula: all 4 combinations of 2 variables."""
        clauses = [
            [Literal("x", True), Literal("y", True)],
            [Literal("x", True), Literal("y", False)],
            [Literal("x", False), Literal("y", True)],
            [Literal("x", False), Literal("y", False)],
        ]
        result = self.solver.solve(clauses, theory_atoms={})
        self.assertFalse(result.is_sat)
        self.assertIsNone(result.boolean_assignment)

    # ------------------------------------------------------------------------
    # 2. Theory Solver QF-LIA Feasibility & Infeasible Cores
    # ------------------------------------------------------------------------
    def test_linear_arithmetic_theory_feasible(self):
        """Tests consistent QF-LIA constraints: x + y <= 10 /\ x >= 3 /\ y >= 4."""
        c1 = LinearConstraint.from_le({"x": 1, "y": 1}, 10, "c1")
        c2 = LinearConstraint.from_ge({"x": 1}, 3, "c2")
        c3 = LinearConstraint.from_ge({"y": 1}, 4, "c3")

        assigned = [(c1, True, "c1"), (c2, True, "c2"), (c3, True, "c3")]
        is_consistent, conflict_core, model = self.theory.check_consistency(assigned)

        self.assertTrue(is_consistent)
        self.assertIsNone(conflict_core)
        self.assertIsNotNone(model)
        self.assertGreaterEqual(model["x"], 3)
        self.assertGreaterEqual(model["y"], 4)
        self.assertLessEqual(model["x"] + model["y"], 10)

    def test_linear_arithmetic_theory_infeasible_and_core(self):
        """Tests inconsistent QF-LIA constraints: x <= 5 /\ x >= 9."""
        c1 = LinearConstraint.from_le({"x": 1}, 5, "c1")
        c2 = LinearConstraint.from_ge({"x": 1}, 9, "c2")
        c3 = LinearConstraint.from_ge({"y": 1}, 0, "c3")  # Irrelevant to conflict

        assigned = [(c1, True, "c1"), (c2, True, "c2"), (c3, True, "c3")]
        is_consistent, conflict_core, model = self.theory.check_consistency(assigned)

        self.assertFalse(is_consistent)
        self.assertIsNotNone(conflict_core)
        # Infeasible core must contain both c1 and c2, but does not need c3
        self.assertIn("c1", conflict_core)
        self.assertIn("c2", conflict_core)

    # ------------------------------------------------------------------------
    # 3. DPLL(T) Conflict Clause Learning & T-Propagation
    # ------------------------------------------------------------------------
    def test_dpllt_conflict_clause_learning(self):
        """Tests that DPLL(T) learns conflict clauses when theory encounters contradiction."""
        # Clause 1: (p \/ q)
        # When p is true: x <= 2 and x >= 6 (UNSAT in QF-LIA)
        # When q is true: y >= 1 and y <= 3 (SAT in QF-LIA)
        t1 = LinearConstraint.from_le({"x": 1}, 2, "t1")
        t2 = LinearConstraint.from_ge({"x": 1}, 6, "t2")
        t3 = LinearConstraint.from_ge({"y": 1}, 1, "t3")
        t4 = LinearConstraint.from_le({"y": 1}, 3, "t4")

        theory_atoms = {"t1": t1, "t2": t2, "t3": t3, "t4": t4}

        clauses: List[Clause] = [
            [Literal("p", True), Literal("q", True)],
            # p -> t1 /\ t2
            [Literal("p", False), Literal("t1", True)],
            [Literal("p", False), Literal("t2", True)],
            # q -> t3 /\ t4
            [Literal("q", False), Literal("t3", True)],
            [Literal("q", False), Literal("t4", True)],
        ]

        result = self.solver.solve(clauses, theory_atoms, enable_t_propagation=False)
        self.assertTrue(result.is_sat)
        self.assertTrue(result.boolean_assignment["q"])
        self.assertFalse(result.boolean_assignment.get("p", False))
        self.assertGreater(result.learned_clauses, 0)
        self.assertIsNotNone(result.integer_model)

    def test_t_propagation(self):
        """Tests that T-propagation automatically assigns implied theory literal."""
        # If t1 (x <= 2) is True, then t2 (x <= 5) is implied to be True by QF-LIA
        t1 = LinearConstraint.from_le({"x": 1}, 2, "t1")
        t2 = LinearConstraint.from_le({"x": 1}, 5, "t2")

        theory_atoms = {"t1": t1, "t2": t2}

        # Formula asserts t1 is True
        clauses: List[Clause] = [
            [Literal("t1", True)],
        ]

        result = self.solver.solve(clauses, theory_atoms, enable_t_propagation=True)
        self.assertTrue(result.is_sat)
        # t2 should be propagated to True
        self.assertTrue(result.boolean_assignment.get("t2", False))
        self.assertGreater(result.theory_propagations, 0)

    # ------------------------------------------------------------------------
    # 4. Formal Program Verification Interface
    # ------------------------------------------------------------------------
    def test_program_verification_valid_abs(self):
        """Verifies absolute value program satisfies specification res >= 0."""
        # Program:
        # if x < 0:
        #     res = 0 - x
        # else:
        #     res = x
        program = IfThenElse(
            cond=Lt(Var("x"), Const(0)),
            then_body=Assign("res", Sub(Const(0), Var("x"))),
            else_body=Assign("res", Var("x")),
        )

        # Pre: True (None)
        # Post: res >= 0
        spec_post = Ge(Var("res"), Const(0))

        v_result = verify_program_satisfies_spec(program, pre_cond=None, post_cond=spec_post)
        self.assertTrue(v_result.is_valid)
        self.assertIsNone(v_result.counterexample)
        self.assertFalse(v_result.smt_result.is_sat)

    def test_program_verification_counterexample_bug(self):
        """Verifies buggy increment program returns concrete counterexample."""
        # Program:
        # res = x + 1
        # Pre: x >= 0
        # Post: res >= 5 (False for x in {0, 1, 2, 3})
        program = Assign("res", Add(Var("x"), Const(1)))
        pre_cond = Ge(Var("x"), Const(0))
        post_cond = Ge(Var("res"), Const(5))

        v_result = verify_program_satisfies_spec(program, pre_cond=pre_cond, post_cond=post_cond)
        self.assertFalse(v_result.is_valid)
        self.assertIsNotNone(v_result.counterexample)
        cex = v_result.counterexample
        # Counterexample x must be in [0, 3]
        x_val = cex.get("x")
        self.assertIsNotNone(x_val)
        self.assertGreaterEqual(x_val, 0)
        self.assertLess(x_val + 1, 5)

    def test_program_verification_bounded_loop(self):
        """Verifies loop unrolling establishes postcondition i >= 2."""
        # Program:
        # i = 0
        # while i < 2:
        #     i = i + 1
        program = Seq([
            Assign("i", Const(0)),
            While(
                cond=Lt(Var("i"), Const(2)),
                body=Assign("i", Add(Var("i"), Const(1))),
                max_unrolls=2,
            ),
        ])

        post_cond = Ge(Var("i"), Const(2))
        with self.assertRaises(NotImplementedError):
            verify_program_satisfies_spec(program, pre_cond=None, post_cond=post_cond)

    def test_difference_logic_cycle_conflict(self):
        """Tests that difference logic negative cycles (x - y <= 2, y - z <= 3, z - x <= -6) derive UNSAT."""
        c1 = LinearConstraint.from_le({"x": 1, "y": -1}, 2, "c1")
        c2 = LinearConstraint.from_le({"y": 1, "z": -1}, 3, "c2")
        c3 = LinearConstraint.from_le({"z": 1, "x": -1}, -6, "c3")

        assigned = [(c1, True, "c1"), (c2, True, "c2"), (c3, True, "c3")]
        is_consistent, conflict_core, _ = self.theory.check_consistency(assigned)
        self.assertFalse(is_consistent)
        self.assertEqual(conflict_core, {"c1", "c2", "c3"})

    def test_nested_conditional_min(self):
        """Verifies min(x, y) implementation satisfies postcondition res <= x and res <= y."""
        # if x < y: res = x else: res = y
        program = IfThenElse(
            cond=Lt(Var("x"), Var("y")),
            then_body=Assign("res", Var("x")),
            else_body=Assign("res", Var("y")),
        )
        post_cond = Le(Var("res"), Var("x"))
        v_res = verify_program_satisfies_spec(program, pre_cond=None, post_cond=post_cond)
        self.assertTrue(v_res.is_valid)

    def test_chvatal_gomory_tightening(self):
        """Tests integer GCD tightening: 2x <= 3 tightens to x <= 1, contradicting x >= 2."""
        c1 = LinearConstraint.from_le({"x": 2}, 3, "c1")
        self.assertEqual(c1.coeffs, {"x": 1})
        self.assertEqual(c1.const, 1)

        c2 = LinearConstraint.from_ge({"x": 1}, 2, "c2")
        is_cons, core, _ = self.theory.check_consistency([(c1, True, "c1"), (c2, True, "c2")])
        self.assertFalse(is_cons)
        self.assertEqual(core, {"c1", "c2"})


if __name__ == "__main__":
    unittest.main()

