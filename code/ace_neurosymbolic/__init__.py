"""ACE Neurosymbolic Engine.

Provides:
- Neural-Guided A* Heuristic Program Search with Statistical Feature Estimators
- Differentiable Neurosymbolic Program Sketching via Gumbel-Softmax Relaxation
- Equivariant AST Graph Representation, Weisfeiler-Lehman Kernels, and Latent Transfer
- Counterexample-Guided Abstraction Refinement (CEGAR) over Predicate Lattices
"""
from __future__ import annotations

from ace_neurosymbolic.cegar_refinement import (
    AbstractPredicateState,
    CEGARResult,
    CEGARVerifier,
    CFGEdge,
    Predicate,
    ProgramCFG,
    build_guarded_division_cfg,
    build_loop_counter_cfg,
    build_unguarded_unsafe_division_cfg,
)
from ace_neurosymbolic.graph_embedding import (
    COMMUTATIVE_OPERATORS,
    ASTGraph,
    EquivariantASTGNN,
    GraphEdge,
    GraphNode,
    LatentProgramLibrary,
    WeisfeilerLehmanASTKernel,
)
from ace_neurosymbolic.neural_guided_search import (
    ExhaustiveProgramSearch,
    Grammar,
    Hole,
    NeuralGuidedAStarSearch,
    PartialAST,
    ProductionRule,
    SearchResult,
    StatisticalFeatureEstimator,
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
    # Equivariant Graph Embeddings & Transfer
    "COMMUTATIVE_OPERATORS",
    "ASTGraph",
    "GraphNode",
    "GraphEdge",
    "WeisfeilerLehmanASTKernel",
    "EquivariantASTGNN",
    "LatentProgramLibrary",
    # CEGAR Predicate Lattice Refinement
    "Predicate",
    "AbstractPredicateState",
    "CFGEdge",
    "ProgramCFG",
    "CEGARVerifier",
    "CEGARResult",
    "build_guarded_division_cfg",
    "build_unguarded_unsafe_division_cfg",
    "build_loop_counter_cfg",
]
