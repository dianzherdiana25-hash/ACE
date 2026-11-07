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
    diff_patch: str
    creation_timestamp: str
    provenance_proof: Optional[ProvenanceProof] = None


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
