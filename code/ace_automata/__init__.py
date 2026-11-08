"""ACE Active Automata Learning Module based on Angluin's L* algorithm.

Provably learns minimal Deterministic Finite Automata (DFA) from membership queries
and counterexamples. Fully compatible with ACE's runtime R1 Automaton signatures.
"""
from __future__ import annotations

from .lstar import LStarLearner, DFA, ObservationTable

__all__ = ["LStarLearner", "DFA", "ObservationTable"]
