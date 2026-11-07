"""Typed exception hierarchy for ACE Autonomous Runtime.

``IntegrityError`` intentionally inherits from ``RuntimeError`` rather than
``ValueError`` so operational input-validation handlers never swallow journal,
key, provenance, or receipt corruption.
"""
from __future__ import annotations


class IntegrityError(RuntimeError):
    """Raised when durable state, receipts, keys, or source provenance fail verification."""


class PolicyError(ValueError):
    """Raised when an untrusted goal, tool, path, or scope violates ExecutionPolicy."""


class BudgetExhaustedError(RuntimeError):
    """Raised when a goal exceeds step, candidate, retry, wall-clock, or CPU ceilings."""


class UncertainExternalEffectError(RuntimeError):
    """Raised when an escrowed external action loses receipt certainty (HALT_UNCERTAIN)."""
