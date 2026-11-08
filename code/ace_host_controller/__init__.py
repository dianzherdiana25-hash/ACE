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
from .resilient_watchdog import (
    CycleStallTimeoutError,
    DiagnosticDump,
    RecoveryFailedError,
    ResilientWatchdog,
    ResourceStats,
    StateIntegrityError,
    TelemetryBeacon,
    WatchdogConfig,
    WatchdogError,
    compute_merkle_root,
    recover_research_state,
    verify_merkle_tree,
    verify_state_merkle_chain,
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
    "CycleStallTimeoutError",
    "DiagnosticDump",
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
    "RecoveryFailedError",
    "ResilientWatchdog",
    "ResourceStats",
    "RollbackRecord",
    "SandboxSecurityError",
    "SealedHoldoutEvaluator",
    "SealingStatus",
    "StateIntegrityError",
    "SubprocessSealedEvaluator",
    "TelemetryBeacon",
    "WatchdogConfig",
    "WatchdogError",
    "compute_merkle_root",
    "detect_os_sealing",
    "recover_research_state",
    "verify_merkle_tree",
    "verify_state_merkle_chain",
]



