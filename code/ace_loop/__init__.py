"""ACE E1.5 public-development autonomous research harness.

Runnable deterministic experimentation; NOT unrestricted AI or OAIE.
"""
from .engine import ResearchEngine, ResearchIntegrityError

__all__ = ['ResearchEngine', 'ResearchIntegrityError']
