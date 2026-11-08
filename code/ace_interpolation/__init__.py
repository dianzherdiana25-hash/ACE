"""ACE Craig Interpolation Engine & Inductive Invariant Synthesizer.

Provenance: ADVISOR_AGENT

Provides:
- Propositional Craig Interpolation via McMillan's resolution refutation proof algorithm.
- Linear Real/Integer Arithmetic Craig Interpolation via Farkas' Lemma duality.
- Inductive Loop Invariant Synthesis from counterexample-guided symbolic trace interpolation.
- Formal verification of Craig conditions:
    1. A implies I
    2. I and B == False (mutually inconsistent)
    3. Symbol(I) subseteq (Symbol(A) intersect Symbol(B))
"""
from __future__ import annotations

from ace_interpolation.craig_interpolator import (
    # Propositional Logic & McMillan
    PropLiteral,
    PropClause,
    PropCNF,
    BoolExpr,
    BoolConst,
    BoolVar,
    BoolNot,
    BoolAnd,
    BoolOr,
    ResolutionNode,
    McMillanPropositionalInterpolator,
    # Linear Arithmetic & Farkas
    LinearConstraint,
    LinearSystem,
    FarkasLinearInterpolator,
    # Loop Invariant Synthesis
    LoopProgram,
    InvariantResult,
    InductiveLoopInvariantSynthesizer,
    # Unified Interpolation Interface
    CraigInterpolant,
    CraigInterpolationEngine,
)

__all__ = [
    "PropLiteral",
    "PropClause",
    "PropCNF",
    "BoolExpr",
    "BoolConst",
    "BoolVar",
    "BoolNot",
    "BoolAnd",
    "BoolOr",
    "ResolutionNode",
    "McMillanPropositionalInterpolator",
    "LinearConstraint",
    "LinearSystem",
    "FarkasLinearInterpolator",
    "LoopProgram",
    "InvariantResult",
    "InductiveLoopInvariantSynthesizer",
    "CraigInterpolant",
    "CraigInterpolationEngine",
]
