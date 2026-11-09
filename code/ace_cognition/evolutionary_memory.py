"""Evolutionary Associative Memory for Cross-Cycle Knowledge Transfer.

Pure-Python (zero-dependency, marginal cost $0.00) associative memory buffer.
Vectorizes code candidates, hypotheses, and execution traces using character/token
n-grams and cosine similarity to transfer successful programmatic mechanisms
across autonomous research cycles.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple


def _tokenize(text: str) -> List[str]:
    """Tokenize code or text into structural tokens."""
    return re.findall(r"[A-Za-z0-9_]+|[^\s\w]", text)


def _compute_vector(tokens: List[str], n: int = 3) -> Dict[str, float]:
    """Compute normalized n-gram term frequency vector."""
    counts: Dict[str, int] = {}
    total = 0

    # 1. Word tokens
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
        total += 1

    # 2. Token n-grams for syntax motifs
    if len(tokens) >= n:
        for i in range(len(tokens) - n + 1):
            gram = " ".join(tokens[i : i + n])
            counts[gram] = counts.get(gram, 0) + 2
            total += 2

    if total == 0:
        return {}

    # L2 normalize
    norm_sq = sum(c * c for c in counts.values())
    l2_norm = math.sqrt(norm_sq) if norm_sq > 0 else 1.0
    return {k: v / l2_norm for k, v in counts.items()}


def _cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """Compute cosine similarity between two sparse unit vectors."""
    if not vec_a or not vec_b:
        return 0.0
    # Iterate over smaller dict
    if len(vec_a) > len(vec_b):
        vec_a, vec_b = vec_b, vec_a
    return sum(val * vec_b.get(k, 0.0) for k, val in vec_a.items())


@dataclass
class MemoryEntry:
    entry_id: str
    cycle_id: int
    task_id: str
    hypothesis_id: str
    source_code: str
    score: float
    decision: str
    feature_vector: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "cycle_id": self.cycle_id,
            "task_id": self.task_id,
            "hypothesis_id": self.hypothesis_id,
            "source_code": self.source_code,
            "score": self.score,
            "decision": self.decision,
            "feature_vector": self.feature_vector,
            "metadata": self.metadata,
        }


class EvolutionaryMemory:
    """Persistent cross-cycle associative memory for code synthesis and repair."""

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path) if storage_path else None
        self.entries: List[MemoryEntry] = []
        if self.storage_path and self.storage_path.exists():
            self._load()

    def record_experience(
        self,
        cycle_id: int,
        task_id: str,
        hypothesis_id: str,
        source_code: str,
        score: float,
        decision: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryEntry:
        """Vectorize and store an empirical candidate outcome in memory."""
        tokens = _tokenize(source_code)
        vector = _compute_vector(tokens)
        entry = MemoryEntry(
            entry_id=f"mem_c{cycle_id}_{len(self.entries) + 1}",
            cycle_id=cycle_id,
            task_id=task_id,
            hypothesis_id=hypothesis_id,
            source_code=source_code,
            score=score,
            decision=decision,
            feature_vector=vector,
            metadata=metadata or {},
        )
        self.entries.append(entry)
        if self.storage_path:
            self._save()
        return entry

    def query_similar(
        self,
        query_text: str,
        top_k: int = 3,
        min_similarity: float = 0.15,
        decision_filter: Optional[str] = "ACCEPTED",
    ) -> List[Tuple[MemoryEntry, float]]:
        """Find most structurally similar past code memories."""
        q_tokens = _tokenize(query_text)
        q_vec = _compute_vector(q_tokens)

        scored: List[Tuple[MemoryEntry, float]] = []
        for e in self.entries:
            if decision_filter and e.decision != decision_filter:
                continue
            sim = _cosine_similarity(q_vec, e.feature_vector)
            if sim >= min_similarity:
                scored.append((e, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def _save(self) -> None:
        if not self.storage_path:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = [e.to_dict() for e in self.entries]
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _load(self) -> None:
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.entries = [
                MemoryEntry(
                    entry_id=d["entry_id"],
                    cycle_id=d["cycle_id"],
                    task_id=d["task_id"],
                    hypothesis_id=d["hypothesis_id"],
                    source_code=d["source_code"],
                    score=d["score"],
                    decision=d["decision"],
                    feature_vector=d.get("feature_vector", {}),
                    metadata=d.get("metadata", {}),
                )
                for d in data
            ]
        except Exception:
            self.entries = []
