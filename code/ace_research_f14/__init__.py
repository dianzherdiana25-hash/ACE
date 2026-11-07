"""ACE F14 Autonomous Mechanism Discovery Package.

Provides compositional grammar G_mech, autonomous error diagnosis,
and generational progression G0 -> G1 -> G2 under Host Controller governance.
"""
from __future__ import annotations

from .benchmark import run_f14_discovery_benchmark, save_evidence_f14
from .discovery_engine import (
    AutonomousGenerationalDiscovery,
    ErrorDiagnostic,
    ErrorDiagnoser,
    GrammarSearchEngine,
)
from .grammar import (
    ASTNode,
    CountOp,
    DyckBalanceOp,
    HalfSplitOp,
    InputString,
    LengthOp,
    ModEqPred,
    RelationalEqPred,
    SliceOp,
    compile_ast_to_callable,
)

__all__ = [
    "ASTNode",
    "AutonomousGenerationalDiscovery",
    "CountOp",
    "DyckBalanceOp",
    "ErrorDiagnostic",
    "ErrorDiagnoser",
    "GrammarSearchEngine",
    "HalfSplitOp",
    "InputString",
    "LengthOp",
    "ModEqPred",
    "RelationalEqPred",
    "SliceOp",
    "compile_ast_to_callable",
    "run_f14_discovery_benchmark",
    "save_evidence_f14",
]
