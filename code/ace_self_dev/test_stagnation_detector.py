"""Unit and integration tests for ACE Stagnation Detector & Strategy Repair.

Validates:
1. Duplicate source_sha detection against persistent research state history.
2. Semantic equivalence detection via prediction bitvectors on confirmation pools.
3. Patience window monitoring (no-validation-improvement over K consecutive attempts).
4. Exhausted search space detection for active strategies.
5. Gating: halting redundant evaluations and preventing uninformative commits.
6. Empirical failure pattern diagnosis: parameter-based vs structural deficit.
7. Representation family policy transitions (Linear -> Composite -> Gated -> Relational -> Dispatch) without looping ordinals.
8. Clean termination with SEARCH_SPACE_EXHAUSTED / STAGNATED when all families are exhausted.
"""
from __future__ import annotations

import math
from pathlib import Path
import shutil
import tempfile
import unittest

from ace_loop.source_evolution import (
    SEED_GENE,
    TypedGene,
    compile_function,
    compute_sha,
    generate_source,
    validate_ast,
)
from ace_self_dev.confirmation_suite import ConfirmationTask, create_confirmation_suite
from ace_self_dev.models import (
    AuthorType,
    CodeCandidate,
    PersistentResearchState,
    ResearchHypothesis,
)
from ace_self_dev.stagnation_detector import (
    BitvectorRegistry,
    StagnationCheckResult,
    StagnationDetector,
    StagnationType,
    candidate_to_string_predicate,
)
from ace_self_dev.strategy_repair import (
    FAMILY_LADDER,
    FailurePatternType,
    RELATIONAL_RULES,
    DISPATCH_RULES,
    RepresentationFamily,
    StrategyRepairDecision,
    StrategyRepairEngine,
)


class TestStagnationDetectorAndStrategyRepair(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.registry_file = Path(self.temp_dir) / "test_bitvector_registry.json"
        self.tasks = create_confirmation_suite(task_seed=42)
        self.task_k2 = self.tasks["task_k2_modular_stride_shift"]
        self.task_j1 = self.tasks["task_j1_multiscale_run_parity"]

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # =========================================================================
    # 1. DUPLICATE SOURCE SHA DETECTION
    # =========================================================================
    def test_duplicate_source_sha_detected(self):
        """Exact matching source_sha in persistent state completed_cycles triggers DUPLICATE_SOURCE_SHA."""
        detector = StagnationDetector(registry_path=str(self.registry_file))
        known_sha = "373167919d71c9af38f74703309667a5899d930c66eead56fad233015bd55d99"

        state = PersistentResearchState(
            cycle_count=1,
            completed_cycles=[
                {
                    "cycle_id": 1,
                    "candidate_id": "CAND_HISTORICAL_001",
                    "source_sha": known_sha,
                    "decision": "REJECTED",
                    "holdout_score": 0.6719,
                }
            ],
        )

        is_dup, matched_cand, matched_cycle = detector.check_duplicate_source_sha(known_sha, state)
        self.assertTrue(is_dup)
        self.assertEqual(matched_cand, "CAND_HISTORICAL_001")
        self.assertEqual(matched_cycle, 1)

        # Pre-evaluation inspection must block evaluation and prevent commits
        cand = CodeCandidate(
            candidate_id="CAND_NEW_TRY",
            parent_id="G0_root",
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
            source_code="def evaluate_mechanism(length: int, density: int, stride_val: int) -> int:\n    return length % 3",
            source_sha=known_sha,
            gene_dict={"is_gated": False},
            diff_patch="",
            creation_timestamp="",
        )
        hyp = ResearchHypothesis(
            hypothesis_id="HYP_TEST_DUP",
            statement="Test duplicate sha",
            target_task_id="task_k2_modular_stride_shift",
        )

        res = detector.inspect_pre_evaluation(cand, hyp, state, self.task_k2)
        self.assertTrue(res.is_stagnated)
        self.assertEqual(res.stagnation_type, StagnationType.DUPLICATE_SOURCE_SHA)
        self.assertFalse(res.should_evaluate)
        self.assertFalse(res.should_commit)
        self.assertEqual(res.historical_match_id, "CAND_HISTORICAL_001")

    def test_unique_source_sha_allowed(self):
        """Novel source_sha passes duplicate check cleanly."""
        detector = StagnationDetector(registry_path=str(self.registry_file))
        state = PersistentResearchState(cycle_count=1, completed_cycles=[])

        is_dup, matched_cand, matched_cycle = detector.check_duplicate_source_sha("novel_sha_abc", state)
        self.assertFalse(is_dup)
        self.assertIsNone(matched_cand)

    # =========================================================================
    # 2. SEMANTIC EQUIVALENCE (BITVECTOR) DETECTION
    # =========================================================================
    def test_semantic_equivalence_detected_different_syntax(self):
        """Two syntactically distinct implementations with identical evaluation bitvectors are flagged."""
        detector = StagnationDetector(registry_path=str(self.registry_file))
        combined_pool = list(self.task_k2.train_pool) + list(self.task_k2.validation_pool)

        # Implementation A: length % 2
        code_a = (
            b"def evaluate_mechanism(length: int, density: int, stride_val: int) -> int:\n"
            b"    return length % 2\n"
        )
        fn_a = compile_function(code_a)
        pred_a = candidate_to_string_predicate(fn_a)
        bv_a, hash_a = detector.compute_prediction_bitvector(pred_a, combined_pool)

        # Register Implementation A
        detector.register_evaluated_candidate(
            task_id="task_k2_modular_stride_shift",
            candidate_id="CAND_IMPL_A",
            source_sha="sha_impl_a",
            score=0.6250,
            bitvector_hash=hash_a,
            cycle_id=10,
            bitvector=bv_a,
        )

        # Implementation B: 1 * (length * 1 + density * 0 + stride_val * 0 - 0) % 2
        # Syntactically completely different code, but algebraically identical function:
        code_b = (
            "def evaluate_mechanism(length: int, density: int, stride_val: int) -> int:\n"
            "    return 1 * (length * 1 + (density * 0) + (stride_val % 2) * 0)\n"
        )
        cand_b = CodeCandidate(
            candidate_id="CAND_IMPL_B",
            parent_id="G0_root",
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
            source_code=code_b,
            source_sha="sha_impl_b_different_syntax",
            gene_dict={"modulus": 2, "weight_length": 1, "weight_density": 0, "window_stride": 1, "parity_threshold": 0, "sign": 1},
            diff_patch="",
            creation_timestamp="",
        )
        hyp = ResearchHypothesis(
            hypothesis_id="HYP_TEST_SEMANTIC",
            statement="Test semantic equivalence",
            target_task_id="task_k2_modular_stride_shift",
        )
        state = PersistentResearchState(cycle_count=10, completed_cycles=[])

        # Pre-evaluation check must detect identical bitvector hash and halt
        res = detector.inspect_pre_evaluation(cand_b, hyp, state, self.task_k2)
        self.assertTrue(res.is_stagnated)
        self.assertEqual(res.stagnation_type, StagnationType.SEMANTIC_EQUIVALENCE)
        self.assertFalse(res.should_evaluate)
        self.assertFalse(res.should_commit)
        self.assertEqual(res.historical_match_id, "CAND_IMPL_A")

    def test_semantically_distinct_candidate_passes(self):
        """Candidate producing distinct output bitvector is not flagged as semantic equivalent."""
        detector = StagnationDetector(registry_path=str(self.registry_file))
        combined_pool = list(self.task_k2.train_pool) + list(self.task_k2.validation_pool)

        # Register Candidate A
        code_a = b"def evaluate_mechanism(length: int, density: int, stride_val: int) -> int:\n    return length % 2\n"
        fn_a = compile_function(code_a)
        pred_a = candidate_to_string_predicate(fn_a)
        _, hash_a = detector.compute_prediction_bitvector(pred_a, combined_pool)

        detector.register_evaluated_candidate(
            task_id="task_k2_modular_stride_shift",
            candidate_id="CAND_A",
            source_sha="sha_a",
            score=0.50,
            bitvector_hash=hash_a,
        )

        # Candidate B produces distinct behavior: density % 2
        code_b = "def evaluate_mechanism(length: int, density: int, stride_val: int) -> int:\n    return density % 2\n"
        cand_b = CodeCandidate(
            candidate_id="CAND_B",
            parent_id="G0_root",
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
            source_code=code_b,
            source_sha="sha_b_different",
            gene_dict={"modulus": 2, "weight_length": 0, "weight_density": 1, "window_stride": 1, "parity_threshold": 0, "sign": 1},
            diff_patch="",
            creation_timestamp="",
        )
        hyp = ResearchHypothesis(
            hypothesis_id="HYP_TEST_DISTINCT",
            statement="Test distinct semantic behavior",
            target_task_id="task_k2_modular_stride_shift",
        )
        state = PersistentResearchState(cycle_count=1, completed_cycles=[])

        res = detector.inspect_pre_evaluation(cand_b, hyp, state, self.task_k2)
        self.assertFalse(res.is_stagnated)
        self.assertEqual(res.stagnation_type, StagnationType.NONE)
        self.assertTrue(res.should_evaluate)
        self.assertTrue(res.should_commit)

    # =========================================================================
    # 3. PATIENCE WINDOW MONITORING
    # =========================================================================
    def test_patience_window_exceeded(self):
        """No validation improvement over K consecutive cycles triggers NO_VALIDATION_IMPROVEMENT."""
        detector = StagnationDetector(patience_k=3, min_improvement=0.0050)
        state = PersistentResearchState(
            cycle_count=4,
            completed_cycles=[
                {"cycle_id": 1, "target_task_id": "task_j1", "holdout_score": 0.6500},
                {"cycle_id": 2, "target_task_id": "task_j1", "holdout_score": 0.6502},  # +0.0002 < 0.0050
                {"cycle_id": 3, "target_task_id": "task_j1", "holdout_score": 0.6400},  # regression
                {"cycle_id": 4, "target_task_id": "task_j1", "holdout_score": 0.6450},  # no improvement
            ],
        )

        is_stagnated, count, best_sc, _ = detector.check_patience_window(state, task_id="task_j1", k=3)
        self.assertTrue(is_stagnated)
        self.assertGreaterEqual(count, 3)
        self.assertAlmostEqual(best_sc, 0.6500, places=4)

    def test_patience_window_resets_on_gain(self):
        """Significant improvement resets the patience counter."""
        detector = StagnationDetector(patience_k=3, min_improvement=0.0050)
        state = PersistentResearchState(
            cycle_count=3,
            completed_cycles=[
                {"cycle_id": 1, "target_task_id": "task_j1", "holdout_score": 0.6000},
                {"cycle_id": 2, "target_task_id": "task_j1", "holdout_score": 0.5900},
                {"cycle_id": 3, "target_task_id": "task_j1", "holdout_score": 0.6200},  # +0.0200 > 0.0050 (reset!)
            ],
        )

        is_stagnated, count, best_sc, _ = detector.check_patience_window(state, task_id="task_j1", k=3)
        self.assertFalse(is_stagnated)
        self.assertEqual(count, 0)
        self.assertAlmostEqual(best_sc, 0.6200, places=4)

    # =========================================================================
    # 4. STRATEGY SEARCH SPACE EXHAUSTION
    # =========================================================================
    def test_strategy_exhaustion_detected(self):
        """When all permitted ordinals for a strategy have been tried, SEARCH_SPACE_EXHAUSTED is triggered."""
        detector = StagnationDetector(strategy_limits={"SYNTHESIZE_GATED_EXPRESSION_TREE": 5})
        state = PersistentResearchState(
            cycle_count=5,
            failure_catalog={
                "task_j1": [
                    {"mutation_ordinal": i, "gene_dict": {"is_gated": True}, "gain_over_parent": 0.0}
                    for i in range(1, 6)
                ]
            },
        )

        is_exhausted, attempted, limit, reason = detector.check_strategy_exhaustion(
            "SYNTHESIZE_GATED_EXPRESSION_TREE", "task_j1", state
        )
        self.assertTrue(is_exhausted)
        self.assertEqual(attempted, 5)
        self.assertEqual(limit, 5)
        self.assertIn("exhausted", reason.lower())

    # =========================================================================
    # 5. STRATEGY REPAIR: FAILURE PATTERN ANALYSIS
    # =========================================================================
    def test_structural_deficit_vs_parameter_based_diagnosis(self):
        """Zero gain variance and low ceiling diagnoses STRUCTURAL_DEFICIT; high variance diagnoses PARAMETER_BASED."""
        repair = StrategyRepairEngine(max_attempts_per_family=4, min_variance_threshold=0.0050)

        # 1. Structural deficit: 3 ordinals tried, all yielded identical gain -0.0234
        state_structural = PersistentResearchState(
            failure_catalog={
                "task_k2": [
                    {"mutation_ordinal": 1, "gene_dict": {"is_gated": False, "is_composite": False}, "gain_over_parent": -0.0234},
                    {"mutation_ordinal": 2, "gene_dict": {"is_gated": False, "is_composite": False}, "gain_over_parent": -0.0234},
                    {"mutation_ordinal": 3, "gene_dict": {"is_gated": False, "is_composite": False}, "gain_over_parent": -0.0234},
                ]
            }
        )
        pattern_s, var_s, ceil_s, _ = repair.analyze_failure_pattern(
            "task_k2", RepresentationFamily.LINEAR_MUTATION, state_structural
        )
        self.assertEqual(pattern_s, FailurePatternType.STRUCTURAL_DEFICIT)
        self.assertAlmostEqual(var_s, 0.0, places=5)
        self.assertLess(ceil_s, 0.0500)

        # 2. Parameter-based: 2 ordinals tried, gains vary significantly (-0.02 vs +0.08)
        state_param = PersistentResearchState(
            failure_catalog={
                "task_k2": [
                    {"mutation_ordinal": 1, "gene_dict": {"is_gated": False, "is_composite": False}, "gain_over_parent": -0.0200},
                    {"mutation_ordinal": 2, "gene_dict": {"is_gated": False, "is_composite": False}, "gain_over_parent": 0.0800},
                ]
            }
        )
        pattern_p, var_p, ceil_p, _ = repair.analyze_failure_pattern(
            "task_k2", RepresentationFamily.LINEAR_MUTATION, state_param
        )
        self.assertEqual(pattern_p, FailurePatternType.PARAMETER_BASED)
        self.assertGreater(var_p, 0.0050)

    # =========================================================================
    # 6. POLICY TRANSITIONS ACROSS REPRESENTATION FAMILIES
    # =========================================================================
    def test_transition_on_structural_deficit_to_next_family(self):
        """Structural deficit triggers immediate transition to next higher representation family, not ordinal looping."""
        repair = StrategyRepairEngine(max_attempts_per_family=2, min_variance_threshold=0.0050)

        # Gated representation failed with structural deficit on task_j1
        state = PersistentResearchState(
            failure_catalog={
                "task_j1": [
                    {"mutation_ordinal": 1, "gene_dict": {"is_gated": True}, "gain_over_parent": 0.0000},
                    {"mutation_ordinal": 2, "gene_dict": {"is_gated": True}, "gain_over_parent": 0.0000},
                ]
            }
        )

        decision = repair.repair_strategy(
            current_task_id="task_j1",
            current_strategy="SYNTHESIZE_GATED_EXPRESSION_TREE",
            state=state,
            tasks=self.tasks,
        )

        self.assertEqual(decision.status, "REPAIRED")
        self.assertEqual(decision.current_family, RepresentationFamily.GATED_EXPRESSION_TREE.value)
        # Must promote to next ladder level: RELATIONAL_MULTI_CLAUSE!
        self.assertEqual(decision.next_family, RepresentationFamily.RELATIONAL_MULTI_CLAUSE.value)
        self.assertEqual(decision.next_strategy, "RELATIONAL_MULTI_CLAUSE")
        self.assertEqual(decision.suggested_ordinal, 1)
        self.assertFalse(decision.is_terminal)

    def test_transition_from_relational_to_dispatch(self):
        """When relational multi-clause is exhausted, policy transitions to multi-task dispatch."""
        repair = StrategyRepairEngine(max_attempts_per_family=2)
        state = PersistentResearchState(
            failure_catalog={
                "task_k1": [
                    {"mutation_ordinal": 1, "gene_dict": {"is_relational": True}, "gain_over_parent": 0.0000},
                    {"mutation_ordinal": 2, "gene_dict": {"is_relational": True}, "gain_over_parent": 0.0000},
                ]
            }
        )

        decision = repair.repair_strategy(
            current_task_id="task_k1",
            current_strategy="RELATIONAL_MULTI_CLAUSE",
            state=state,
            tasks=self.tasks,
        )

        self.assertEqual(decision.status, "REPAIRED")
        self.assertEqual(decision.next_family, RepresentationFamily.MULTI_TASK_DISPATCH.value)
        self.assertEqual(decision.next_strategy, "MULTI_TASK_DISPATCH")
        self.assertFalse(decision.is_terminal)

    # =========================================================================
    # 7. CLEAN SEARCH SPACE EXHAUSTION
    # =========================================================================
    def test_search_space_exhausted_clean_termination(self):
        """When all representation families are exhausted across all tasks, cleanly return SEARCH_SPACE_EXHAUSTED."""
        repair = StrategyRepairEngine(max_attempts_per_family=1)

        # Populate state with 1 failure in EVERY family for EVERY task in self.tasks
        failure_catalog = {}
        for tid in self.tasks.keys():
            failure_catalog[tid] = [
                {"mutation_ordinal": 1, "gene_dict": {"is_composite": False, "is_gated": False, "is_relational": False, "is_dispatch": False}, "gain_over_parent": 0.0},
                {"mutation_ordinal": 1, "gene_dict": {"is_composite": True}, "gain_over_parent": 0.0},
                {"mutation_ordinal": 1, "gene_dict": {"is_gated": True}, "gain_over_parent": 0.0},
                {"mutation_ordinal": 1, "gene_dict": {"is_relational": True}, "gain_over_parent": 0.0},
                {"mutation_ordinal": 1, "gene_dict": {"is_dispatch": True}, "gain_over_parent": 0.0},
            ]

        state = PersistentResearchState(cycle_count=20, failure_catalog=failure_catalog)

        decision = repair.repair_strategy(
            current_task_id=list(self.tasks.keys())[0],
            current_strategy="MULTI_TASK_DISPATCH",
            state=state,
            tasks=self.tasks,
        )

        self.assertEqual(decision.status, "SEARCH_SPACE_EXHAUSTED")
        self.assertEqual(decision.failure_pattern, FailurePatternType.SEARCH_SPACE_EXHAUSTED)
        self.assertTrue(decision.is_terminal)
        self.assertIsNone(decision.next_family)
        self.assertIsNone(decision.next_strategy)
        self.assertIn("SEARCH_SPACE_EXHAUSTED", decision.repair_rationalization)

    # =========================================================================
    # 8. AST CODE GENERATION FOR NOVEL FAMILIES
    # =========================================================================
    def test_relational_and_dispatch_code_generation_ast_validity(self):
        """Verify that synthesized relational and dispatch functions strictly conform to AST validation."""
        repair = StrategyRepairEngine()

        for ord_val in range(1, len(RELATIONAL_RULES) + 1):
            gene, src_bytes = repair.generate_relational_source(ord_val)
            func_node = validate_ast(src_bytes, expected_name="evaluate_mechanism")
            self.assertEqual(func_node.name, "evaluate_mechanism")
            fn = compile_function(src_bytes)
            # Must evaluate successfully on typical inputs without exceptions
            res = fn(6, 2, 1)
            self.assertIn(res, (0, 1))

        for ord_val in range(1, len(DISPATCH_RULES) + 1):
            gene, src_bytes = repair.generate_dispatch_source(ord_val)
            func_node = validate_ast(src_bytes, expected_name="evaluate_mechanism")
            self.assertEqual(func_node.name, "evaluate_mechanism")
            fn = compile_function(src_bytes)
            res = fn(6, 2, 1)
            self.assertIn(res, (0, 1))


if __name__ == "__main__":
    unittest.main()
