"""ACE F12 Causal Autonomous Research Package.

Implements causal gap identification, active information-gain experiment selection,
and generational capability growth under Host Controller governance.
"""
from __future__ import annotations

RELEASE_GATE = "BLOCK_RELEASE"
SCIENTIFIC_STATUS = "NOT_ASSESSED"
OAIE_ESTABLISHED = False
SCHEMA_VERSION = "ace.f12_causal_research.v1"

from .causal_agent import (
    ActiveInformationGainSynthesizer,
    CausalGapAnalyzer,
    CausalMemory,
    CausalResearchAgent,
)
from .tasks import (
    DyckBalanceTask,
    RelationalSplitTask,
    StridedModTask,
    create_f12_task_suite,
)

__all__ = [
    "ActiveInformationGainSynthesizer",
    "CausalGapAnalyzer",
    "CausalMemory",
    "CausalResearchAgent",
    "DyckBalanceTask",
    "OAIE_ESTABLISHED",
    "RELEASE_GATE",
    "RelationalSplitTask",
    "SCHEMA_VERSION",
    "SCIENTIFIC_STATUS",
    "StridedModTask",
    "create_f12_task_suite",
]
