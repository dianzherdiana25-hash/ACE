"""ACE Abstract Interpretation & Invariant Synthesis Module.

Features Interval Lattice abstract domain, Galois connection transfer operators,
widening/narrowing inductive fixpoint engines, and semantic drift bound verifiers.
"""
from __future__ import annotations

from .invariants import (
    Interval,
    AbstractState,
    AbstractInterpreter,
    InvariantSynthesizer,
    INF,
    NEG_INF,
)
from .disjunctive_domain import (
    DisjunctiveInterval,
    TracePartitionState,
    DisjunctiveInterpreter,
)

__all__ = [
    "Interval",
    "AbstractState",
    "AbstractInterpreter",
    "InvariantSynthesizer",
    "DisjunctiveInterval",
    "TracePartitionState",
    "DisjunctiveInterpreter",
    "INF",
    "NEG_INF",
]
