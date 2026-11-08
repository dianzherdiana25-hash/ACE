"""ACE Equality Saturation & E-Graphs (Optimal AST Rewriting) Package.

Implements:
- ENode: Strongly-typed canonical AST equivalence node.
- EClass: Equivalence class partition maintaining upward parent notifications.
- UnionFind: Disjoint set union-find with path compression.
- EGraph: Egg-style e-graph supporting delayed congruence closure.
- Pattern & RewriteRule: Pattern matching and non-destructive rewriting rules.
- EqualitySaturation: Saturation engine exploring exponential rewrites without cyclic blowup.
- Extractor & CostFunction: Optimal concrete TypedASTNode term extraction.
"""
from ace_egraph.equality_saturation import (
    ASTDepthCost,
    ASTSizeCost,
    CostFunction,
    EClass,
    EGraph,
    ENode,
    EqualitySaturation,
    Extractor,
    Pattern,
    RewriteRule,
    SaturationReport,
    UnionFind,
    build_ace_dsl_rewrites,
)

__all__ = [
    "ASTDepthCost",
    "ASTSizeCost",
    "CostFunction",
    "EClass",
    "EGraph",
    "ENode",
    "EqualitySaturation",
    "Extractor",
    "Pattern",
    "RewriteRule",
    "SaturationReport",
    "UnionFind",
    "build_ace_dsl_rewrites",
]
