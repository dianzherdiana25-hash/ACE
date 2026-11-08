"""Out-of-grammar ratio 4:1 modular primitives (W4)."""
from __future__ import annotations


class Ratio4ModularPrimitive:
    """Predicts True when count(a) > 4 * count(b) using integer arithmetic."""

    def predict(self, word: str) -> bool:
        na = word.count("a")
        nb = word.count("b")
        return na > (4 * nb)
