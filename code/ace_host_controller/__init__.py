"""ACE Independent Host Controller & Evaluation Package.

Provides an authoritative, external supervisor layer over ACE autonomous research:
- LineageGraph and CandidateNode tracking (parent SHA, source SHA, generation)
- ExecutionBudget and CapabilityPermit governance
- HostSandboxGate enforcing fail-closed BLOCKED_ENVIRONMENT
- SealedHoldoutEvaluator with cryptographic manifest
- ExposureLedger tracking benchmark non-contamination
- Acceptance/Rejection gating with automated rollback
"""
from __future__ import annotations

from .budget_permits import (
    BudgetExceededError,
    CapabilityPermit,
    ExecutionBudget,
    PermitDeniedError,
)
from .controller import (
    AcceptanceDecision,
    HostController,
    RollbackRecord,
)
from .exposure_ledger import (
    ContaminationError,
    ExposureLedger,
    ExposureRecord,
)
from .lineage import (
    CandidateNode,
    LineageCycleError,
    LineageGraph,
    LineageNotFoundError,
)
from .sandbox_gate import (
    GateResult,
    HostSandboxGate,
    SandboxSecurityError,
)
from .sealed_evaluator import (
    EvaluationReceipt,
    EvaluatorManifest,
    SealedHoldoutEvaluator,
)

__all__ = [
    "AcceptanceDecision",
    "BudgetExceededError",
    "CandidateNode",
    "CapabilityPermit",
    "ContaminationError",
    "EvaluationReceipt",
    "EvaluatorManifest",
    "ExecutionBudget",
    "ExposureLedger",
    "ExposureRecord",
    "GateResult",
    "HostController",
    "HostSandboxGate",
    "LineageCycleError",
    "LineageGraph",
    "LineageNotFoundError",
    "PermitDeniedError",
    "RollbackRecord",
    "SandboxSecurityError",
    "SealedHoldoutEvaluator",
]
