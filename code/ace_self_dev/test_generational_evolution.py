"""Comprehensive Unit Test Suite for Generational Progression (G0 -> G1 -> G2 -> Gn).

Tests all scientific pillars of generational capability evolution:
1. Generational Milestone Management (G0 -> G1 -> G2 -> Gn).
2. Primitive Extraction via PrimitiveSynthesizer and Registration in GenerationalLibrary.
3. Higher-Generation Candidate Synthesis Incorporating Primitives as First-Class Composite AST Nodes.
4. Cryptographic Lineage Tracking: Merkle Parent Hash Chaining, Candidate Source SHA,
   Promotion Receipts, and Empirical Validation Proofs.
5. Fail-Closed Lineage Governance (Rejection on low gain or regression, baseline retention).
6. Deterministic Persistence and Merkle Root Invariance Across Reloads.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest

from ace_loop.source_evolution import compute_sha, validate_ast
from ace_self_dev.confirmation_suite import ConfirmationTask, create_confirmation_suite
from ace_self_dev.generational_ladder import (
    GenerationalCandidateSynthesizer,
    GenerationalCompositeASTNode,
    GenerationalLadder,
    GenerationalLibrary,
    GenerationalMilestone,
)
from ace_self_dev.lineage_manager import (
    GENESIS_PARENT_HASH,
    CryptographicLineageNode,
    LineageManager,
    compute_node_merkle_hash,
)
from ace_self_dev.models import (
    AuthorType,
    CandidateDecision,
    CodeCandidate,
    EmpiricalValidationProof,
    PromotionReceipt,
    ResearchHypothesis,
)
from ace_self_dev.primitive_synthesizer import PrimitiveSynthesizer, SynthesizedPrimitive
from ace_self_dev.provenance_engine import ProvenanceEngine


class TestGenerationalEvolution(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.tmp_dir.name)
        self.tasks = create_confirmation_suite(task_seed=42)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_milestone_initialization_and_g0(self) -> None:
        """Pillar 1: Initialization of G0 genesis milestone and root cryptographic node."""
        ladder = GenerationalLadder(checkpoint_dir=str(self.test_path / "ladder"))
        m0 = ladder.initialize_g0(
            root_id="G0_root_seed",
            baseline_score=0.6875,
        )

        self.assertEqual(m0.generation, 0)
        self.assertEqual(m0.milestone_tag, "G0")
        self.assertEqual(m0.status, "CERTIFIED_PROMOTED")
        self.assertEqual(m0.active_head_id, "G0_root_seed")
        self.assertEqual(ladder.current_generation, 0)

        # Check cryptographic lineage root
        root_node = ladder.lineage.get_active_head()
        self.assertIsNotNone(root_node)
        self.assertEqual(root_node.candidate_id, "G0_root_seed")
        self.assertIsNone(root_node.parent_id)
        self.assertEqual(root_node.parent_merkle_hash, GENESIS_PARENT_HASH)
        self.assertEqual(root_node.generation, 0)

        # Verify chain integrity
        valid, msg = ladder.lineage.verify_chain_integrity()
        self.assertTrue(valid)
        self.assertIn("verified", msg)

    def test_g1_certified_promotion_and_primitive_extraction(self) -> None:
        """Pillar 2: Certified G1 promotion, primitive extraction & registration in GenerationalLibrary."""
        ladder = GenerationalLadder(checkpoint_dir=str(self.test_path / "ladder"))
        ladder.initialize_g0(baseline_score=0.6875)

        # Build high-performing G1 multi-task candidate solving task_k2 (modular stride) & task_j2 (symmetric run)
        root_fn = lambda w: (len(w) % 3 == 0)

        def pred_k2_only(w: str) -> bool:
            if len(w) < 4:
                return False
            even_a = sum(1 for i, ch in enumerate(w) if i % 2 == 0 and ch == "a")
            odd_a = sum(1 for i, ch in enumerate(w) if i % 2 == 1 and ch == "a")
            return (even_a % 3) == (odd_a % 3)

        def pred_j2(w: str) -> bool:
            if len(w) < 3:
                return False
            c_start, c_end = w[0], w[-1]
            l1 = len(w) - len(w.lstrip(c_start))
            l2 = len(w) - len(w.rstrip(c_end))
            return (l1 == l2) and (w.count("a") % 2 == 0)

        def g1_candidate_fn(w: str, tid: Optional[str] = None) -> bool:
            if tid == "task_k2_modular_stride_shift":
                return pred_k2_only(w)
            elif tid == "task_j2_symmetric_run_boundary":
                return pred_j2(w)
            return root_fn(w)

        g1_source = (
            "def evaluate_mechanism(length: int, density: int, stride_val: int) -> int:\n"
            "    return 0 if (((stride_val * 2 + density * -1) % 3) == 0) else 1\n"
        )
        g1_sha = compute_sha(g1_source.encode("utf-8"))

        g1_candidate = CodeCandidate(
            candidate_id="CAND_G1_relational_stride_shift",
            parent_id="G0_root_seed",
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
            source_code=g1_source,
            source_sha=g1_sha,
            gene_dict={
                "is_relational": True,
                "is_relational_gated": True,
                "modulus": 3,
                "stride_weight": 2,
                "density_weight": -1,
                "target_residue": 0,
            },
        )

        promoted, receipt, msg = ladder.evaluate_and_certify_promotion(
            candidate=g1_candidate,
            target_generation=1,
            task_suite=self.tasks,
            candidate_fn=g1_candidate_fn,
        )

        self.assertTrue(promoted)
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.generation, 1)
        self.assertEqual(receipt.candidate_id, "CAND_G1_relational_stride_shift")
        self.assertGreaterEqual(receipt.empirical_proof.gain_over_parent, 0.1500)
        self.assertEqual(receipt.empirical_proof.prior_regression, 0.0)

        # Verify active head advanced
        self.assertEqual(ladder.current_generation, 1)
        self.assertEqual(ladder.lineage.active_head_id, "CAND_G1_relational_stride_shift")

        # Verify primitive extraction and registration into GenerationalLibrary
        self.assertGreaterEqual(len(receipt.primitives_extracted), 1)
        g1_prims = ladder.library.get_primitives_for_generation(1)
        self.assertGreaterEqual(len(g1_prims), 1)
        prim = g1_prims[0]
        self.assertIn("congruence_kernel_mod3", prim.name)

        # AST safety check on extracted primitive
        prim_tree = ast.parse(prim.source_code)
        self.assertIsInstance(prim_tree.body[0], ast.FunctionDef)

    def test_g2_composite_ast_node_synthesis_and_validation(self) -> None:
        """Pillar 3: G2 candidate synthesis incorporating registered primitives as first-class composite AST nodes."""
        ladder = GenerationalLadder(checkpoint_dir=str(self.test_path / "ladder"))
        ladder.initialize_g0(baseline_score=0.6875)

        # Manually register two verified primitives into library (simulating G1 outputs)
        p1_code = (
            "def prim_congruence_m3_s2_d1(length: int, density: int, stride_val: int) -> int:\n"
            "    return 0 if ((((stride_val * 2) + (density * 1)) % 3) == 0) else 1\n"
        )
        p1 = SynthesizedPrimitive(
            primitive_id="PRIM_test_congruence",
            name="congruence_kernel_mod3",
            signature="(length: int, density: int, stride_val: int) -> int",
            expression_body="(((stride_val * 2) + (density * 1)) % 3) == 0",
            source_code=p1_code,
            source_sha=compute_sha(p1_code.encode("utf-8")),
            complexity_cost=4,
            compression_value=1.45,
            discovered_task_id="task_k2",
            origin_candidate_id="cand_g1",
        )
        ladder.library.register_primitive(p1, generation=1, candidate_id="cand_g1")

        p2_code = (
            "def prim_balance_s2_d1(length: int, density: int, stride_val: int) -> int:\n"
            "    return 0 if (((stride_val * 2) - density) == 0) else 1\n"
        )
        p2 = SynthesizedPrimitive(
            primitive_id="PRIM_test_balance",
            name="stride_density_balance",
            signature="(length: int, density: int, stride_val: int) -> int",
            expression_body="((stride_val * 2) - density) == 0",
            source_code=p2_code,
            source_sha=compute_sha(p2_code.encode("utf-8")),
            complexity_cost=3,
            compression_value=1.35,
            discovered_task_id="task_j2",
            origin_candidate_id="cand_g1",
        )
        ladder.library.register_primitive(p2, generation=1, candidate_id="cand_g1")

        # Test First-Class Composite AST Nodes across operators
        for op in ("XOR", "AND", "OR", "ADD", "IF_ELSE"):
            composite = GenerationalCompositeASTNode(
                operator=op,
                left_primitive=p1,
                right_primitive=p2,
                guard_condition="(length >= 4)",
                generation=2,
            )
            # Verify AST safety
            self.assertTrue(composite.validate_ast_safety())

            # Verify AST node generation
            func_def = composite.to_ast()
            self.assertEqual(func_def.name, "evaluate_mechanism")

            # Verify compilation and execution
            compiled_fn = composite.compile()
            res = compiled_fn(length=6, density=2, stride_val=1)
            self.assertIsInstance(res, int)

        # Synthesize G2 candidate via GenerationalCandidateSynthesizer
        hyp = ResearchHypothesis(
            hypothesis_id="hyp_g2_composite_transfer",
            statement="Synthesize G2 composite XOR across modular congruence and balance primitives",
            target_task_id="task_k1",
        )
        cand_g2 = ladder.synthesizer.synthesize_candidate(
            target_generation=2,
            hypothesis=hyp,
            operator="XOR",
        )

        self.assertIn("CAND_G2", cand_g2.candidate_id)
        self.assertTrue(cand_g2.gene_dict["is_generational_composite"])
        self.assertEqual(cand_g2.gene_dict["generation"], 2)
        self.assertEqual(cand_g2.gene_dict["operator"], "XOR")
        self.assertEqual(cand_g2.gene_dict["left_primitive_id"], "PRIM_test_congruence")
        self.assertEqual(cand_g2.gene_dict["right_primitive_id"], "PRIM_test_balance")

        # AST compliance on generated candidate source
        validate_ast(cand_g2.source_code.encode("utf-8"), expected_name="evaluate_mechanism")

    def test_end_to_end_generational_progression_g0_to_g2(self) -> None:
        """Pillar 4: End-to-end milestone progression G0 -> G1 -> G2 with certified receipts."""
        ladder = GenerationalLadder(checkpoint_dir=str(self.test_path / "ladder"))
        ladder.initialize_g0(baseline_score=0.5000)

        # --- STEP 1: Evolve G0 -> G1 ---
        root_fn = lambda w: False  # flat parity baseline giving 0.50 on balanced holdouts

        def pred_k2_only(w: str) -> bool:
            if len(w) < 4:
                return False
            even_a = sum(1 for i, ch in enumerate(w) if i % 2 == 0 and ch == "a")
            odd_a = sum(1 for i, ch in enumerate(w) if i % 2 == 1 and ch == "a")
            return (even_a % 3) == (odd_a % 3)

        def pred_j2(w: str) -> bool:
            if len(w) < 3:
                return False
            c_start, c_end = w[0], w[-1]
            l1 = len(w) - len(w.lstrip(c_start))
            l2 = len(w) - len(w.rstrip(c_end))
            return (l1 == l2) and (w.count("a") % 2 == 0)

        def g1_fn(w: str, tid: Optional[str] = None) -> bool:
            if tid == "task_k2_modular_stride_shift":
                return pred_k2_only(w)
            elif tid == "task_j2_symmetric_run_boundary":
                return pred_j2(w)
            return root_fn(w)

        g1_source = (
            "def evaluate_mechanism(length: int, density: int, stride_val: int) -> int:\n"
            "    return 0 if (((stride_val * 2 + density * -1) % 3) == 0) else 1\n"
        )
        cand_g1 = CodeCandidate(
            candidate_id="CAND_G1_milestone_head",
            parent_id="G0_root_seed",
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
            source_code=g1_source,
            source_sha=compute_sha(g1_source.encode("utf-8")),
            gene_dict={
                "is_relational": True,
                "is_relational_gated": True,
                "modulus": 3,
                "stride_weight": 2,
                "density_weight": -1,
                "target_residue": 0,
            },
        )
        promoted_g1, receipt_g1, _ = ladder.evaluate_and_certify_promotion(
            candidate=cand_g1,
            target_generation=1,
            task_suite=self.tasks,
            candidate_fn=g1_fn,
        )
        self.assertTrue(promoted_g1)
        self.assertEqual(ladder.current_generation, 1)

        # --- STEP 2: Evolve G1 -> G2 ---
        # Add a complementary primitive to library for G2 composition
        prim_balance_code = (
            "def prim_balance_s1_d1(length: int, density: int, stride_val: int) -> int:\n"
            "    return 0 if ((stride_val - density) == 0) else 1\n"
        )
        prim_balance = SynthesizedPrimitive(
            primitive_id="PRIM_stride_balance",
            name="stride_balance_equal",
            signature="(length: int, density: int, stride_val: int) -> int",
            expression_body="(stride_val - density) == 0",
            source_code=prim_balance_code,
            source_sha=compute_sha(prim_balance_code.encode("utf-8")),
            complexity_cost=2,
            compression_value=1.25,
            discovered_task_id="task_j2",
            origin_candidate_id="CAND_G1_milestone_head",
        )
        ladder.library.register_primitive(prim_balance, generation=1, candidate_id="CAND_G1_milestone_head")

        # Synthesize G2 candidate
        hyp_g2 = ResearchHypothesis(
            hypothesis_id="hyp_g2_modular_balance",
            statement="G2 recursive composition of congruence and balance",
            target_task_id="task_k1",
        )
        cand_g2 = ladder.synthesizer.synthesize_candidate(
            target_generation=2,
            hypothesis=hyp_g2,
            parent_candidate=cand_g1,
            operator="IF_ELSE",
            guard_condition="(length >= 4)",
        )

        # Higher-order solver covering task_k2, task_j2, task_k1 (center pivot), and task_j1 (multiscale run parity)
        def pred_k1(w: str) -> bool:
            if len(w) < 3 or len(w) % 2 == 0:
                return False
            mid = len(w) // 2
            pivot = w[mid]
            left, right = w[:mid], w[mid + 1:]
            return left.count("a") == right.count("a") if pivot == "a" else left.count("b") == right.count("b")

        def pred_j1(w: str) -> bool:
            if not w:
                return True
            runs = []
            c, cnt = w[0], 1
            for ch in w[1:]:
                if ch == c:
                    cnt += 1
                else:
                    runs.append(cnt)
                    c = ch
                    cnt = 1
            runs.append(cnt)
            for i in range(len(runs) - 1):
                if (runs[i] % 2) == (runs[i + 1] % 2):
                    return False
            return True

        def g2_fn(w: str, tid: Optional[str] = None) -> bool:
            if tid == "task_k2_modular_stride_shift":
                return pred_k2_only(w)
            elif tid == "task_j2_symmetric_run_boundary":
                return pred_j2(w)
            elif tid == "task_k1_center_pivot_density":
                return pred_k1(w)
            elif tid == "task_j1_multiscale_run_parity":
                return pred_j1(w)
            return root_fn(w)

        promoted_g2, receipt_g2, _ = ladder.evaluate_and_certify_promotion(
            candidate=cand_g2,
            target_generation=2,
            task_suite=self.tasks,
            candidate_fn=g2_fn,
        )
        self.assertTrue(promoted_g2)
        self.assertEqual(ladder.current_generation, 2)
        self.assertEqual(ladder.lineage.active_head_id, cand_g2.candidate_id)

        # Verify all milestones present
        self.assertEqual(set(ladder.milestones.keys()), {0, 1, 2})
        self.assertEqual(ladder.milestones[0].status, "CERTIFIED_PROMOTED")
        self.assertEqual(ladder.milestones[1].status, "CERTIFIED_PROMOTED")
        self.assertEqual(ladder.milestones[2].status, "CERTIFIED_PROMOTED")

        # Verify ladder cryptographic integrity end-to-end
        valid_ladder, logs = ladder.verify_ladder_integrity()
        self.assertTrue(valid_ladder)
        self.assertGreaterEqual(len(logs), 3)

    def test_cryptographic_merkle_parent_hash_chaining(self) -> None:
        """Pillar 5: Merkle parent hash chaining, tamper detection & receipt signature verification."""
        mgr = LineageManager(storage_path=str(self.test_path / "crypto_lineage.json"))
        root = mgr.register_root(root_id="G0_root", source_sha="00" * 32, baseline_score=0.50)

        # Chaining G0 -> G1
        cand_g1 = mgr.register_candidate(
            candidate_id="G1_cand",
            parent_id="G0_root",
            generation=1,
            source_sha="11" * 32,
        )
        self.assertEqual(cand_g1.parent_merkle_hash, root.merkle_node_hash)

        # G1 promotion receipt
        proof_g1 = EmpiricalValidationProof(
            proof_id="proof_g1",
            candidate_id="G1_cand",
            parent_id="G0_root",
            generation=1,
            holdout_score=0.75,
            baseline_score=0.50,
            gain_over_parent=0.25,
            prior_regression=0.0,
            task_scores={"t1": 0.75},
            evaluator_manifest_digest="man_1",
            witness_count=32,
            proof_digest="digest_proof_1",
            timestamp="2026-11-07T00:00:00Z",
        )
        rec_g1 = PromotionReceipt(
            receipt_id="rec_g1",
            generation=1,
            candidate_id="G1_cand",
            parent_id="G0_root",
            source_sha="11" * 32,
            parent_merkle_hash=root.merkle_node_hash,
            merkle_node_hash=compute_node_merkle_hash(root.merkle_node_hash, "G1_cand", "11" * 32, 1, "digest_proof_1"),
            empirical_proof=proof_g1,
            primitives_extracted=["prim_1"],
            receipt_signature="sig_g1",
            key_fingerprint="fp_1",
            timestamp="2026-11-07T00:00:00Z",
        )
        prom_node_g1 = mgr.record_promotion("G1_cand", receipt=rec_g1)
        self.assertEqual(mgr.active_head_id, "G1_cand")

        # Chaining G1 -> G2
        cand_g2 = mgr.register_candidate(
            candidate_id="G2_cand",
            parent_id="G1_cand",
            generation=2,
            source_sha="22" * 32,
        )
        self.assertEqual(cand_g2.parent_merkle_hash, prom_node_g1.merkle_node_hash)

        # Verify chain integrity G0 -> G1 -> G2
        valid, _ = mgr.verify_chain_integrity("G2_cand")
        self.assertTrue(valid)

        # Verify lineage path
        path = mgr.get_lineage_path("G2_cand")
        self.assertEqual([n.candidate_id for n in path], ["G0_root", "G1_cand", "G2_cand"])

        # Tamper Detection 1: Tamper with G1 source SHA in node
        mgr.nodes["G1_cand"].source_sha = "ff" * 32
        valid_tampered, tamper_msg = mgr.verify_chain_integrity("G2_cand")
        self.assertFalse(valid_tampered)
        self.assertIn("Merkle hash mismatch", tamper_msg)

        # Restore G1
        mgr.nodes["G1_cand"].source_sha = "11" * 32
        valid_restored, _ = mgr.verify_chain_integrity("G2_cand")
        self.assertTrue(valid_restored)

        # Tamper Detection 2: Tamper with parent Merkle hash
        mgr.nodes["G2_cand"].parent_merkle_hash = "deadbeef" * 8
        valid_parent_tamper, msg2 = mgr.verify_chain_integrity("G2_cand")
        self.assertFalse(valid_parent_tamper)
        self.assertIn("Merkle chain break", msg2)

    def test_fail_closed_governance_and_regression_blocking(self) -> None:
        """Pillar 6: Fail-closed governance blocks promotions with low gain or high regression."""
        ladder = GenerationalLadder(
            checkpoint_dir=str(self.test_path / "ladder_fail_closed"),
            min_gain=0.1500,
            max_regression=0.0200,
        )
        ladder.initialize_g0(baseline_score=0.6875)

        # Test Case A: Sub-threshold gain (+0.0500 < +0.1500)
        def low_gain_fn(w: str, tid: Optional[str] = None) -> bool:
            return len(w) % 3 == 0  # unchanged baseline

        cand_low = CodeCandidate(
            candidate_id="CAND_insufficient_gain",
            parent_id="G0_root_seed",
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
            source_code="def evaluate_mechanism(length, density, stride_val): return 0\n",
            source_sha="33" * 32,
            gene_dict={"is_composite": False},
        )
        promoted, receipt, reason = ladder.evaluate_and_certify_promotion(
            candidate=cand_low,
            target_generation=1,
            task_suite=self.tasks,
            candidate_fn=low_gain_fn,
        )
        self.assertFalse(promoted)
        self.assertIsNone(receipt)
        self.assertIn("Insufficient holdout gain", reason)
        self.assertEqual(ladder.current_generation, 0)
        self.assertEqual(ladder.lineage.active_head_id, "G0_root_seed")
        self.assertEqual(ladder.lineage.nodes["CAND_insufficient_gain"].status, "REJECTED")

        # Test Case B: Regression on established baseline
        # Assume active head had established scores
        ladder.lineage.nodes["G0_root_seed"].metadata["task_scores"] = {
            "task_j1_multiscale_run_parity": 0.90,
        }

        def regressive_fn(w: str, tid: Optional[str] = None) -> bool:
            if tid == "task_j1_multiscale_run_parity":
                return False  # severe regression to 0.0
            return True

        cand_regr = CodeCandidate(
            candidate_id="CAND_regressive",
            parent_id="G0_root_seed",
            author_type=AuthorType.ACE_AUTONOMOUS_V02,
            source_code="def evaluate_mechanism(length, density, stride_val): return 1\n",
            source_sha="44" * 32,
            gene_dict={"is_composite": False},
        )
        promoted_regr, _, regr_reason = ladder.evaluate_and_certify_promotion(
            candidate=cand_regr,
            target_generation=1,
            task_suite=self.tasks,
            candidate_fn=regressive_fn,
        )
        self.assertFalse(promoted_regr)
        self.assertIn("Regression exceeded", regr_reason)
        self.assertEqual(ladder.lineage.active_head_id, "G0_root_seed")

    def test_library_merkle_root_and_state_persistence(self) -> None:
        """Pillar 7: Deterministic Merkle root of GenerationalLibrary and crash-resilient persistence."""
        lib_path = self.test_path / "persisted_lib.json"
        lib = GenerationalLibrary(storage_path=str(lib_path))

        # Empty root
        empty_root = lib.compute_library_merkle_root()
        self.assertEqual(empty_root, hashlib.sha256(b"EMPTY_GENERATIONAL_LIBRARY").hexdigest())

        # Register Primitive 1
        p1_code = "def prim_one(length: int, density: int, stride_val: int) -> int: return 0\n"
        prim1 = SynthesizedPrimitive(
            primitive_id="PRIM_001",
            name="prim_one",
            signature="(length: int, density: int, stride_val: int) -> int",
            expression_body="0",
            source_code=p1_code,
            source_sha=compute_sha(p1_code.encode("utf-8")),
            complexity_cost=1,
            compression_value=1.1,
            discovered_task_id="task_j1",
            origin_candidate_id="cand_1",
        )
        lib.register_primitive(prim1, generation=1, candidate_id="cand_1")
        root_after_p1 = lib.compute_library_merkle_root()
        self.assertNotEqual(empty_root, root_after_p1)

        # Register Primitive 2
        p2_code = "def prim_two(length: int, density: int, stride_val: int) -> int: return 1\n"
        prim2 = SynthesizedPrimitive(
            primitive_id="PRIM_002",
            name="prim_two",
            signature="(length: int, density: int, stride_val: int) -> int",
            expression_body="1",
            source_code=p2_code,
            source_sha=compute_sha(p2_code.encode("utf-8")),
            complexity_cost=1,
            compression_value=1.1,
            discovered_task_id="task_k1",
            origin_candidate_id="cand_2",
        )
        lib.register_primitive(prim2, generation=2, candidate_id="cand_2")
        root_after_p2 = lib.compute_library_merkle_root()
        self.assertNotEqual(root_after_p1, root_after_p2)

        # Reload from disk
        reloaded_lib = GenerationalLibrary(storage_path=str(lib_path))
        self.assertEqual(reloaded_lib.total_primitives, 2)
        self.assertEqual(reloaded_lib.compute_library_merkle_root(), root_after_p2)

        # Verify generation separation
        g1_prims = reloaded_lib.get_primitives_for_generation(1)
        g2_prims = reloaded_lib.get_primitives_for_generation(2)
        self.assertEqual(len(g1_prims), 1)
        self.assertEqual(len(g2_prims), 1)
        self.assertEqual(g1_prims[0].primitive_id, "PRIM_001")
        self.assertEqual(g2_prims[0].primitive_id, "PRIM_002")


if __name__ == "__main__":
    unittest.main()
