"""ACE DreamCoder-style Wake-Sleep Library Abstraction Module.

Compresses discovered solutions by mining recurring AST motifs across tasks and
parameterizing them into new reusable first-class DSL primitives (PRD G4).
"""
from __future__ import annotations

from .wake_sleep import WakeSleepAbstractionEngine, DiscoveredPrimitive

__all__ = ["WakeSleepAbstractionEngine", "DiscoveredPrimitive"]
