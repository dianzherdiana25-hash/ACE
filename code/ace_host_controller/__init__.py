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
from .boundary import (
    BoundarySecurityViolation,
    ImmutablePromotionRules,
    SealingStatus,
    detect_os_sealing,
)
from .subprocess_evaluator import SubprocessSealedEvaluator
from .evaluator_v2 import (
    ChainedExposureRecord,
    ContaminationDetectedError,
    DualOracleHarness,
    LedgerTamperError,
    MerkleExposureLedger,
    OracleBoundaryViolation,
    PreRegistrationCommitment,
)

__all__ = [
    "AcceptanceDecision",
    "BoundarySecurityViolation",
    "BudgetExceededError",
    "CandidateNode",
    "CapabilityPermit",
    "ChainedExposureRecord",
    "ContaminationDetectedError",
    "ContaminationError",
    "DualOracleHarness",
    "EvaluationReceipt",
    "EvaluatorManifest",
    "ExecutionBudget",
    "ExposureLedger",
    "ExposureRecord",
    "GateResult",
    "HostController",
    "HostSandboxGate",
    "ImmutablePromotionRules",
    "LedgerTamperError",
    "LineageCycleError",
    "LineageGraph",
    "LineageNotFoundError",
    "MerkleExposureLedger",
    "OracleBoundaryViolation",
    "PermitDeniedError",
    "PreRegistrationCommitment",
    "RollbackRecord",
    "SandboxSecurityError",
    "SealedHoldoutEvaluator",
    "SealingStatus",
    "SubprocessSealedEvaluator",
    "detect_os_sealing",
]
