"""ACE Evolutionary Island Program Search Module inspired by DeepMind's FunSearch and STGP.

Maintains multi-island population diversity, strongly-typed AST genetic operators,
and multi-objective Pareto ranking (accuracy, parsimony, novelty).
"""
from __future__ import annotations

from .island_search import EvolutionaryIslandSearch, ProgramCandidate, TypedASTNode

__all__ = ["EvolutionaryIslandSearch", "ProgramCandidate", "TypedASTNode"]
