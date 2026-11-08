"""Unit tests for Counterexample-Guided Abstraction Refinement (CEGAR) over Predicate Lattices."""
from __future__ import annotations

import unittest

from ace_neurosymbolic.cegar_refinement import (
    AbstractPredicateState,
    CEGARVerifier,
    Predicate,
    ProgramCFG,
    build_guarded_division_cfg,
    build_loop_counter_cfg,
    build_unguarded_unsafe_division_cfg,
)


class TestCEGARRefinement(unittest.TestCase):
    def test_predicate_lattice_operations(self):
        p1 = Predicate("p_x_pos", "x >= 0", lambda s: s.get("x", 0) >= 0)
        p2 = Predicate("p_y_zero", "y == 0", lambda s: s.get("y", 0) == 0)

        # 1. Top and Bot
        top = AbstractPredicateState.top([p1, p2])
        self.assertFalse(top.is_bot)
        self.assertIsNone(top.get("p_x_pos"))
        self.assertIsNone(top.get("p_y_zero"))

        bot = AbstractPredicateState.bot()
        self.assertTrue(bot.is_bot)

        # 2. Meet (sqcap: conjunction)
        s1 = AbstractPredicateState.from_dict({"p_x_pos": True, "p_y_zero": None})
        s2 = AbstractPredicateState.from_dict({"p_x_pos": None, "p_y_zero": False})
        meet_res = s1.meet(s2)
        self.assertEqual(meet_res.get("p_x_pos"), True)
        self.assertEqual(meet_res.get("p_y_zero"), False)

        # Contradiction yields BOT
        s_conflict = AbstractPredicateState.from_dict({"p_x_pos": False, "p_y_zero": None})
        conflict_meet = s1.meet(s_conflict)
        self.assertTrue(conflict_meet.is_bot)

        # 3. Join (sqcup: disjunction)
        join_res = s1.join(s2)
        self.assertIsNone(join_res.get("p_x_pos"))
        self.assertIsNone(join_res.get("p_y_zero"))

        s3 = AbstractPredicateState.from_dict({"p_x_pos": True, "p_y_zero": True})
        join_agreement = s1.join(s3)
        self.assertEqual(join_agreement.get("p_x_pos"), True)
        self.assertIsNone(join_agreement.get("p_y_zero"))

        # 4. Lattice ordering (is_subset)
        self.assertTrue(bot.is_subset(s1))
        self.assertTrue(s3.is_subset(s1))
        self.assertTrue(s1.is_subset(top))
        self.assertFalse(top.is_subset(s1))

    def test_guarded_division_cegar_verification(self):
        """Verifies safe guarded division eliminates spurious counterexamples monotonically."""
        cfg = build_guarded_division_cfg()
        verifier = CEGARVerifier(cfg, initial_predicates=[])
        res = verifier.verify(initial_concrete_states=[{"x": 10, "y": 0}, {"x": 10, "y": 2}])

        self.assertEqual(res.status, "SAFE")
        self.assertTrue(res.is_certified)
        self.assertGreaterEqual(res.spurious_counterexamples_eliminated, 1)
        self.assertGreaterEqual(len(res.discovered_predicates), 1)

        # Error state certified unreachable
        self.assertEqual(res.inductive_invariants["error"], "FALSE (BOT)")
        # Compute safe certified guarded against y == 0
        self.assertIn("not pred_interpolant", res.inductive_invariants["compute_safe"])

    def test_unguarded_unsafe_division_cegar_verification(self):
        """Verifies truly unsafe program detects concrete witness counterexample."""
        cfg = build_unguarded_unsafe_division_cfg()
        verifier = CEGARVerifier(cfg, initial_predicates=[])
        res = verifier.verify(initial_concrete_states=[{"x": 10, "y": 0}])

        self.assertEqual(res.status, "UNSAFE")
        self.assertFalse(res.is_certified)
        self.assertIsNotNone(res.concrete_counterexample)
        self.assertEqual(len(res.concrete_counterexample), 3)
        # Final state in counterexample reached error
        self.assertEqual(res.concrete_counterexample[-1]["y"], 0)

    def test_loop_counter_cegar_verification(self):
        """Verifies loop counting termination with inductive invariant generation."""
        cfg = build_loop_counter_cfg(target_count=3)
        verifier = CEGARVerifier(cfg, initial_predicates=[])
        res = verifier.verify(initial_concrete_states=[{"i": 0}])

        self.assertIn(res.status, ["SAFE", "UNSAFE"])
        if res.status == "SAFE":
            self.assertTrue(res.is_certified)
            self.assertEqual(res.inductive_invariants["error"], "FALSE (BOT)")

    def test_monotonic_lattice_refinement(self):
        """Verifies monotonic growth of discovered predicate lattice and termination."""
        cfg = build_guarded_division_cfg()
        verifier = CEGARVerifier(cfg, initial_predicates=[])

        # Step-by-step check: initially 0 predicates
        self.assertEqual(len(verifier.predicates), 0)
        res = verifier.verify(initial_concrete_states=[{"x": 5, "y": 0}])

        self.assertEqual(res.status, "SAFE")
        self.assertEqual(res.spurious_counterexamples_eliminated, 1)
        self.assertEqual(len(verifier.predicates), 1)

    def test_edge_cases(self):
        # 1. Direct entry to error CFG
        cfg_err = ProgramCFG(entry_loc="entry", error_loc="error")
        cfg_err.add_edge("entry", "error", lambda s: True, "True")
        verifier = CEGARVerifier(cfg_err)
        res = verifier.verify([{"x": 1}])
        self.assertEqual(res.status, "UNSAFE")

        # 2. Trivial safe CFG without error reachable
        cfg_safe = ProgramCFG(entry_loc="entry", error_loc="error")
        cfg_safe.add_location("exit")
        cfg_safe.add_edge("entry", "exit", lambda s: True, "True")
        verifier_safe = CEGARVerifier(cfg_safe)
        res_safe = verifier_safe.verify([{"x": 1}])
        self.assertEqual(res_safe.status, "SAFE")
        self.assertTrue(res_safe.is_certified)
        self.assertEqual(res_safe.spurious_counterexamples_eliminated, 0)


if __name__ == "__main__":
    unittest.main()
