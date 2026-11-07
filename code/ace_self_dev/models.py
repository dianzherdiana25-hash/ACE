"""Data models for ACE Autonomous Self-Development Loop V0.2.

Expands V0.1 models with:
- AuthorType.ACE_AUTONOMOUS_V02
- ProvenanceProof (verifiable execution context & HMAC authentication)
- NextAgendaPriority (autonomous agenda progression)
- PersistentResearchState (durable research memory, failure catalog, rolling digest)
- Prior cycle chaining and Merkle state digest links
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Tuple


class AuthorType(str, Enum):
    ACE_AUTONOMOUS_V01 = "ACE_AUTONOMOUS_V01"
    ACE_AUTONOMOUS_V02 = "ACE_AUTONOMOUS_V02"
    GEMINI = "GEMINI"
    CODEX = "CODEX"
    HUMAN = "HUMAN"


class CandidateDecision(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    STAGNATED = "STAGNATED"
    ABSTAINED = "ABSTAINED"


@dataclass(frozen=True)
class ProvenanceProof:
    """Verifiable cryptographic proof of candidate generation and execution context."""
    author_type: AuthorType
    execution_pid: int
    platform: str
    python_version: str
    git_commit_sha: str
    source_sha: str
    key_fingerprint: str
    hmac_signature: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "author_type": self.author_type.value,
            "execution_pid": self.execution_pid,
            "platform": self.platform,
            "python_version": self.python_version,
            "git_commit_sha": self.git_commit_sha,
            "source_sha": self.source_sha,
            "key_fingerprint": self.key_fingerprint,
            "hmac_signature": self.hmac_signature,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProvenanceProof:
        return cls(
            author_type=AuthorType(data["author_type"]),
            execution_pid=data["execution_pid"],
            platform=data["platform"],
            python_version=data["python_version"],
            git_commit_sha=data["git_commit_sha"],
            source_sha=data["source_sha"],
            key_fingerprint=data["key_fingerprint"],
            hmac_signature=data["hmac_signature"],
            timestamp=data["timestamp"],
        )


@dataclass(frozen=True)
class SystemDiagnosis:
    """Diagnostic assessment of system capabilities and structural weaknesses."""
    timestamp: str
    baseline_head_id: str
    baseline_score: float
    diagnosed_weakness_task: str
    diagnosed_weakness_family: str
    observed_failure_rate: float
    error_cue: str
    diagnostic_details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResearchHypothesis:
    """Concrete, falsifiable hypothesis targeting a diagnosed weakness."""
    hypothesis_id: str
    statement: str
    target_task_id: str
    min_required_gain: float = 0.1500
    max_regression_tolerance: float = 0.0200
    max_search_budget_cost_usd: float = 0.0
    preregistration_hash: str = ""
    strategy: str = "LINEAR_MUTATION"


@dataclass(frozen=True)
class CodeCandidate:
    """Type-checked, AST-validated algorithm / code modification candidate."""
    candidate_id: str
    parent_id: str
    author_type: AuthorType
    source_code: str
    source_sha: str
    gene_dict: Dict[str, Any]
    diff_patch: str = ""
    creation_timestamp: str = ""
    provenance_proof: Optional[ProvenanceProof] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "parent_id": self.parent_id,
            "author_type": self.author_type.value,
            "source_code": self.source_code,
            "source_sha": self.source_sha,
            "gene_dict": self.gene_dict,
            "diff_patch": self.diff_patch,
            "creation_timestamp": self.creation_timestamp,
            "provenance_proof": self.provenance_proof.to_dict() if self.provenance_proof else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CodeCandidate:
        prov = ProvenanceProof.from_dict(data["provenance_proof"]) if data.get("provenance_proof") else None
        return cls(
            candidate_id=data["candidate_id"],
            parent_id=data["parent_id"],
            author_type=AuthorType(data["author_type"]),
            source_code=data["source_code"],
            source_sha=data["source_sha"],
            gene_dict=data["gene_dict"],
            diff_patch=data.get("diff_patch", ""),
            creation_timestamp=data.get("creation_timestamp", ""),
            provenance_proof=prov,
        )


@dataclass(frozen=True)
class EvaluationReceipt:
    """Cryptographically verifiable receipt of independent evaluation."""
    receipt_id: str
    evaluator_manifest_digest: str
    candidate_id: str
    parent_id: str
    train_score: float
    validation_score: float
    holdout_score: float
    gain_over_parent: float
    prior_regression: float
    decision: CandidateDecision
    decision_reason: str
    evaluator_calls: int
    cpu_seconds: float
    memory_mb: float
    cost_usd: float
    receipt_signature: str
    key_fingerprint: str
    timestamp: str
    prior_cycle_id: Optional[int] = None
    state_digest_before: str = ""
    state_digest_after: str = ""
    provenance_proof: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class EmpiricalValidationProof:
    """Empirical validation proof establishing holdout gain, non-regression, and manifest validity."""
    proof_id: str
    candidate_id: str
    parent_id: str
    generation: int
    holdout_score: float
    baseline_score: float
    gain_over_parent: float
    prior_regression: float
    task_scores: Dict[str, float]
    evaluator_manifest_digest: str
    witness_count: int
    proof_digest: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "candidate_id": self.candidate_id,
            "parent_id": self.parent_id,
            "generation": self.generation,
            "holdout_score": self.holdout_score,
            "baseline_score": self.baseline_score,
            "gain_over_parent": self.gain_over_parent,
            "prior_regression": self.prior_regression,
            "task_scores": self.task_scores,
            "evaluator_manifest_digest": self.evaluator_manifest_digest,
            "witness_count": self.witness_count,
            "proof_digest": self.proof_digest,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EmpiricalValidationProof:
        return cls(
            proof_id=data["proof_id"],
            candidate_id=data["candidate_id"],
            parent_id=data["parent_id"],
            generation=data["generation"],
            holdout_score=float(data["holdout_score"]),
            baseline_score=float(data["baseline_score"]),
            gain_over_parent=float(data["gain_over_parent"]),
            prior_regression=float(data.get("prior_regression", 0.0)),
            task_scores=data.get("task_scores", {}),
            evaluator_manifest_digest=data.get("evaluator_manifest_digest", ""),
            witness_count=int(data.get("witness_count", 0)),
            proof_digest=data.get("proof_digest", ""),
            timestamp=data.get("timestamp", ""),
        )


@dataclass(frozen=True)
class PromotionReceipt:
    """Cryptographic receipt verifying certified generational promotion (G_k -> G_{k+1})."""
    receipt_id: str
    generation: int
    candidate_id: str
    parent_id: str
    source_sha: str
    parent_merkle_hash: str
    merkle_node_hash: str
    empirical_proof: EmpiricalValidationProof
    primitives_extracted: List[str]
    receipt_signature: str
    key_fingerprint: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "generation": self.generation,
            "candidate_id": self.candidate_id,
            "parent_id": self.parent_id,
            "source_sha": self.source_sha,
            "parent_merkle_hash": self.parent_merkle_hash,
            "merkle_node_hash": self.merkle_node_hash,
            "empirical_proof": self.empirical_proof.to_dict(),
            "primitives_extracted": self.primitives_extracted,
            "receipt_signature": self.receipt_signature,
            "key_fingerprint": self.key_fingerprint,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PromotionReceipt:
        return cls(
            receipt_id=data["receipt_id"],
            generation=data["generation"],
            candidate_id=data["candidate_id"],
            parent_id=data["parent_id"],
            source_sha=data["source_sha"],
            parent_merkle_hash=data["parent_merkle_hash"],
            merkle_node_hash=data["merkle_node_hash"],
            empirical_proof=EmpiricalValidationProof.from_dict(data["empirical_proof"]),
            primitives_extracted=data.get("primitives_extracted", []),
            receipt_signature=data["receipt_signature"],
            key_fingerprint=data["key_fingerprint"],
            timestamp=data["timestamp"],
        )


@dataclass(frozen=True)
class NextAgendaPriority:
    """Autonomous selection of the next research goal and hypothesis strategy."""
    priority_task_id: str
    priority_family: str
    strategy: str  # e.g., "EXPLORE_MUTATION_ORDINAL", "TARGET_NEXT_WEAKEST_TASK"
    suggested_ordinal: int
    rationalization: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "priority_task_id": self.priority_task_id,
            "priority_family": self.priority_family,
            "strategy": self.strategy,
            "suggested_ordinal": self.suggested_ordinal,
            "rationalization": self.rationalization,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> NextAgendaPriority:
        return cls(
            priority_task_id=data["priority_task_id"],
            priority_family=data["priority_family"],
            strategy=data["strategy"],
            suggested_ordinal=data.get("suggested_ordinal", 1),
            rationalization=data.get("rationalization", ""),
            timestamp=data.get("timestamp", ""),
        )


@dataclass
class CycleCheckpoint:
    """Durable state checkpoint for crash-safe resumption."""
    cycle_id: int
    phase: str  # "INITIALIZED", "DIAGNOSED", "HYPOTHESIS_SELECTED", "CANDIDATE_GENERATED", "EVALUATED", "DECIDED", "REPORTED"
    active_head_id: str
    prior_cycle_id: Optional[int] = None
    state_digest_before: str = ""
    state_digest_after: str = ""
    diagnosis: Optional[Dict[str, Any]] = None
    hypothesis: Optional[Dict[str, Any]] = None
    candidate: Optional[Dict[str, Any]] = None
    evaluation: Optional[Dict[str, Any]] = None
    decision: Optional[str] = None
    next_goal: Optional[Dict[str, Any]] = None
    cost_usd: float = 0.0
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "phase": self.phase,
            "active_head_id": self.active_head_id,
            "prior_cycle_id": self.prior_cycle_id,
            "state_digest_before": self.state_digest_before,
            "state_digest_after": self.state_digest_after,
            "diagnosis": self.diagnosis,
            "hypothesis": self.hypothesis,
            "candidate": self.candidate,
            "evaluation": self.evaluation,
            "decision": self.decision,
            "next_goal": self.next_goal,
            "cost_usd": self.cost_usd,
            "updated_at": self.updated_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CycleCheckpoint:
        return cls(
            cycle_id=data["cycle_id"],
            phase=data["phase"],
            active_head_id=data["active_head_id"],
            prior_cycle_id=data.get("prior_cycle_id"),
            state_digest_before=data.get("state_digest_before", ""),
            state_digest_after=data.get("state_digest_after", ""),
            diagnosis=data.get("diagnosis"),
            hypothesis=data.get("hypothesis"),
            candidate=data.get("candidate"),
            evaluation=data.get("evaluation"),
            decision=data.get("decision"),
            next_goal=data.get("next_goal"),
            cost_usd=data.get("cost_usd", 0.0),
            updated_at=data.get("updated_at", ""),
        )


@dataclass
class PersistentResearchState:
    """Persistent, cross-process research memory for autonomous continuity."""
    schema_version: str = "2.0"
    active_generation_id: str = "G0_root_seed"
    cycle_count: int = 0
    completed_cycles: List[Dict[str, Any]] = field(default_factory=list)
    failure_catalog: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    hypotheses_history: List[Dict[str, Any]] = field(default_factory=list)
    next_agenda_priority: Optional[Dict[str, Any]] = None
    concurrency_lock: Dict[str, Any] = field(default_factory=lambda: {
        "is_locked": False,
        "locked_by": "",
        "locked_at": "",
        "expires_at": "",
        "lock_token": "",
    })
    immutable_baseline: Dict[str, Any] = field(default_factory=dict)
    state_digest: str = ""
    fail_closed_recovery: Dict[str, Any] = field(default_factory=lambda: {
        "last_known_good_cycle": 0,
        "last_known_good_digest": "",
        "recovery_count": 0,
    })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "active_generation_id": self.active_generation_id,
            "cycle_count": self.cycle_count,
            "completed_cycles": self.completed_cycles,
            "failure_catalog": self.failure_catalog,
            "hypotheses_history": self.hypotheses_history,
            "next_agenda_priority": self.next_agenda_priority,
            "concurrency_lock": self.concurrency_lock,
            "immutable_baseline": self.immutable_baseline,
            "state_digest": self.state_digest,
            "fail_closed_recovery": self.fail_closed_recovery,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PersistentResearchState:
        return cls(
            schema_version=data.get("schema_version", "2.0"),
            active_generation_id=data.get("active_generation_id", "G0_root_seed"),
            cycle_count=data.get("cycle_count", 0),
            completed_cycles=data.get("completed_cycles", []),
            failure_catalog=data.get("failure_catalog", {}),
            hypotheses_history=data.get("hypotheses_history", []),
            next_agenda_priority=data.get("next_agenda_priority"),
            concurrency_lock=data.get("concurrency_lock", {
                "is_locked": False,
                "locked_by": "",
                "locked_at": "",
                "expires_at": "",
                "lock_token": "",
            }),
            immutable_baseline=data.get("immutable_baseline", {}),
            state_digest=data.get("state_digest", ""),
            fail_closed_recovery=data.get("fail_closed_recovery", {
                "last_known_good_cycle": 0,
                "last_known_good_digest": "",
                "recovery_count": 0,
            }),
        )
