"""ACE Autonomous Continuity & Self-Development Package V0.2."""
from .models import (
    AuthorType,
    CandidateDecision,
    CodeCandidate,
    CycleCheckpoint,
    EmpiricalValidationProof,
    EvaluationReceipt,
    NextAgendaPriority,
    PersistentResearchState,
    PromotionReceipt,
    ProvenanceProof,
    ResearchHypothesis,
    SystemDiagnosis,
)
from .confirmation_suite import ConfirmationTask, create_confirmation_suite
from .coordinator import SelfDevelopmentCoordinator
from .agenda_engine import AgendaEngine
from .provenance_engine import ProvenanceEngine
from .state_manager import StateManager
from .stagnation_detector import (
    BitvectorRegistry,
    StagnationCheckResult,
    StagnationDetector,
    StagnationType,
)
from .strategy_repair import (
    FailurePatternType,
    RepresentationFamily,
    StrategyRepairDecision,
    StrategyRepairEngine,
)
from .failure_constraint_engine import FailureConstraint, FailureConstraintEngine
from .quality_diversity import EliteEntry, QualityDiversityArchive
from .primitive_synthesizer import PrimitiveSynthesizer, SynthesizedPrimitive
from .metacognitive_predictor import (
    CalibrationReport,
    CandidateFeatures,
    HighRiskHeuristic,
    MetacognitiveForecast,
    MetacognitivePredictor,
    ReliabilityBin,
    compute_brier_score,
    compute_calibration_report,
    compute_expected_calibration_error,
)
from .lineage_manager import CryptographicLineageNode, LineageManager
from .generational_ladder import (
    GenerationalCandidateSynthesizer,
    GenerationalCompositeASTNode,
    GenerationalLadder,
    GenerationalLibrary,
    GenerationalMilestone,
)

__all__ = [
    "AuthorType",
    "CandidateDecision",
    "CodeCandidate",
    "CycleCheckpoint",
    "EvaluationReceipt",
    "NextAgendaPriority",
    "PersistentResearchState",
    "ProvenanceProof",
    "ResearchHypothesis",
    "SystemDiagnosis",
    "ConfirmationTask",
    "create_confirmation_suite",
    "SelfDevelopmentCoordinator",
    "AgendaEngine",
    "ProvenanceEngine",
    "StateManager",
    "BitvectorRegistry",
    "StagnationCheckResult",
    "StagnationDetector",
    "StagnationType",
    "FailurePatternType",
    "RepresentationFamily",
    "StrategyRepairDecision",
    "StrategyRepairEngine",
    "FailureConstraint",
    "FailureConstraintEngine",
    "EliteEntry",
    "QualityDiversityArchive",
    "PrimitiveSynthesizer",
    "SynthesizedPrimitive",
    "CalibrationReport",
    "CandidateFeatures",
    "HighRiskHeuristic",
    "MetacognitiveForecast",
    "MetacognitivePredictor",
    "ReliabilityBin",
    "compute_brier_score",
    "compute_calibration_report",
    "compute_expected_calibration_error",
    "EmpiricalValidationProof",
    "PromotionReceipt",
    "CryptographicLineageNode",
    "LineageManager",
    "GenerationalMilestone",
    "GenerationalLibrary",
    "GenerationalCompositeASTNode",
    "GenerationalCandidateSynthesizer",
    "GenerationalLadder",
]
