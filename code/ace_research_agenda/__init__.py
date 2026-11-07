"""ACE Fase 9 — Autonomous Research Agenda & Closed-Loop Scientific Operating Mode."""
from .coordinator import (
    AGENDA_CYCLE_STAGES,
    AutonomousResearchCoordinator,
    run_autonomous_research_campaign,
)
from .models import (
    CapabilityGap,
    ExperimentVerdict,
    ResearchArchive,
    ResearchCampaignBudget,
    ResearchHypothesis,
)

__all__ = [
    "AGENDA_CYCLE_STAGES",
    "AutonomousResearchCoordinator",
    "CapabilityGap",
    "ExperimentVerdict",
    "ResearchArchive",
    "ResearchCampaignBudget",
    "ResearchHypothesis",
    "run_autonomous_research_campaign",
]
