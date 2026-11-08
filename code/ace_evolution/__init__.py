"""ACE Evolutionary Island Program Search Module inspired by DeepMind's FunSearch and STGP.

Maintains multi-island population diversity, strongly-typed AST genetic operators,
and multi-objective Pareto ranking (accuracy, parsimony, novelty).
"""
from __future__ import annotations

from .island_search import EvolutionaryIslandSearch, ProgramCandidate, TypedASTNode
from .pareto_dsl_optimizer import (
    CurriculumStage,
    DSLGrammarWeights,
    GrammarCandidate,
    HierarchicalSubGrammar,
    MacroPrimitive,
    Objectives,
    OptimizationCurriculum,
    ParetoDSLOptimizer,
    ParetoOptimizationResult,
    ProgramParetoCandidate,
    SelfRefiningProgramSynthesizer,
    SelfRefiningResult,
    WeightedASTGenerator,
    calculate_crowding_distance,
    compute_hypervolume_2d,
    crowded_comparison,
    fast_non_dominated_sort,
    tournament_selection,
)

__all__ = [
    "EvolutionaryIslandSearch",
    "ProgramCandidate",
    "TypedASTNode",
    "Objectives",
    "DSLGrammarWeights",
    "MacroPrimitive",
    "HierarchicalSubGrammar",
    "WeightedASTGenerator",
    "GrammarCandidate",
    "ProgramParetoCandidate",
    "SelfRefiningProgramSynthesizer",
    "SelfRefiningResult",
    "ParetoDSLOptimizer",
    "ParetoOptimizationResult",
    "CurriculumStage",
    "OptimizationCurriculum",
    "fast_non_dominated_sort",
    "calculate_crowding_distance",
    "crowded_comparison",
    "tournament_selection",
    "compute_hypervolume_2d",
]
