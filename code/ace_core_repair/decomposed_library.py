"""Decomposed component capability library supporting component-level inheritance (W3)."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple


class DecomposedLibrary:
    """Stores decomposed sub-components (counters, guards) with boolean composition operators."""

    def __init__(self):
        self.counters: Dict[str, Callable[[str], bool]] = {}
        self.guards: Dict[str, Callable[[str], bool]] = {}

    def register_component(self, name: str, kind: str, predicate: Callable[[str], bool]):
        if kind == "counter":
            self.counters[name] = predicate
        elif kind == "guard":
            self.guards[name] = predicate
        else:
            raise ValueError(f"Unknown component kind '{kind}', allowed: 'counter', 'guard'")

    def compose_and_solve(
        self,
        train_data: List[Tuple[str, bool]]
    ) -> Tuple[Optional[Callable[[str], bool]], int]:
        """Tries combinations of existing counters and guards via AND/OR/NOT operators before refitting."""
        # 1. Try single components
        for c_name, c_pred in self.counters.items():
            if all(bool(c_pred(w)) == y for w, y in train_data):
                return c_pred, 1

        for g_name, g_pred in self.guards.items():
            if all(bool(g_pred(w)) == y for w, y in train_data):
                return g_pred, 1

        # 2. Try AND composition: guard AND counter
        for g_name, g_pred in self.guards.items():
            for c_name, c_pred in self.counters.items():
                composite = lambda w, g=g_pred, c=c_pred: bool(g(w)) and bool(c(w))
                if all(composite(w) == y for w, y in train_data):
                    return composite, 1

        # 3. Try OR composition: guard OR counter
        for g_name, g_pred in self.guards.items():
            for c_name, c_pred in self.counters.items():
                composite_or = lambda w, g=g_pred, c=c_pred: bool(g(w)) or bool(c(w))
                if all(composite_or(w) == y for w, y in train_data):
                    return composite_or, 1

        return None, 0
