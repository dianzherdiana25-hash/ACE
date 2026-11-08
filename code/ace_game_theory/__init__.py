"""ACE Game-Theoretic Minimax Adversarial Synthesis Package."""
from ace_game_theory.minimax_synthesizer import (
    HedgePlayer,
    MinimaxCoEvolution,
    TwoPlayerGameMatrix,
    compute_nash_gap,
)

__all__ = [
    "HedgePlayer",
    "MinimaxCoEvolution",
    "TwoPlayerGameMatrix",
    "compute_nash_gap",
]
