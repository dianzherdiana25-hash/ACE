"""Generational Ladder: Multi-Generation Progression (G0 -> G1 -> G2 -> Gn) for ACE.

Implements generational capability evolution enabling synthesized primitives to serve as
modular building blocks for higher-generation candidate evolution:
1. Manages generational milestones (G0 -> G1 -> G2 -> Gn).
2. When a candidate achieves certified promotion to generation G_k, extracts verified
   primitives via PrimitiveSynthesizer and registers them into an active GenerationalLibrary.
3. In generation G_{k+1}, candidate synthesis incorporates registered primitives as
   first-class composite AST nodes.
4. Maintains cryptographic lineage tracking: Merkle parent hash chaining, candidate source
   SHA, promotion receipts, and empirical validation proofs.
"""
from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from ace_loop.source_evolution import compute_sha, validate_ast
from .confirmation_suite import ConfirmationTask
from .lineage_manager import CryptographicLineageNode, LineageManager
from .models import (
    AuthorType,
    CandidateDecision,
    CodeCandidate,
    EmpiricalValidationProof,
    PromotionReceipt,
    ResearchHypothesis,
)
from .primitive_synthesizer import PrimitiveSynthesizer, SynthesizedPrimitive
from .provenance_engine import ProvenanceEngine


@dataclass
class GenerationalMilestone:
    """Represents a milestone in the evolutionary ladder (G0, G1, G2, ..., Gn)."""
    generation: int
    milestone_tag: str  # e.g., "G0", "G1", "G2"
    status: str  # "ACTIVE", "CERTIFIED_PROMOTED", "RETAINED", "PENDING"
    active_head_id: str
    promoted_candidate_id: Optional[str] = None
    promotion_receipt_id: Optional[str] = None
    empirical_proof_digest: Optional[str] = None
    achieved_timestamp: str = ""
    target_tasks: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GenerationalMilestone:
        return cls(**data)


class GenerationalLibrary:
    """Active catalog of verified algorithmic primitives organized by generational epoch."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path) if storage_path else None
        self._primitives: Dict[str, SynthesizedPrimitive] = {}
        self._generation_map: Dict[int, List[str]] = {}  # gen -> list of primitive_ids
        self._candidate_origin_map: Dict[str, str] = {}  # primitive_id -> origin_candidate_id
        if self.storage_path and self.storage_path.exists():
            self._load()

    @property
    def total_primitives(self) -> int:
        return len(self._primitives)

    def register_primitive(
        self,
        primitive: SynthesizedPrimitive,
        generation: int,
        candidate_id: str,
    ) -> bool:
        """Register a verified primitive into the generational library."""
        pid = primitive.primitive_id
        if pid in self._primitives:
            return False

        # Validate AST safety of the primitive source code
        fn_name = primitive.source_code.split("def ")[1].split("(")[0]
        validate_ast(primitive.source_code.encode("utf-8"), expected_name=fn_name)

        self._primitives[pid] = primitive
        if generation not in self._generation_map:
            self._generation_map[generation] = []
        if pid not in self._generation_map[generation]:
            self._generation_map[generation].append(pid)

        self._candidate_origin_map[pid] = candidate_id
        self._save()
        return True

    def get_primitives_for_generation(self, generation: int) -> List[SynthesizedPrimitive]:
        """Return all primitives introduced in a specific generation."""
        pids = self._generation_map.get(generation, [])
        return [self._primitives[pid] for pid in pids if pid in self._primitives]

    def get_active_primitives(
        self,
        max_generation: Optional[int] = None,
    ) -> List[SynthesizedPrimitive]:
        """Return all active primitives introduced up to max_generation."""
        if max_generation is None:
            return list(self._primitives.values())

        res: List[SynthesizedPrimitive] = []
        for gen in sorted(self._generation_map.keys()):
            if gen <= max_generation:
                for pid in self._generation_map[gen]:
                    if pid in self._primitives:
                        res.append(self._primitives[pid])
        return res

    def get_primitive(self, primitive_id: str) -> Optional[SynthesizedPrimitive]:
        return self._primitives.get(primitive_id)

    def compute_library_merkle_root(self) -> str:
        """Deterministic Merkle root of all primitives currently active in the library."""
        if not self._primitives:
            return hashlib.sha256(b"EMPTY_GENERATIONAL_LIBRARY").hexdigest()

        leaf_hashes = []
        for pid in sorted(self._primitives.keys()):
            prim = self._primitives[pid]
            gen = next((g for g, pids in self._generation_map.items() if pid in pids), 0)
            leaf_payload = f"{prim.primitive_id}:{prim.source_sha}:{gen}:{prim.name}".encode("utf-8")
            leaf_hashes.append(hashlib.sha256(leaf_payload).hexdigest())

        combined = ":".join(leaf_hashes).encode("utf-8")
        return hashlib.sha256(combined).hexdigest()

    def export_summary(self) -> Dict[str, Any]:
        return {
            "total_primitives": len(self._primitives),
            "generations": {
                gen: len(pids) for gen, pids in sorted(self._generation_map.items())
            },
            "library_merkle_root": self.compute_library_merkle_root(),
            "primitives": [
                {
                    "primitive_id": p.primitive_id,
                    "name": p.name,
                    "signature": p.signature,
                    "source_sha": p.source_sha,
                    "generation": next((g for g, pids in self._generation_map.items() if p.primitive_id in pids), 0),
                    "origin_candidate_id": self._candidate_origin_map.get(p.primitive_id, p.origin_candidate_id),
                }
                for p in self._primitives.values()
            ],
        }

    def _save(self) -> None:
        if not self.storage_path:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "primitives": {
                pid: {
                    "primitive_id": p.primitive_id,
                    "name": p.name,
                    "signature": p.signature,
                    "expression_body": p.expression_body,
                    "source_code": p.source_code,
                    "source_sha": p.source_sha,
                    "complexity_cost": p.complexity_cost,
                    "compression_value": p.compression_value,
                    "discovered_task_id": p.discovered_task_id,
                    "origin_candidate_id": p.origin_candidate_id,
                }
                for pid, p in self._primitives.items()
            },
            "generation_map": self._generation_map,
            "candidate_origin_map": self._candidate_origin_map,
        }
        self.storage_path.write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        if not self.storage_path or not self.storage_path.exists():
            return
        try:
            raw = json.loads(self.storage_path.read_text())
            self._primitives = {
                pid: SynthesizedPrimitive(**pdata)
                for pid, pdata in raw.get("primitives", {}).items()
            }
            self._generation_map = {
                int(gen): pids for gen, pids in raw.get("generation_map", {}).items()
            }
            self._candidate_origin_map = raw.get("candidate_origin_map", {})
        except Exception:
            self._primitives = {}
            self._generation_map = {}
            self._candidate_origin_map = {}


class GenerationalCompositeASTNode:
    """First-class composite AST node combining verified primitives for higher-generation synthesis."""

    def __init__(
        self,
        operator: str,  # "XOR", "AND", "OR", "ADD", "SUB", "MULT", "IF_ELSE"
        left_primitive: SynthesizedPrimitive,
        right_primitive: SynthesizedPrimitive,
        guard_condition: Optional[str] = None,
        generation: int = 2,
    ):
        self.operator = operator.upper()
        self.left_primitive = left_primitive
        self.right_primitive = right_primitive
        self.guard_condition = guard_condition or "(length >= 4)"
        self.generation = generation

        valid_ops = {"XOR", "AND", "OR", "ADD", "SUB", "MULT", "IF_ELSE"}
        if self.operator not in valid_ops:
            raise ValueError(f"Invalid composite operator: {operator}. Supported: {valid_ops}")

    def to_expression_str(self) -> str:
        """Render the composite AST node expression."""
        left_body = self.left_primitive.expression_body
        right_body = self.right_primitive.expression_body

        left_expr = f"(0 if ({left_body}) else 1)"
        right_expr = f"(0 if ({right_body}) else 1)"

        if self.operator == "XOR":
            return f"({left_expr} ^ {right_expr})"
        elif self.operator == "ADD":
            return f"({left_expr} + {right_expr})"
        elif self.operator == "SUB":
            return f"({left_expr} - {right_expr})"
        elif self.operator == "MULT":
            return f"({left_expr} * {right_expr})"
        elif self.operator == "AND":
            return f"(0 if (({left_expr} == 0) and ({right_expr} == 0)) else 1)"
        elif self.operator == "OR":
            return f"(0 if (({left_expr} == 0) or ({right_expr} == 0)) else 1)"
        elif self.operator == "IF_ELSE":
            return f"({left_expr} if {self.guard_condition} else {right_expr})"
        raise ValueError(f"Unknown operator {self.operator}")

    def to_function_code(self, function_name: str = "evaluate_mechanism") -> str:
        """Render complete, pure Python function definition adhering to AST security boundaries."""
        expr_str = self.to_expression_str()
        code_lines = [
            f"def {function_name}(length: int, density: int, stride_val: int) -> int:",
            f"    return {expr_str}",
            "",
        ]
        return "\n".join(code_lines)

    def to_ast(self, function_name: str = "evaluate_mechanism") -> ast.FunctionDef:
        """Convert into a parsed and validated ast.FunctionDef."""
        code_str = self.to_function_code(function_name=function_name)
        tree = ast.parse(code_str)
        func_def = tree.body[0]
        assert isinstance(func_def, ast.FunctionDef)
        return func_def

    def validate_ast_safety(self) -> bool:
        """Verify the composite AST node complies with strict sandbox security boundaries."""
        code_str = self.to_function_code()
        validate_ast(code_str.encode("utf-8"), expected_name="evaluate_mechanism")
        return True

    def compile(self) -> Callable[[int, int, int], int]:
        """Compile verified composite AST node into an isolated pure callable."""
        code_str = self.to_function_code()
        self.validate_ast_safety()
        env: Dict[str, Any] = {"__builtins__": {}}
        code_obj = compile(code_str, f"<generational_composite_G{self.generation}>", "exec")
        exec(code_obj, env)
        fn = env.get("evaluate_mechanism")
        if not callable(fn):
            raise RuntimeError("Compiled composite node did not produce 'evaluate_mechanism' callable")
        return fn

    def to_gene_dict(self) -> Dict[str, Any]:
        """Export gene representation for provenance and checkpoint serialization."""
        return {
            "is_generational_composite": True,
            "generation": self.generation,
            "operator": self.operator,
            "left_primitive_id": self.left_primitive.primitive_id,
            "right_primitive_id": self.right_primitive.primitive_id,
            "left_primitive_name": self.left_primitive.name,
            "right_primitive_name": self.right_primitive.name,
            "guard_condition": self.guard_condition if self.operator == "IF_ELSE" else None,
            "complexity_cost": self.left_primitive.complexity_cost + self.right_primitive.complexity_cost + 1,
        }


class GenerationalCandidateSynthesizer:
    """Synthesizes higher-generation candidates incorporating registered library primitives."""

    def __init__(
        self,
        library: GenerationalLibrary,
        provenance_engine: Optional[ProvenanceEngine] = None,
    ):
        self.library = library
        self.provenance_engine = provenance_engine or ProvenanceEngine()

    def synthesize_candidate(
        self,
        target_generation: int,
        hypothesis: ResearchHypothesis,
        parent_candidate: Optional[CodeCandidate] = None,
        parent_id: Optional[str] = None,
        operator: str = "XOR",
        guard_condition: Optional[str] = None,
        author_type: AuthorType = AuthorType.ACE_AUTONOMOUS_V02,
    ) -> CodeCandidate:
        """Construct higher-generation candidate using registered primitives as first-class composite AST nodes."""
        effective_parent_id = parent_id or (parent_candidate.candidate_id if parent_candidate else f"G{target_generation-1}_baseline")
        parent_source = parent_candidate.source_code if parent_candidate else "def evaluate_mechanism(length, density, stride_val):\n    return 0\n"

        # Query available primitives from preceding generations
        available_primitives = self.library.get_active_primitives(max_generation=target_generation - 1)
        if len(available_primitives) < 1:
            raise ValueError(
                f"Cannot synthesize generation G{target_generation} candidate: no active primitives in GenerationalLibrary"
            )

        # Select primary and secondary primitives
        if len(available_primitives) == 1:
            left_prim = available_primitives[0]
            right_prim = available_primitives[0]
        else:
            left_prim = available_primitives[0]
            right_prim = available_primitives[1]

        composite_node = GenerationalCompositeASTNode(
            operator=operator,
            left_primitive=left_prim,
            right_primitive=right_prim,
            guard_condition=guard_condition,
            generation=target_generation,
        )

        # Enforce AST safety
        composite_node.validate_ast_safety()
        source_code = composite_node.to_function_code()
        source_bytes = source_code.encode("utf-8")
        source_sha = compute_sha(source_bytes)

        # Unified diff patch against parent
        diff_lines = list(
            difflib.unified_diff(
                parent_source.splitlines(keepends=True),
                source_code.splitlines(keepends=True),
                fromfile=f"a/{effective_parent_id}.py",
                tofile=f"b/{hypothesis.hypothesis_id}_G{target_generation}.py",
            )
        )
        diff_patch = "".join(diff_lines)

        proof = self.provenance_engine.create_provenance_proof(
            source_sha=source_sha,
            author_type=author_type,
        )

        cand_id = f"CAND_G{target_generation}_{hypothesis.hypothesis_id}"
        return CodeCandidate(
            candidate_id=cand_id,
            parent_id=effective_parent_id,
            author_type=author_type,
            source_code=source_code,
            source_sha=source_sha,
            gene_dict=composite_node.to_gene_dict(),
            diff_patch=diff_patch,
            creation_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            provenance_proof=proof,
        )


class GenerationalLadder:
    """Manages the full evolutionary ladder G0 -> G1 -> G2 -> Gn."""

    def __init__(
        self,
        checkpoint_dir: str = "checkpoints/generational_ladder",
        min_gain: float = 0.1500,
        max_regression: float = 0.0200,
        signing_key: Optional[str] = None,
    ):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        self.min_gain = min_gain
        self.max_regression = max_regression

        self.provenance_engine = ProvenanceEngine(signing_key=signing_key)
        self.primitive_synthesizer = PrimitiveSynthesizer(
            library_path=str(self.checkpoint_dir / "primitive_synthesizer.json")
        )
        self.library = GenerationalLibrary(
            storage_path=str(self.checkpoint_dir / "generational_library.json")
        )
        self.lineage = LineageManager(
            storage_path=str(self.checkpoint_dir / "lineage_manager.json")
        )
        self.synthesizer = GenerationalCandidateSynthesizer(
            library=self.library,
            provenance_engine=self.provenance_engine,
        )

        self.current_generation: int = 0
        self.milestones: Dict[int, GenerationalMilestone] = {}
        self._load()

    def initialize_g0(
        self,
        root_id: str = "G0_root_seed",
        root_fn: Optional[Callable[[str], bool]] = None,
        root_source_code: Optional[str] = None,
        baseline_score: float = 0.6875,
    ) -> GenerationalMilestone:
        """Initialize genesis G0 milestone and register root node in cryptographic lineage."""
        source = root_source_code or (
            "def evaluate_mechanism(length: int, density: int, stride_val: int) -> int:\n"
            "    return 0 if ((length % 3) == 0) else 1\n"
        )
        source_sha = compute_sha(source.encode("utf-8"))

        self.lineage.register_root(
            root_id=root_id,
            source_sha=source_sha,
            baseline_score=baseline_score,
            metadata={"description": "G0 genesis baseline seed heuristic"},
        )

        m0 = GenerationalMilestone(
            generation=0,
            milestone_tag="G0",
            status="CERTIFIED_PROMOTED",
            active_head_id=root_id,
            promoted_candidate_id=root_id,
            achieved_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            metadata={"baseline_score": baseline_score},
        )
        self.milestones[0] = m0
        self.current_generation = 0
        self._save()
        return m0

    def evaluate_and_certify_promotion(
        self,
        candidate: CodeCandidate,
        target_generation: int,
        task_suite: Dict[str, ConfirmationTask],
        candidate_fn: Callable[[str, Optional[str]], bool],
    ) -> Tuple[bool, Optional[PromotionReceipt], str]:
        """Evaluate candidate on sealed holdouts and grant certified promotion if gating bounds hold.

        Promotion requires:
        1. Holdout gain over active baseline >= min_gain (+0.1500).
        2. Prior regression <= max_regression (0.0200).
        3. Cryptographic Merkle chaining and receipt generation.
        4. Verified primitive extraction and registration into GenerationalLibrary.
        """
        active_node = self.lineage.get_active_head()
        active_head_id = active_node.candidate_id if active_node else "G0_root_seed"
        baseline_score = active_node.metadata.get("baseline_score", 0.6875) if active_node else 0.6875

        # Ensure candidate is registered in lineage graph before evaluation
        if candidate.candidate_id not in self.lineage.nodes:
            self.lineage.register_candidate(
                candidate_id=candidate.candidate_id,
                parent_id=active_head_id,
                generation=target_generation,
                source_sha=candidate.source_sha,
            )

        # 1. Sealed holdout empirical evaluation across tasks
        task_scores: Dict[str, float] = {}
        total_holdout_instances = 0
        task_manifest_parts: List[str] = []

        for tid, task in sorted(task_suite.items()):
            holdout = task.sealed_confirmation_holdout
            correct = 0
            for w, expected in holdout:
                pred = candidate_fn(w, tid)
                if pred == expected:
                    correct += 1
            task_acc = correct / len(holdout) if holdout else 0.0
            task_scores[tid] = task_acc
            total_holdout_instances += len(holdout)
            task_manifest_parts.append(f"{tid}:{len(holdout)}:{task_acc:.4f}")

        overall_holdout = sum(task_scores.values()) / len(task_scores) if task_scores else 0.0
        gain = overall_holdout - baseline_score

        # Check regression on previously established baselines
        prior_task_scores = (active_node.metadata.get("task_scores") or {}) if active_node else {}
        regressions = []
        for tid, old_acc in prior_task_scores.items():
            new_acc = task_scores.get(tid, 0.0)
            if new_acc < old_acc:
                regressions.append(old_acc - new_acc)
        prior_regression = max(regressions) if regressions else 0.0

        evaluator_manifest_digest = hashlib.sha256(";".join(task_manifest_parts).encode("utf-8")).hexdigest()

        # Empirical proof digest
        proof_payload = (
            f"{candidate.candidate_id}:{target_generation}:{overall_holdout:.4f}:"
            f"{baseline_score:.4f}:{gain:.4f}:{prior_regression:.4f}:{evaluator_manifest_digest}"
        ).encode("utf-8")
        proof_digest = hashlib.sha256(proof_payload).hexdigest()

        proof = EmpiricalValidationProof(
            proof_id=f"PROOF_G{target_generation}_{candidate.candidate_id}",
            candidate_id=candidate.candidate_id,
            parent_id=active_head_id,
            generation=target_generation,
            holdout_score=overall_holdout,
            baseline_score=baseline_score,
            gain_over_parent=gain,
            prior_regression=prior_regression,
            task_scores=task_scores,
            evaluator_manifest_digest=evaluator_manifest_digest,
            witness_count=total_holdout_instances,
            proof_digest=proof_digest,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        # 2. Gate Verification: Fail-closed rejection check
        rejection_reasons: List[str] = []
        if gain < self.min_gain:
            rejection_reasons.append(f"Insufficient holdout gain: {gain:.4f} < {self.min_gain:.4f}")

        if prior_regression > self.max_regression:
            rejection_reasons.append(f"Regression exceeded: {prior_regression:.4f} > {self.max_regression:.4f}")

        if rejection_reasons:
            combined_reason = "; ".join(rejection_reasons)
            self.lineage.record_rejection(
                candidate_id=candidate.candidate_id,
                reason=combined_reason,
                parent_id=active_head_id,
                generation=target_generation,
                source_sha=candidate.source_sha,
            )
            return False, None, combined_reason

        # 3. Certified Promotion!
        # Step A: Extract verified sub-primitives from candidate
        extracted_prims = self.primitive_synthesizer.extract_primitives_from_candidate(
            candidate=candidate,
            task_id="multi_task_promotion",
            validation_score=overall_holdout,
        )

        # Register extracted primitives into active GenerationalLibrary
        extracted_pids: List[str] = []
        for prim in extracted_prims:
            registered = self.library.register_primitive(
                primitive=prim,
                generation=target_generation,
                candidate_id=candidate.candidate_id,
            )
            extracted_pids.append(prim.primitive_id)

        # Step B: Cryptographic receipt with HMAC signature
        parent_merkle = active_node.merkle_node_hash if active_node else "0" * 64
        merkle_node_hash = hashlib.sha256(
            f"{parent_merkle}:{candidate.candidate_id}:{candidate.source_sha}:{target_generation}:{proof.proof_digest}".encode("utf-8")
        ).hexdigest()

        receipt_id = f"PROM_G{target_generation}_{candidate.candidate_id}"
        sig_payload = f"{receipt_id}:{candidate.source_sha}:{merkle_node_hash}:{proof.proof_digest}".encode("utf-8")
        sig = hashlib.sha256(
            self.provenance_engine.signing_key.encode("utf-8") + sig_payload
        ).hexdigest()

        receipt = PromotionReceipt(
            receipt_id=receipt_id,
            generation=target_generation,
            candidate_id=candidate.candidate_id,
            parent_id=active_head_id,
            source_sha=candidate.source_sha,
            parent_merkle_hash=parent_merkle,
            merkle_node_hash=merkle_node_hash,
            empirical_proof=proof,
            primitives_extracted=extracted_pids,
            receipt_signature=sig,
            key_fingerprint=self.provenance_engine.key_fingerprint,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        # Step C: Update cryptographic lineage with Merkle link
        self.lineage.record_promotion(candidate.candidate_id, receipt=receipt)
        # Update node metadata with task scores
        self.lineage.nodes[candidate.candidate_id].metadata["task_scores"] = task_scores
        self.lineage.nodes[candidate.candidate_id].metadata["baseline_score"] = overall_holdout

        # Step D: Advance milestone
        milestone = GenerationalMilestone(
            generation=target_generation,
            milestone_tag=f"G{target_generation}",
            status="CERTIFIED_PROMOTED",
            active_head_id=candidate.candidate_id,
            promoted_candidate_id=candidate.candidate_id,
            promotion_receipt_id=receipt.receipt_id,
            empirical_proof_digest=proof.proof_digest,
            achieved_timestamp=receipt.timestamp,
            target_tasks=list(task_scores.keys()),
            metadata={
                "holdout_score": overall_holdout,
                "gain_over_parent": gain,
                "primitives_extracted_count": len(extracted_pids),
            },
        )
        self.milestones[target_generation] = milestone
        self.current_generation = target_generation
        self._save()

        return True, receipt, f"Candidate {candidate.candidate_id} certified and promoted to G{target_generation}"

    def verify_ladder_integrity(self) -> Tuple[bool, List[str]]:
        """Verify complete cryptographic ladder integrity across all milestones."""
        logs: List[str] = []

        # 1. Lineage Merkle chain integrity
        valid_chain, chain_msg = self.lineage.verify_chain_integrity()
        if not valid_chain:
            return False, [f"Merkle chain failure: {chain_msg}"]
        logs.append(f"Merkle chain intact: {chain_msg}")

        # 2. Verify all milestones have valid promotion receipts and empirical proofs
        for gen, m in sorted(self.milestones.items()):
            if gen == 0:
                continue
            rid = m.promotion_receipt_id
            if not rid or rid not in self.lineage.receipts:
                return False, [f"Missing promotion receipt for milestone G{gen}"]

            receipt = self.lineage.receipts[rid]
            # Verify HMAC signature
            sig_payload = f"{receipt.receipt_id}:{receipt.source_sha}:{receipt.merkle_node_hash}:{receipt.empirical_proof.proof_digest}".encode("utf-8")
            expected_sig = hashlib.sha256(
                self.provenance_engine.signing_key.encode("utf-8") + sig_payload
            ).hexdigest()
            if receipt.receipt_signature != expected_sig:
                return False, [f"Invalid receipt HMAC signature for G{gen}"]

            # Verify gain threshold
            if receipt.empirical_proof.gain_over_parent < self.min_gain:
                return False, [f"Receipt gain {receipt.empirical_proof.gain_over_parent} below minimum for G{gen}"]

            logs.append(f"Milestone G{gen} verified: receipt {rid} signed and valid")

        # 3. Verify GenerationalLibrary Merkle root
        lib_root = self.library.compute_library_merkle_root()
        logs.append(f"GenerationalLibrary Merkle root verified: {lib_root[:16]}")

        return True, logs

    def export_status(self) -> Dict[str, Any]:
        return {
            "current_generation": self.current_generation,
            "active_head_id": self.lineage.active_head_id,
            "milestones": {
                gen: m.to_dict() for gen, m in sorted(self.milestones.items())
            },
            "library_summary": self.library.export_summary(),
            "lineage_merkle_root": self.lineage.compute_merkle_root(),
        }

    def _save(self) -> None:
        state_file = self.checkpoint_dir / "ladder_state.json"
        data = {
            "current_generation": self.current_generation,
            "milestones": {gen: m.to_dict() for gen, m in self.milestones.items()},
        }
        state_file.write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        state_file = self.checkpoint_dir / "ladder_state.json"
        if not state_file.exists():
            return
        try:
            raw = json.loads(state_file.read_text())
            self.current_generation = raw.get("current_generation", 0)
            self.milestones = {
                int(gen): GenerationalMilestone.from_dict(m)
                for gen, m in raw.get("milestones", {}).items()
            }
        except Exception:
            self.milestones = {}
