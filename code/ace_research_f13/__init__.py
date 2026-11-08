"""ACE F13 Causal Memory Validation Package.

Provides curriculum task suite, structured causal memory, active inquiry agent,
and benchmark runner with Cohen's d effect size evaluation across 6 matched arms and 5 seeds.
"""
from __future__ import annotations

from .agent import F13CausalAgent, HypothesisCandidate
from .benchmark import ARMS, PRE_REGISTERED_SEEDS, run_f13_curriculum_benchmark, save_evidence
from .causal_memory import CausalMemoryV2, DistilledAbstraction
from .tasks import F13Task, create_distractor_tasks, create_f13_curriculum

__all__ = [
    "ARMS",
    "CausalMemoryV2",
    "DistilledAbstraction",
    "F13CausalAgent",
    "F13Task",
    "HypothesisCandidate",
    "PRE_REGISTERED_SEEDS",
    "create_distractor_tasks",
    "create_f13_curriculum",
    "run_f13_curriculum_benchmark",
    "save_evidence",
]
