"""Typed graph adjacency traversal primitives for bounded graph reasoning (W4)."""
from __future__ import annotations

from typing import List, Tuple


class GraphAdjacencyPrimitive:
    """Bounded graph traversal operator operating on adjacency bitstrings.

    Vertices: 4 (0, 1, 2, 3)
    Edges representation: length 6 string where 'a' indicates presence of edge:
    Index 0: (0, 1)
    Index 1: (0, 2)
    Index 2: (0, 3)
    Index 3: (1, 2)
    Index 4: (1, 3)
    Index 5: (2, 3)
    """

    EDGES: List[Tuple[int, int]] = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]

    def __init__(self, target_nodes: int = 4):
        self.target_nodes = target_nodes

    def predict(self, word: str) -> bool:
        if len(word) < 6:
            return False

        adj = {i: [] for i in range(self.target_nodes)}
        for idx in range(min(6, len(word))):
            if word[idx] == "a":
                u, v = self.EDGES[idx]
                adj[u].append(v)
                adj[v].append(u)

        visited = set()
        queue = [0]
        while queue:
            curr = queue.pop(0)
            if curr not in visited:
                visited.add(curr)
                for neighbor in adj[curr]:
                    if neighbor not in visited:
                        queue.append(neighbor)

        return len(visited) == self.target_nodes
