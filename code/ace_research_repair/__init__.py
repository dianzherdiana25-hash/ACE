"""ACE Fase 5 Autonomous Software Repair package (`code/ace_research_repair`).

Public interface exports `RepairEngine`, `RepairMemory`, and corpus metadata
while maintaining strict AST isolation from `evaluator.py`.
"""
from __future__ import annotations

from .corpus import (
    ARMS,
    BUDGET_K,
    FAMILIES,
    PRESCORE_COMMIT,
    PRESCORE_DOC_SHA256,
    CorpusUnit,
    DevTestCase,
    PerturbationSpec,
    PublicUnitView,
    source_units,
    target_units,
)
from .engine import PIPELINE_STAGES, RepairEngine
from .memory import MemoryIntegrityError, RepairMemory

__all__ = [
    "ARMS",
    "BUDGET_K",
    "CorpusUnit",
    "DevTestCase",
    "FAMILIES",
    "MemoryIntegrityError",
    "PIPELINE_STAGES",
    "PRESCORE_COMMIT",
    "PRESCORE_DOC_SHA256",
    "PerturbationSpec",
    "PublicUnitView",
    "RepairEngine",
    "RepairMemory",
    "source_units",
    "target_units",
]
