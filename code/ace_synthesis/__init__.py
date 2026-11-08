"""ACE Program Synthesis Module.

Features Counterexample-Guided Inductive Synthesis (CEGIS) for fast, verified program discovery.
"""
from __future__ import annotations

from .cegis import CEGISSynthesizer, SynthesisResult

__all__ = ["CEGISSynthesizer", "SynthesisResult"]
