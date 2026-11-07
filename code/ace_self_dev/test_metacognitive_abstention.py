"""Unit and integration test suite for Metacognitive Self-Modeling & Failure Predictor.

Verifies:
1. Candidate feature extraction (structural depth, operator variety, history of failure constraints).
2. Operator collapse and zero-weight degeneracy detection.
3. Popperian FailureConstraint exact matching and partial overlap risk scoring.
4. Calibrated expected failure probability calculation P(failure | features).
5. Pre-execution abstention gating (should_abstain) and 'ABSTAIN_PREDICTED_FAILURE' recommendation.
6. Calibration evaluation: Brier score, Expected Calibration Error (ECE), and MCE.
7. Selective risk reduction and coverage metrics.
8. Online observation recording and durable persistence.
9. End-to-end integration with SelfDevelopmentCoordinator ($0 budget and 0 holdout queries on abstention).
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from ace_loop.source_evolution import (
    CompositeGene,
    GatedGene,
    RelationalGatedGene,
    SEED_GENE,
    TypedGene,
    generate_source,
    mutate_gene,
)
from ace_self_dev.confirmation_suite import ConfirmationTask, create_confirmation_suite
from ace_self_dev.coordinator import SelfDevelopmentCoordinator
from ace_self_dev.failure_constraint_engine import FailureConstraint, FailureConstraintEngine
from ace_self_dev.metacognitive_predictor import (
    CalibrationReport,
    CandidateFeatures,
    HighRiskHeuristic,
    MetacognitiveForecast,
    MetacognitivePredictor,
    ReliabilityBin,
    compute_ast_depth,
    compute_brier_score,
    compute_calibration_report,
    compute_expected_calibration_error,
    compute_gene_depth,
    extract_ast_operators,
    extract_gene_operators,
)
from ace_self_dev.models import (
    AuthorType,
    CandidateDecision,
    CodeCandidate,
    EvaluationReceipt,
    ResearchHypothesis,
)


class TestMetacognitiveAbstention(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="ace_metacog_test_"))
        self.predictor = MetacognitivePredictor(
            risk_tolerance_threshold=0.70,
            storage_path=str(self.tmp_dir / "metacog_memory.json"),
            base_failure_rate=0.50,
        )

    def tearDown(self):
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _make_candidate(
        self,
        candidate_id: str,
        gene: Any,
        source_code: str | None = None,
    ) -> CodeCandidate:
        gene_dict = gene.to_dict() if hasattr(gene, "to_dict") else gene
        src = source_code or generate_source(gene).decode("utf-8")
        return CodeCandidate(
            candidate_id=candidate_id,
            parent_id="G0_root_seed",
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
            source_code=src,
            source_sha=f"sha_{candidate_id}",
            gene_dict=gene_dict,
        )

    # 1. Feature Extraction: Structural Depth
    def test_feature_extraction_structural_depth(self):
        """Verifies structural depth calculation across atomic, composite, and relational genes."""
        # Atomic gene
        atomic_gene = SEED_GENE
        atomic_cand = self._make_candidate("cand_atomic", atomic_gene)
        feats_atomic = self.predictor.extract_features(atomic_cand)
        self.assertEqual(feats_atomic.gene_depth, 1)
        self.assertEqual(feats_atomic.structural_depth, 3)

        # Composite gene
        comp_gene = CompositeGene(gene_a=SEED_GENE, gene_b=SEED_GENE, operator="ADD")
        comp_cand = self._make_candidate("cand_comp", comp_gene)
        feats_comp = self.predictor.extract_features(comp_cand)
        self.assertEqual(feats_comp.gene_depth, 2)
        self.assertGreaterEqual(feats_comp.structural_depth, 3)

        # Relational gated gene
        rel_gene = RelationalGatedGene(
            length_op=">=",
            length_threshold=6,
            stride_weight=2,
            density_weight=-1,
            modulus=4,
            target_residue=0,
            congruence_op="==",
            boundary_var="density",
            boundary_op="<=",
            boundary_threshold=5,
            combiner="AND",
        )
        rel_cand = self._make_candidate("cand_rel", rel_gene)
        feats_rel = self.predictor.extract_features(rel_cand)
        self.assertEqual(feats_rel.gene_depth, 3)
        self.assertGreaterEqual(feats_rel.structural_depth, 3)

    # 2. Feature Extraction: Operator Variety
    def test_feature_extraction_operator_variety(self):
        """Verifies operator variety scoring across rich vs narrow operator sets."""
        rich_gene = RelationalGatedGene(
            length_op=">=",
            length_threshold=4,
            stride_weight=1,
            density_weight=2,
            modulus=3,
            target_residue=0,
            congruence_op="==",
            boundary_var="density",
            boundary_op="<=",
            boundary_threshold=4,
            combiner="AND",
        )
        rich_cand = self._make_candidate("cand_rich", rich_gene)
        feats_rich = self.predictor.extract_features(rich_cand)
        self.assertGreater(feats_rich.operator_variety, 0.40)
        self.assertIn(">=", feats_rich.unique_operators)
        self.assertIn("==", feats_rich.unique_operators)
        self.assertIn("and", feats_rich.unique_operators)

    # 3. High-Risk Heuristic: Operator Collapse & Zero-Weight Degeneracy
    def test_operator_collapse_and_zero_weight_heuristic(self):
        """Verifies operator collapse and zero-weight degeneracy are caught."""
        # Zero-weight degeneracy: weights all zero
        zero_gene = TypedGene(
            window_stride=2,
            modulus=3,
            parity_threshold=1,
            weight_length=0,
            weight_density=0,
            sign=1,
        )
        zero_cand = self._make_candidate("cand_zero", zero_gene)
        feats_zero = self.predictor.extract_features(zero_cand)
        self.assertIn(HighRiskHeuristic.ZERO_WEIGHT_DEGENERACY.value, feats_zero.heuristics_triggered)
        p_fail_zero = self.predictor.predict_failure_probability(zero_cand)
        self.assertGreaterEqual(p_fail_zero, 0.70)

        should_abs, risk, reason = self.predictor.should_abstain(zero_cand)
        self.assertTrue(should_abs)
        self.assertTrue(reason.startswith("ABSTAIN_PREDICTED_FAILURE"))
        self.assertIn("ZERO_WEIGHT_DEGENERACY", reason)

    # 4. Failure Constraint Matching: Popperian Falsification Violation
    def test_failure_constraint_violation_and_risk(self):
        """Verifies that direct failure constraint violations raise predicted risk and trigger abstention."""
        # Create a candidate that uses mod 3 == 0 with combiner AND
        rel_gene = RelationalGatedGene(
            length_op=">=",
            length_threshold=8,
            modulus=3,
            target_residue=0,
            combiner="AND",
        )
        cand = self._make_candidate("cand_violator", rel_gene)

        # 1. Without constraints -> candidate proceeds normally
        should_abs_no_c, risk_no_c, _ = self.predictor.should_abstain(cand, failure_constraints=())
        self.assertFalse(should_abs_no_c)
        self.assertLess(risk_no_c, 0.70)

        # 2. Add an exact Modulus Conflict constraint
        fc_mod = FailureConstraint(
            constraint_id="FC_MOD_3_0",
            task_id="parity_mod_3",
            constraint_type="MODULUS_CONFLICT",
            violating_witness="aaabbb",
            expected_label=False,
            forbidden_pattern={"modulus": 3, "target_residue": 0, "combiner": "AND"},
            deduced_reason="AND mod 3 == 0 falsely admitted witness 'aaabbb'",
        )

        feats_mod = self.predictor.extract_features(cand, failure_constraints=[fc_mod])
        self.assertEqual(feats_mod.constraint_conflicts_count, 1)
        self.assertIn("FC_MOD_3_0", feats_mod.violating_constraint_ids)
        self.assertIn(HighRiskHeuristic.CONSTRAINT_VIOLATION.value, feats_mod.heuristics_triggered)

        should_abs_mod, risk_mod, reason_mod = self.predictor.should_abstain(cand, failure_constraints=[fc_mod])
        self.assertTrue(should_abs_mod)
        self.assertGreaterEqual(risk_mod, 0.70)
        self.assertTrue(reason_mod.startswith("ABSTAIN_PREDICTED_FAILURE"))
        self.assertIn("CONSTRAINT_VIOLATION", reason_mod)

        # 3. Add a Length Guard Excess constraint
        fc_len = FailureConstraint(
            constraint_id="FC_LEN_EXCESS",
            task_id="length_guard_task",
            constraint_type="LENGTH_GUARD_EXCESS",
            violating_witness="aaa",  # length 3 < candidate length_threshold 8
            expected_label=True,
            forbidden_pattern={"min_threshold": 8},
            deduced_reason="Length threshold >= 8 excludes positive witness 'aaa'",
        )
        feats_len = self.predictor.extract_features(cand, failure_constraints=[fc_len])
        self.assertEqual(feats_len.constraint_conflicts_count, 1)
        self.assertIn("FC_LEN_EXCESS", feats_len.violating_constraint_ids)

    # 5. High-Risk Heuristic: Degenerate Modulus and Extreme Length Guard
    def test_degenerate_modulus_and_extreme_length_guard(self):
        """Verifies degenerate modulus (<=1) and extreme length guard (>32) trigger abstention."""
        # Extreme length guard (> 32)
        extreme_gene = RelationalGatedGene(
            length_threshold=64,  # > 32
            modulus=3,
        )
        extreme_cand = self._make_candidate("cand_extreme_len", extreme_gene)
        feats_len = self.predictor.extract_features(extreme_cand)
        self.assertIn(HighRiskHeuristic.EXTREME_LENGTH_GUARD.value, feats_len.heuristics_triggered)
        should_abs_len, risk_len, reason_len = self.predictor.should_abstain(extreme_cand)
        self.assertTrue(should_abs_len)
        self.assertIn("EXTREME_LENGTH_GUARD", reason_len)

        # Degenerate modulus (<= 1)
        deg_gene_dict = {
            "is_composite": False,
            "window_stride": 2,
            "modulus": 1,  # degenerate mod 1
            "parity_threshold": 0,
            "weight_length": 1,
            "weight_density": 1,
            "sign": 1,
        }
        deg_cand = CodeCandidate(
            candidate_id="cand_deg_mod",
            parent_id="root",
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
            source_code="def evaluate_mechanism(l, d, s): return 0",
            source_sha="sha_deg",
            gene_dict=deg_gene_dict,
        )
        feats_deg = self.predictor.extract_features(deg_cand)
        self.assertIn(HighRiskHeuristic.DEGENERATE_MODULUS.value, feats_deg.heuristics_triggered)
        should_abs_deg, risk_deg, reason_deg = self.predictor.should_abstain(deg_cand)
        self.assertTrue(should_abs_deg)
        self.assertIn("DEGENERATE_MODULUS", reason_deg)

    # 6. Mathematical Formulations: Brier Score and ECE Calibration
    def test_calibration_brier_score_and_ece(self):
        """Verifies standalone Brier score and ECE mathematical formulations."""
        # 1. Perfect calibration: predictions match outcomes exactly
        # 5 samples: p = [1.0, 1.0, 0.0, 0.0, 1.0], y = [True, True, False, False, True]
        p_perfect = [1.0, 1.0, 0.0, 0.0, 1.0]
        y_perfect = [True, True, False, False, True]
        brier_perfect = compute_brier_score(p_perfect, y_perfect)
        ece_perfect = compute_expected_calibration_error(p_perfect, y_perfect, n_bins=10)
        self.assertAlmostEqual(brier_perfect, 0.0, places=4)
        self.assertAlmostEqual(ece_perfect, 0.0, places=4)

        # 2. Known hand-calculated miscalibration
        # Predictions: [0.8, 0.8, 0.2, 0.2]
        # True outcomes (failure): [False, False, True, True] (completely inverted!)
        # Brier = ((0.8 - 0)^2 + (0.8 - 0)^2 + (0.2 - 1)^2 + (0.2 - 1)^2) / 4
        #       = (0.64 + 0.64 + 0.64 + 0.64) / 4 = 0.64
        p_inverted = [0.8, 0.8, 0.2, 0.2]
        y_inverted = [False, False, True, True]
        brier_inv = compute_brier_score(p_inverted, y_inverted)
        self.assertAlmostEqual(brier_inv, 0.64, places=4)

        # ECE with 10 bins:
        # Bin 2 ([0.2, 0.3)): 2 items, avg_p = 0.2, avg_y = 1.0 -> |0.2 - 1.0| = 0.8
        # Bin 8 ([0.8, 0.9)): 2 items, avg_p = 0.8, avg_y = 0.0 -> |0.8 - 0.0| = 0.8
        # Weighted ECE = (2/4)*0.8 + (2/4)*0.8 = 0.80
        ece_inv = compute_expected_calibration_error(p_inverted, y_inverted, n_bins=10)
        self.assertAlmostEqual(ece_inv, 0.80, places=4)

        # 3. Input validation
        with self.assertRaises(ValueError):
            compute_brier_score([], [])
        with self.assertRaises(ValueError):
            compute_brier_score([0.5], [True, False])
        with self.assertRaises(ValueError):
            compute_expected_calibration_error([0.5], [True], n_bins=0)

    # 7. Comprehensive Calibration Report (ECE, MCE, Selective Risk, Coverage)
    def test_calibration_report_metrics(self):
        """Verifies complete CalibrationReport including coverage and selective risk."""
        # 10 trials: 6 executed (4 succeeded, 2 failed), 4 abstained (all 4 would have failed)
        records = [
            # Executed and succeeded (y = False)
            (0.15, False, True),
            (0.20, False, True),
            (0.25, False, True),
            (0.30, False, True),
            # Executed and failed (y = True)
            (0.40, True, True),
            (0.50, True, True),
            # Abstained and would have failed (y = True, executed = False)
            (0.85, True, False),
            (0.90, True, False),
            (0.92, True, False),
            (0.95, True, False),
        ]
        report = compute_calibration_report(records, n_bins=10)
        self.assertIsInstance(report, CalibrationReport)
        self.assertEqual(report.n_trials, 10)
        self.assertAlmostEqual(report.coverage, 0.60, places=4)  # 6 / 10
        self.assertAlmostEqual(report.selective_risk, 0.3333, places=2)  # 2 / 6 = ~0.3333
        # Decision accuracy: 4 correct executed successes + 4 correct abstentions = 8 / 10 = 0.80
        self.assertAlmostEqual(report.decision_accuracy, 0.80, places=2)
        self.assertGreater(report.brier_score, 0.0)
        self.assertGreater(report.ece, 0.0)
        self.assertEqual(len(report.bins), 10)

        # Verify to_dict() serialization
        rep_dict = report.to_dict()
        self.assertIn("ece_10", rep_dict)
        self.assertIn("brier_score", rep_dict)
        self.assertIn("selective_risk", rep_dict)
        self.assertIn("coverage", rep_dict)

    # 8. Online Observation Recording & Disk Persistence
    def test_online_observation_and_persistence(self):
        """Verifies recording evaluation outcomes and reloading persisted memory."""
        self.predictor.record_outcome("cand_1", 0.25, actual_failure=False, executed=True)
        self.predictor.record_outcome("cand_2", 0.85, actual_failure=True, executed=False)
        self.assertEqual(self.predictor.total_observed_trials, 2)

        # Evaluate calibration on internal records
        cal = self.predictor.evaluate_calibration(n_bins=5)
        self.assertEqual(cal.n_trials, 2)
        self.assertEqual(cal.coverage, 0.50)

        # Reload from storage_path
        reloaded = MetacognitivePredictor(
            storage_path=str(self.tmp_dir / "metacog_memory.json")
        )
        self.assertEqual(reloaded.total_observed_trials, 2)
        cal_reloaded = reloaded.evaluate_calibration(n_bins=5)
        self.assertAlmostEqual(cal.brier_score, cal_reloaded.brier_score, places=4)
        self.assertAlmostEqual(cal.ece, cal_reloaded.ece, places=4)

    # 9. MetacognitiveForecast Dataclass Integration
    def test_metacognitive_forecast(self):
        """Verifies MetacognitiveForecast returns complete structured diagnostics."""
        cand = self._make_candidate("cand_forecast", SEED_GENE)
        fc = self.predictor.forecast(cand)
        self.assertIsInstance(fc, MetacognitiveForecast)
        self.assertIsInstance(fc.features, CandidateFeatures)
        self.assertFalse(fc.should_abstain)
        self.assertEqual(fc.recommendation, "PROCEED_EVALUATION")
        self.assertGreater(fc.p_success, 0.0)
        self.assertGreater(fc.p_failure, 0.0)
        self.assertAlmostEqual(fc.p_success + fc.p_failure, 1.0, places=3)

        d = fc.to_dict()
        self.assertIn("p_failure", d)
        self.assertIn("p_success", d)
        self.assertIn("uncertainty", d)
        self.assertIn("recommendation", d)

    # 10. End-to-End Pipeline: Pre-Execution Abstention Saves $0 Budget in Coordinator
    def test_coordinator_pre_execution_abstention_pipeline(self):
        """Full pipeline test: Coordinator abstains on high-risk candidate with $0 budget and 0 holdout calls."""
        coord_ckpt_dir = self.tmp_dir / "coord_ckpt"
        coord_evid_dir = self.tmp_dir / "coord_evid"
        coordinator = SelfDevelopmentCoordinator(
            checkpoint_dir=str(coord_ckpt_dir),
            evidence_dir=str(coord_evid_dir),
        )

        # Deduce a formal failure constraint for target task 'task_j1_multiscale_run_parity'
        target_tid = "task_j1_multiscale_run_parity"
        fc = FailureConstraint(
            constraint_id="FC_TEST_MOD_3_1",
            task_id=target_tid,
            constraint_type="MODULUS_CONFLICT",
            violating_witness="aaa",
            expected_label=False,
            forbidden_pattern={"modulus": 3, "target_residue": 1},
            deduced_reason="Modular congruence mod 3 == 1 fails on witness 'aaa'",
        )
        coordinator.failure_constraint_engine._constraints[target_tid] = [fc]
        coordinator.failure_constraint_engine._save()
        self.assertGreater(coordinator.failure_constraint_engine.total_constraints, 0)

        # Run autonomous cycle where candidate matches the falsified constraint
        cycle_result = coordinator.run_autonomous_cycle(
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
        )

        # Verify that pre-execution abstention was triggered
        self.assertEqual(cycle_result["decision"], CandidateDecision.ABSTAINED.value)
        self.assertTrue(cycle_result["should_abstain"])
        self.assertTrue(cycle_result["decision_reason"].startswith("ABSTAIN_PREDICTED_FAILURE"))
        self.assertFalse(cycle_result["is_promoted"])  # Invariant baseline preserved!

        # Verify receipt: $0 cost, 0 evaluator calls!
        ckpt = coordinator.checkpointer.load_checkpoint(cycle_result["cycle_id"])
        self.assertIsNotNone(ckpt)
        self.assertEqual(ckpt.evaluation["decision"], "ABSTAINED")
        self.assertEqual(ckpt.evaluation["evaluator_calls"], 0)
        self.assertEqual(ckpt.evaluation["cost_usd"], 0.0)
        self.assertEqual(ckpt.evaluation["evaluator_manifest_digest"], "SKIPPED_DUE_TO_PREDICTED_FAILURE")
        self.assertIn("metacognitive_forecast", ckpt.evaluation)
        self.assertTrue(ckpt.evaluation["metacognitive_forecast"]["should_abstain"])


if __name__ == "__main__":
    unittest.main()
