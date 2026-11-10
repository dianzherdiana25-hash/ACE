"""E2E Test Suite: Autonomous Bug Diagnosis, Patch Generation, and Testing (Requirement 4).

4-Tier Systematic Verification:
Tier 1: Feature Coverage (problem selection, bounded patch generation, independent evaluation)
Tier 2: Boundary & Corner Cases (negative controls rejecting trivial predictors, unparseable inputs)
Tier 3: Cross-Feature Interactions (meta-productivity calculation, unified diff validity, zero-cost AST synthesis)
Tier 4: Real-World Scenarios (closed-loop problem selection -> patch synthesis -> evaluation)
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

# Ensure ACE/code is on sys.path
_CODE_DIR = Path(__file__).resolve().parent.parent.parent / "code"
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

from ace_code_agent.independent_evaluator import IndependentEvaluator
from ace_code_agent.models import ImprovementHypothesis, ResearchProblem
from ace_code_agent.patch_synthesizer import ModularPatchGenerator
from ace_code_agent.problem_selector import ProblemSelector


class TestAutonomousCodingE2E(unittest.TestCase):
    """End-to-end verification of autonomous bug diagnosis, patch generation, and testing."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="ace_e2e_coding_"))
        self.selector = ProblemSelector()
        self.synthesizer = ModularPatchGenerator(use_external_model=False)
        self.evaluator = IndependentEvaluator()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Tier 1: Feature Coverage (Happy Path)
    # -------------------------------------------------------------------------

    def test_tier1_problem_selector_formulates_valid_problem_and_hypothesis(self):
        """Verify problem selector autonomously produces structured problem and hypothesis from diagnostics."""
        diagnostics = {
            "cycle_count": 10,
            "stagnation_events": 2,
            "task_failure_counts": {"task_k1": 5},
            "common_rejection_reasons": {"NO_VALIDATION_IMPROVEMENT": 4},
        }
        problem, hypothesis = self.selector.select_next_problem(diagnostics)

        self.assertIsInstance(problem, ResearchProblem)
        self.assertIsInstance(hypothesis, ImprovementHypothesis)
        self.assertEqual(problem.category, "REPRESENTATION_BOTTLENECK")
        self.assertEqual(hypothesis.problem_id, problem.problem_id)
        self.assertTrue(len(problem.target_files) > 0)
        self.assertTrue(hypothesis.proposed_strategy in [
            "MULTI_TASK_COMPOSITE_DISPATCH",
            "LIBRARY_PRIMITIVE_SYNTHESIS",
            "CONSTRAINT_PRUNING",
        ])

    def test_tier1_patch_synthesizer_generates_valid_ast_and_diff(self):
        """Verify patch synthesizer produces a valid unified diff and parseable Python code snippet."""
        hypothesis = ImprovementHypothesis(
            hypothesis_id="hyp_test_01",
            problem_id="prob_test_01",
            statement="Expand dispatch topology with composite modulo predicate.",
            proposed_strategy="MULTI_TASK_COMPOSITE_DISPATCH",
            expected_metric_gain=0.1875,
            target_module="code/ace_self_dev/strategy_repair.py",
            rationale="Single-task candidates cannot mathematically cross the +0.1500 promotion gate.",
        )
        original_code = "def repair_strategy():\n    return 'linear_mutation'\n"
        target_file = "code/ace_self_dev/strategy_repair.py"

        patch = self.synthesizer.generate_patch(hypothesis, original_code, target_file)

        self.assertEqual(patch.hypothesis_id, "hyp_test_01")
        self.assertEqual(patch.target_file, target_file)
        self.assertEqual(patch.patch_type, "AST_TRANSFORMATION")
        self.assertEqual(patch.author_provenance, "ACE_BOUNDED_AST_PATCH_GENERATOR_V04")
        self.assertTrue(len(patch.diff_content) > 0)
        self.assertIn("repair_strategy", patch.diff_content)

        # Verify replacement code snippet is syntactically valid Python
        parsed = ast.parse(patch.replacement_code_snippet)
        self.assertIsInstance(parsed, ast.Module)

    def test_tier1_independent_evaluator_evaluates_predicate(self):
        """Verify independent evaluator tests a candidate predicate against held-out instances."""
        def good_parity_predicate(length: int, density: int, stride_val: int) -> int:
            return 1 if (length + density) % 2 == 0 else 0

        score, hits, total = self.evaluator.evaluate_predicate(good_parity_predicate, task_id="task_k1")
        self.assertEqual(total, 16)
        self.assertIsInstance(score, float)
        self.assertTrue(0.0 <= score <= 1.0)
        self.assertEqual(hits, int(score * total))

    # -------------------------------------------------------------------------
    # Tier 2: Boundary & Corner Cases
    # -------------------------------------------------------------------------

    def test_tier2_negative_control_rejects_trivial_all_ones_predicate(self):
        """Verify negative control check rejects degenerate candidates that trivially return 1."""
        def degenerate_all_ones(l: int, d: int, s: int) -> int:
            return 1

        passes_negative_control = self.evaluator.evaluate_negative_control(degenerate_all_ones)
        self.assertFalse(passes_negative_control, "Degenerate all-ones predicate must fail negative control")

    def test_tier2_negative_control_accepts_discriminating_predicate(self):
        """Verify negative control check accepts genuinely discriminating non-trivial predicates."""
        def non_trivial_predicate(l: int, d: int, s: int) -> int:
            return 1 if (l > 0 and d > 0 and s > 0 and (l + d) % 2 == 0) else 0

        passes_negative_control = self.evaluator.evaluate_negative_control(non_trivial_predicate)
        self.assertTrue(passes_negative_control, "Discriminating predicate must pass negative control")

    def test_tier2_problem_selector_defaults_to_representation_expansion_on_empty_diagnostics(self):
        """Verify problem selector handles empty diagnostics gracefully with a fallback problem."""
        empty_diag: dict = {}
        problem, hypothesis = self.selector.select_next_problem(empty_diag)
        self.assertIsInstance(problem, ResearchProblem)
        self.assertIsInstance(hypothesis, ImprovementHypothesis)
        self.assertEqual(problem.priority_score, 0.75)

    # -------------------------------------------------------------------------
    # Tier 3: Cross-Feature Interactions
    # -------------------------------------------------------------------------

    def test_tier3_meta_productivity_calculation(self):
        """Verify meta-productivity correctly balances novelty rate against evaluation latencies."""
        durations = [0.05, 0.04, 0.06, 0.05]
        metrics = self.evaluator.compute_meta_productivity(
            cycle_count=10,
            novel_candidates_count=8,
            eval_durations=durations,
        )
        self.assertEqual(metrics["novelty_rate"], 0.8)
        self.assertAlmostEqual(metrics["mean_latency_s"], 0.05, places=4)
        self.assertGreater(metrics["meta_productivity_index"], 0.0)

    def test_tier3_zero_cost_patch_generator_metadata(self):
        """Verify patch generator adheres strictly to zero-cost invariant ($0.00 / Rp0)."""
        hypothesis = ImprovementHypothesis(
            hypothesis_id="hyp_zero_cost_01",
            problem_id="prob_zc_01",
            statement="Test zero marginal cost.",
            proposed_strategy="MULTI_TASK_COMPOSITE_DISPATCH",
            expected_metric_gain=0.1500,
            target_module="code/ace_self_dev/dummy.py",
            rationale="Verify $0.00 zero marginal cost invariant.",
        )
        patch = self.synthesizer.generate_patch(hypothesis, "x = 1\n", "dummy.py")
        self.assertEqual(patch.generator_metadata.get("marginal_cost_usd"), 0.0)
        self.assertTrue(patch.generator_metadata.get("ast_validated"))

    # -------------------------------------------------------------------------
    # Tier 4: Real-World Scenarios
    # -------------------------------------------------------------------------

    def test_tier4_closed_loop_diagnose_synthesize_and_evaluate(self):
        """Simulate complete autonomous coding cycle from failure diagnosis to candidate scoring."""
        # 1. Diagnose from failure log
        diag = {
            "cycle_count": 3,
            "stagnation_events": 1,
            "task_failure_counts": {"task_k1": 3},
            "common_rejection_reasons": {"NO_VALIDATION_IMPROVEMENT": 2},
        }
        problem, hypothesis = self.selector.select_next_problem(diag)

        # 2. Synthesize candidate patch
        original_source = (
            "def dispatch_task(task_id: str, length: int, density: int, stride_val: int) -> int:\n"
            "    return (length + density) % 2\n"
        )
        patch = self.synthesizer.generate_patch(hypothesis, original_source, "dispatch.py")
        self.assertTrue(len(patch.replacement_code_snippet) > 0)

        # 3. Simulate independent evaluation of candidate
        scope: dict = {}
        full_code = original_source + "\n" + patch.replacement_code_snippet
        exec(full_code, scope)
        candidate_fn = scope["dispatch_task"]

        # 4. Evaluate against confirmation holdouts
        score, hits, total = self.evaluator.evaluate_predicate(
            lambda l, d, s: candidate_fn("task_k1", l, d, s),
            task_id="task_k1",
        )
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
        self.assertEqual(total, 16)


if __name__ == "__main__":
    unittest.main()
