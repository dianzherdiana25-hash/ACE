"""Test Suite for ACE Vision Breakthrough Architecture.

Validates the 4 Scientific Pillars for Reaching OAIE:
1. Popper-inspired Learning from Failures (FailureConstraintEngine).
2. pyribs MAP-Elites Quality Diversity Archive (QualityDiversityArchive).
3. Stitch / DreamCoder Library Learning & Program Compression (PrimitiveSynthesizer).
4. Mathematical Proof & Execution of Multi-Task Composite Dispatch for G0 -> G1 Promotion.
5. Autonomous Continuity Integration in Coordinator.
"""
from __future__ import annotations

import ast
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from ace_host_controller import (
    ExecutionBudget,
    HostController,
    HostSandboxGate,
    SealedHoldoutEvaluator,
)
from ace_loop.source_evolution import (
    GatedGene,
    RelationalGatedGene,
    RelationalGene,
    TypedGene,
    compile_function,
    validate_ast,
)
from ace_self_dev.confirmation_suite import create_confirmation_suite
from ace_self_dev.coordinator import SelfDevelopmentCoordinator
from ace_self_dev.failure_constraint_engine import FailureConstraint, FailureConstraintEngine
from ace_self_dev.models import (
    AuthorType,
    CandidateDecision,
    CodeCandidate,
    PersistentResearchState,
    ResearchHypothesis,
)
from ace_self_dev.primitive_synthesizer import PrimitiveSynthesizer, SynthesizedPrimitive
from ace_self_dev.quality_diversity import EliteEntry, QualityDiversityArchive


class TestVisionBreakthrough(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_failure_constraint_deduction_and_pruning(self) -> None:
        """Pillar 1: Popper LFF constraint deduction and O(1) in-memory pruning."""
        storage = self.test_path / "fc.json"
        engine = FailureConstraintEngine(storage_path=str(storage))

        # Rejected gene: GatedGene with min_length=6 that blocked positive witness of length 4
        gene = GatedGene(min_length=6, modulus=3, target_residue=0)
        c = engine.deduce_constraint(
            task_id="task_k2",
            gene=gene,
            witness_input="abab",
            expected_label=True,
            predicted_label=False,
        )

        self.assertEqual(c.constraint_type, "LENGTH_GUARD_EXCESS")
        self.assertEqual(engine.total_constraints, 1)

        # Prospective candidate with min_length=7 should be pruned immediately
        prospective = GatedGene(min_length=7, modulus=3, target_residue=0)
        is_pruned, reason = engine.check_pruning("task_k2", prospective)
        self.assertTrue(is_pruned)
        self.assertIn("blocks positive witness", str(reason))
        self.assertEqual(engine.pruned_candidates_count, 1)

        # Prospective candidate with min_length=3 should NOT be pruned
        valid_prospective = GatedGene(min_length=3, modulus=3, target_residue=0)
        is_pruned, _ = engine.check_pruning("task_k2", valid_prospective)
        self.assertFalse(is_pruned)

        # Verify persistence and reload
        reloaded = FailureConstraintEngine(storage_path=str(storage))
        self.assertEqual(reloaded.total_constraints, 1)

    def test_quality_diversity_archive(self) -> None:
        """Pillar 2: pyribs MAP-Elites grid coverage and novelty preservation."""
        storage = self.test_path / "qd.json"
        archive = QualityDiversityArchive(storage_path=str(storage))
        self.assertEqual(archive.total_niches, 15)
        self.assertEqual(archive.filled_niches, 0)

        # Candidate A: Linear tier (0), sparse predictions (10% positive)
        cand_a = CodeCandidate(
            candidate_id="cand_a",
            parent_id="root",
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
            source_code="def evaluate_mechanism(length, density, stride_val): return 1",
            source_sha="sha_a",
            gene_dict={"is_composite": False},
        )
        inserted, reason = archive.consider_candidate(cand_a, fitness=0.60, validation_predictions=[True, False, False, False, False] * 2)
        self.assertTrue(inserted)
        self.assertEqual(archive.filled_niches, 1)

        # Candidate B: Relational tier (3), balanced predictions (50% positive)
        cand_b = CodeCandidate(
            candidate_id="cand_b",
            parent_id="root",
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
            source_code="def evaluate_mechanism(length, density, stride_val): return 0",
            source_sha="sha_b",
            gene_dict={"is_relational": True},
        )
        inserted, _ = archive.consider_candidate(cand_b, fitness=0.85, validation_predictions=[True, False] * 5)
        self.assertTrue(inserted)
        self.assertEqual(archive.filled_niches, 2)
        self.assertGreater(archive.coverage, 0.10)

        # Sampling modes
        sampled_best = archive.sample_parent(mode="best")
        self.assertIsNotNone(sampled_best)
        self.assertEqual(sampled_best.candidate_id, "cand_b")

        summary = archive.to_summary_dict()
        self.assertEqual(summary["filled_niches"], 2)
        self.assertEqual(summary["max_fitness"], 0.85)

    def test_primitive_synthesizer(self) -> None:
        """Pillar 3: Stitch/DreamCoder library learning and AST pure extraction."""
        storage = self.test_path / "lib.json"
        synthesizer = PrimitiveSynthesizer(library_path=str(storage))

        cand = CodeCandidate(
            candidate_id="cand_relational_gated",
            parent_id="root",
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
            source_code="def evaluate_mechanism(length, density, stride_val): return 0",
            source_sha="sha_rel",
            gene_dict={
                "is_relational": True,
                "is_relational_gated": True,
                "modulus": 3,
                "stride_weight": 2,
                "density_weight": -1,
                "target_residue": 0,
            },
        )

        extracted = synthesizer.extract_primitives_from_candidate(
            candidate=cand,
            task_id="task_k2",
            validation_score=0.90,
        )
        self.assertGreaterEqual(len(extracted), 1)
        prim = extracted[0]
        self.assertIn("congruence_kernel_mod3", prim.name)

        # Verify strict AST compliance of the synthesized primitive
        ast_tree = ast.parse(prim.source_code)
        self.assertIsInstance(ast_tree, ast.Module)
        func_def = ast_tree.body[0]
        self.assertIsInstance(func_def, ast.FunctionDef)

        # Verify reload
        reloaded = PrimitiveSynthesizer(library_path=str(storage))
        self.assertEqual(reloaded.total_primitives, 1)

    def test_multi_task_g1_promotion_proof(self) -> None:
        """Pillar 4: Proof that multi-task composite dispatch crosses +0.1500 to achieve G1 promotion."""
        tasks = create_confirmation_suite(task_seed=42)
        holdout_banks = {tid: list(t.sealed_confirmation_holdout) for tid, t in tasks.items()}
        sealed_eval = SealedHoldoutEvaluator(
            manifest_id="manifest_proof_g1",
            holdout_banks=holdout_banks,
        )
        hc = HostController(
            evaluator=sealed_eval,
            budget=ExecutionBudget(max_execution_seconds=60.0, max_queries=500, max_candidates=20),
            sandbox_gate=HostSandboxGate(enforce_os_containment=False),
            root_candidate_id="G0_root",
            min_gain=0.1500,
            max_regression=0.0200,
        )
        root_fn = lambda w: (len(w) % 3 == 0)
        root_score = hc.initialize_root_score(root_fn)
        self.assertEqual(root_score, 0.6875)

        # Step 1: Single-task candidate on task_k2 (even with 100% score) achieves gain = +0.1250 < +0.1500 -> REJECTED
        def pred_k2_only(w, tid=""):
            if tid == "task_k2_modular_stride_shift":
                if len(w) < 4:
                    return False
                even_a = sum(1 for i, ch in enumerate(w) if i % 2 == 0 and ch == "a")
                odd_a = sum(1 for i, ch in enumerate(w) if i % 2 == 1 and ch == "a")
                return (even_a % 3) == (odd_a % 3)
            return root_fn(w)

        dec_single = hc.evaluate_and_gate(
            candidate_id="candidate_single_task_k2",
            parent_id="G0_root",
            generation=1,
            source_sha="11" * 32,
            candidate_fn=pred_k2_only,
            candidate_code_or_spec="def evaluate_mechanism(): pass",
        )
        self.assertEqual(dec_single.status, "REJECTED")
        self.assertAlmostEqual(dec_single.gain_over_parent, 0.1250, places=4)
        self.assertIn("below required min_gain 0.1500", " ".join(dec_single.rejection_reasons))

        # Step 2: Multi-task composite dispatch solving task_k2 (32/32) and task_j2 (30/32)
        def pred_j2(w):
            if len(w) < 3:
                return False
            c_start, c_end = w[0], w[-1]
            l1 = len(w) - len(w.lstrip(c_start))
            l2 = len(w) - len(w.rstrip(c_end))
            return (l1 == l2) and (w.count("a") % 2 == 0)

        def multi_task_dispatcher(w, tid=None):
            if tid == "task_k2_modular_stride_shift":
                return pred_k2_only(w, "task_k2_modular_stride_shift")
            elif tid == "task_j2_symmetric_run_boundary":
                return pred_j2(w)
            else:
                return root_fn(w)

        dec_multi = hc.evaluate_and_gate(
            candidate_id="G1_promoted_multitask_dispatcher",
            parent_id="G0_root",
            generation=1,
            source_sha="22" * 32,
            candidate_fn=multi_task_dispatcher,
            candidate_code_or_spec="def evaluate_mechanism(): pass",
        )

        # CERTIFIED G1 PROMOTION VERIFICATION
        self.assertEqual(dec_multi.status, "ACCEPTED")
        self.assertGreaterEqual(dec_multi.gain_over_parent, 0.1500)
        self.assertAlmostEqual(dec_multi.gain_over_parent, 0.1875, places=4)
        self.assertEqual(dec_multi.prior_regression, 0.0)
        self.assertEqual(len(dec_multi.rejection_reasons), 0)
        self.assertEqual(hc.lineage.nodes["G1_promoted_multitask_dispatcher"].status, "ACCEPTED")

    def test_coordinator_integration(self) -> None:
        """Pillar 5: Coordinator runs cycle and records deep research primitives."""
        coord = SelfDevelopmentCoordinator(
            checkpoint_dir=str(self.test_path / "checkpoints"),
            evidence_dir=str(self.test_path / "evidence"),
        )
        res = coord.run_autonomous_cycle(candidate_search_budget=2)
        self.assertIn("cycle_id", res)
        self.assertIn("decision", res)

        # Verify evidence gzip has deep research metadata
        evidence_file = Path(res["evidence_path"])
        self.assertTrue(evidence_file.exists())
        with gzip.open(evidence_file, "rt") as f:
            evidence_data = json.load(f)
        self.assertIn("deep_research_primitives", evidence_data)
        dr_prim = evidence_data["deep_research_primitives"]
        self.assertIn("failure_constraints_total", dr_prim)
        self.assertIn("qd_archive_coverage_pct", dr_prim)
        self.assertIn("synthesized_primitives_total", dr_prim)


if __name__ == "__main__":
    unittest.main()
