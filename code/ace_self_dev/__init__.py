"""ACE Autonomous Continuity & Self-Development Package V0.2."""
from .models import (
    AuthorType,
    CandidateDecision,
    CodeCandidate,
    CycleCheckpoint,
    EvaluationReceipt,
    NextAgendaPriority,
    PersistentResearchState,
    ProvenanceProof,
    ResearchHypothesis,
    SystemDiagnosis,
)
from .confirmation_suite import ConfirmationTask, create_confirmation_suite
from .coordinator import SelfDevelopmentCoordinator
from .agenda_engine import AgendaEngine
from .provenance_engine import ProvenanceEngine
from .state_manager import StateManager

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
]
