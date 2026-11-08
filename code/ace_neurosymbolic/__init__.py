"""ACE Neurosymbolic Engine.

Provides:
- Neural-Guided A* Heuristic Program Search with Statistical Feature Estimators
- Differentiable Neurosymbolic Program Sketching via Gumbel-Softmax Relaxation
"""
from __future__ import annotations

from ace_neurosymbolic.neural_guided_search import (
    Grammar,
    Hole,
    NeuralGuidedAStarSearch,
    PartialAST,
    ProductionRule,
    SearchResult,
    StatisticalFeatureEstimator,
    ExhaustiveProgramSearch,
    benchmark_speedup,
)
from ace_neurosymbolic.sketch_synthesizer import (
    DifferentiableSketchSynthesizer,
    GumbelSoftmax,
    LogicalConjunctionSketch,
    PrimitiveChoice,
    ProgramSketch,
    RelationalComparisonSketch,
    SketchSynthesisResult,
    Slot,
    SmoothInterpreter,
    compare_with_unrelaxed_enumeration,
)

__all__ = [
    # Neural Guided Search
    "Hole",
    "PartialAST",
    "ProductionRule",
    "Grammar",
    "StatisticalFeatureEstimator",
    "NeuralGuidedAStarSearch",
    "ExhaustiveProgramSearch",
    "SearchResult",
    "benchmark_speedup",
    # Differentiable Sketching
    "Slot",
    "PrimitiveChoice",
    "GumbelSoftmax",
    "SmoothInterpreter",
    "ProgramSketch",
    "RelationalComparisonSketch",
    "LogicalConjunctionSketch",
    "DifferentiableSketchSynthesizer",
    "SketchSynthesisResult",
    "compare_with_unrelaxed_enumeration",
]
