"""Adversarial tests for finite residual composition and explicit limits."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from e14.e14_shared_budget import BudgetContractError
from e14.e14aa_learning import (ATOMS, GRID, SearchLimits, choose_query, evaluate,
                               fit, signature, select_query, _program)


class ResidualLearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # A periodic term plus an independently located threshold term.
        cls.program = _program(((ATOMS.index(("residue", 3, 1)), 2),
                                (ATOMS.index(("threshold", 7)), -1)))
        cls.labels = [(xy, evaluate(cls.program, *xy)) for xy in GRID]

    def test_composed_form_outside_previous_single_term_grammar(self):
        from e14.e14y_induction import grammar
        expected = signature(self.program)
        self.assertNotIn(expected, {entry[2] for entry in grammar()})
        result = fit(self.labels)
        self.assertTrue(result.complete)
        self.assertTrue(result.unique)
        self.assertEqual(result.signatures, (expected,))
        self.assertEqual(signature(result.programs[0]), expected)

    def test_active_acquisition_can_identify_form_with_only_purchased_labels(self):
        history = [self.labels[0]]
        for _ in range(12):
            result = fit(history)
            if result.unique:
                break
            query = choose_query(result, history)
            self.assertIsNotNone(query)
            self.assertNotIn(query, [xy for xy, _ in history])
            history.append((query, evaluate(self.program, *query)))
        self.assertTrue(result.unique)
        self.assertEqual(result.signatures, (signature(self.program),))
        self.assertLessEqual(len(history), 12)

    def test_ambiguous_fit_never_claims_unrestricted_soundness(self):
        result = fit([((4, 4), 8)])
        self.assertTrue(result.complete)
        self.assertFalse(result.unique)
        self.assertIn("CONDITIONAL", result.scope)
        self.assertGreater(len(result.signatures), 1)

    def test_candidate_limit_cannot_certify_unique_partial_fit(self):
        result = fit([((4, 4), 8)], limits=SearchLimits(max_candidates=1))
        self.assertEqual(result.status, "CANDIDATE_LIMIT")
        self.assertEqual(result.stats.candidates, 1)
        self.assertFalse(result.complete)
        self.assertFalse(result.unique)
        self.assertEqual(len(result.signatures), 1)

    def test_evaluation_limit_counts_precomputation(self):
        result = fit([], limits=SearchLimits(max_evaluations=7))
        self.assertEqual(result.status, "EVALUATION_LIMIT")
        self.assertEqual(result.stats.evaluations, 7)
        self.assertEqual(result.stats.atom_evaluations, 7)
        self.assertFalse(result.unique)

    def test_program_memory_limit_is_explicit(self):
        result = fit([], limits=SearchLimits(max_programs=1))
        self.assertEqual(result.status, "PROGRAM_LIMIT")
        self.assertLessEqual(len(result.programs), 1)
        self.assertFalse(result.complete)

    def test_cpu_expiration_is_explicit(self):
        with patch("e14.e14aa_learning.time.process_time", side_effect=range(100)):
            result = fit([], limits=SearchLimits(max_seconds=0.01))
        self.assertEqual(result.status, "CPU_LIMIT")
        self.assertFalse(result.complete)

    def test_single_term_and_node_controls_cannot_fit_composite_truth(self):
        for limits in (SearchLimits(max_terms=1), SearchLimits(max_nodes=3)):
            result = fit(self.labels, limits=limits)
            self.assertTrue(result.complete)
            self.assertEqual(result.status, "NO_FIT")

    def test_conflicting_duplicate_receipt_requires_epoch_reset(self):
        with self.assertRaisesRegex(BudgetContractError, "semantic epoch"):
            fit([((4, 4), 8), ((4, 4), 9)])

    def test_consistent_duplicate_receipts_do_not_change_candidate_set(self):
        a = fit(self.labels)
        b = fit(self.labels[:1] + self.labels[:1] + self.labels[1:-1])
        self.assertEqual(a.signatures, b.signatures)

    def test_invalid_labels_coordinates_and_limit_types_fail_closed(self):
        for evidence in ([((4, 4), True)], [((True, 4), 8)], [((4, 19), 20)],
                         [((4, 4), 8.0)], [[[4, 4], 8]], [((4, 4), -1)]):
            with self.subTest(evidence=evidence), self.assertRaises(BudgetContractError):
                fit(evidence)
        for kwargs in ({"max_candidates": True}, {"max_terms": 3},
                       {"max_seconds": float("nan")}, {"max_seconds": True},
                       {"max_nodes": 100000}):
            with self.subTest(kwargs=kwargs), self.assertRaises(BudgetContractError):
                SearchLimits(**kwargs)

    def test_adversarial_ast_fails_before_recursive_evaluation(self):
        tree = ("lo",)
        for _ in range(10000):
            tree = ("add", tree, ("const", 1))
        for ast in (tree, ("const", True), ("__import__",),
                    ("mod", ("lo",), ("const", 0)), ["lo"]):
            with self.subTest(kind=type(ast)), self.assertRaises(BudgetContractError):
                evaluate(ast, 4, 5)

    def test_query_selector_respects_restricted_domain(self):
        evidence = [((4, 4), 8)]
        result = fit(evidence)
        self.assertIsNone(choose_query(result, evidence, allowed=[(4, 4)]))
        query = choose_query(result, evidence, allowed=[(4, 4), (4, 5)])
        self.assertEqual(query, (4, 5))
        with self.assertRaises(BudgetContractError):
            choose_query(result, evidence, allowed=[(True, 4)])

    def test_query_resource_limit_never_returns_partial_minimax_as_complete(self):
        evidence = [((4, 4), 8)]
        result = fit(evidence)
        selection = select_query(result, evidence, max_evaluations=7)
        self.assertFalse(selection.complete)
        self.assertEqual(selection.status, "EVALUATION_LIMIT")
        self.assertEqual(selection.signature_lookups, 7)
        self.assertIsNone(selection.costs)
        selected = select_query(result, evidence, allowed=[(4, 5)])
        self.assertTrue(selected.complete)
        self.assertEqual(selected.signature_lookups, len(result.signatures))
        self.assertEqual(selected.costs, (4, 5))

    def test_forged_signature_artifacts_fail_closed(self):
        result = fit(self.labels)
        for signatures in (((True,) * len(GRID),), ((8,),), [result.signatures[0]]):
            bad = replace(result, signatures=signatures)
            with self.subTest(kind=type(signatures)), self.assertRaises(BudgetContractError):
                select_query(bad, [])

    def test_counters_include_failed_fits_and_exact_exhaustive_form_count(self):
        result = fit(self.labels)
        self.assertEqual(result.stats.candidates, 1 + 29 * 6 + (29 * 28 // 2) * 36)
        self.assertEqual(result.stats.atom_evaluations, len(ATOMS) * len(GRID))
        self.assertGreater(result.stats.evidence_evaluations, result.stats.candidates)
        self.assertGreater(result.stats.primitive_evaluations, result.stats.evaluations)
        self.assertGreater(result.stats.cpu_seconds, 0)

    def test_deterministic_candidates_and_query_ignore_timing_fields(self):
        a = fit(self.labels[:8]); b = fit(self.labels[:8])
        self.assertEqual((a.programs, a.signatures, a.status), (b.programs, b.signatures, b.status))
        self.assertEqual(choose_query(a, self.labels[:8]), choose_query(b, self.labels[:8]))


if __name__ == "__main__":
    unittest.main()
