"""Data models for ACE Autonomous Self-Development Loop V0.1."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Tuple


class AuthorType(str, Enum):
    ACE_AUTONOMOUS_V01 = "ACE_AUTONOMOUS_V01"
    GEMINI = "GEMINI"
    CODEX = "CODEX"
    HUMAN = "HUMAN"


class CandidateDecision(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"


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


@dataclass(frozen=True)
class CodeCandidate:
    """Type-checked, AST-validated algorithm / code modification candidate."""
    candidate_id: str
    parent_id: str
    author_type: AuthorType
    source_code: str
    source_sha: str
    gene_dict: Dict[str, int]
    diff_patch: str
    creation_timestamp: str


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
    timestamp: str


@dataclass
class CycleCheckpoint:
    """Durable state checkpoint for crash-safe resumption."""
    cycle_id: int
    phase: str  # "INITIALIZED", "DIAGNOSED", "HYPOTHESIS_SELECTED", "CANDIDATE_GENERATED", "EVALUATED", "DECIDED", "REPORTED"
    active_head_id: str
    diagnosis: Optional[Dict[str, Any]] = None
    hypothesis: Optional[Dict[str, Any]] = None
    candidate: Optional[Dict[str, Any]] = None
    evaluation: Optional[Dict[str, Any]] = None
    decision: Optional[str] = None
    cost_usd: float = 0.0
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "phase": self.phase,
            "active_head_id": self.active_head_id,
            "diagnosis": self.diagnosis,
            "hypothesis": self.hypothesis,
            "candidate": self.candidate,
            "evaluation": self.evaluation,
            "decision": self.decision,
            "cost_usd": self.cost_usd,
            "updated_at": self.updated_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CycleCheckpoint:
        return cls(
            cycle_id=data["cycle_id"],
            phase=data["phase"],
            active_head_id=data["active_head_id"],
            diagnosis=data.get("diagnosis"),
            hypothesis=data.get("hypothesis"),
            candidate=data.get("candidate"),
            evaluation=data.get("evaluation"),
            decision=data.get("decision"),
            cost_usd=data.get("cost_usd", 0.0),
            updated_at=data.get("updated_at", ""),
        )
