"""ACE Neurosymbolic Engine: Neural-Guided Program Search.

Provides:
- Statistical Feature Estimator over I/O specifications
- Partial AST representations with typed Hole expansion
- Neural-Guided A* Heuristic Program Search
- Comparative Exhaustive Search Baseline for Soundness and Speedup Verification
"""
from __future__ import annotations

from ace_neurosymbolic.neural_guided_search import (
    Hole,
    PartialAST,
    ProductionRule,
    Grammar,
    StatisticalFeatureEstimator,
    NeuralGuidedAStarSearch,
    ExhaustiveProgramSearch,
    SearchResult,
    benchmark_speedup,
)

__all__ = [
    "Hole",
    "PartialAST",
    "ProductionRule",
    "Grammar",
    "StatisticalFeatureEstimator",
    "NeuralGuidedAStarSearch",
    "ExhaustiveProgramSearch",
    "SearchResult",
    "benchmark_speedup",
]
