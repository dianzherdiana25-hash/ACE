"""Lineage graph tracking and candidate lineage governance for ACE Host Controller.

Maintains immutable parent-child relationships, generational tags (G0, G1, G2),
source SHA-256 hashes, evaluation metrics, and rollback points.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Optional


class LineageCycleError(ValueError):
    """Raised when a cycle is detected in the candidate lineage DAG."""


class LineageNotFoundError(KeyError):
    """Raised when a referenced candidate node does not exist in lineage."""


@dataclass
class CandidateNode:
    """Represents a discrete candidate in the evolutionary lineage."""

    candidate_id: str
    parent_id: Optional[str]
    source_sha: str
    generation: int
    lineage_depth: int
    status: str = "REGISTERED"  # REGISTERED, EVALUATING, ACCEPTED, REJECTED, ROLLED_BACK
    holdout_score: float = 0.0
    prior_score: float = 0.0
    regression: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize candidate node to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CandidateNode:
        """Construct candidate node from dictionary."""
        return cls(**data)


class LineageGraph:
    """Manages the candidate lineage DAG, tracking ancestors, generation jumps, and active head."""

    def __init__(self, root_id: Optional[str] = None):
        self.nodes: dict[str, CandidateNode] = {}
        self.root_id: Optional[str] = root_id
        self.active_head_id: Optional[str] = root_id

    def register_candidate(
        self,
        candidate_id: str,
        parent_id: Optional[str],
        source_sha: str,
        generation: int,
        metadata: Optional[dict[str, Any]] = None,
    ) -> CandidateNode:
        """Register a new candidate in the lineage DAG."""
        if candidate_id in self.nodes:
            raise ValueError(f"Candidate {candidate_id} already registered in lineage")

        if parent_id is not None:
            if parent_id not in self.nodes:
                raise LineageNotFoundError(f"Parent candidate {parent_id} not found in lineage")
            parent_node = self.nodes[parent_id]
            depth = parent_node.lineage_depth + 1
            if generation < parent_node.generation:
                raise ValueError(
                    f"Candidate generation G{generation} cannot be lower than parent generation G{parent_node.generation}"
                )
        else:
            depth = 0
            if self.root_id is None:
                self.root_id = candidate_id

        node = CandidateNode(
            candidate_id=candidate_id,
            parent_id=parent_id,
            source_sha=source_sha,
            generation=generation,
            lineage_depth=depth,
            status="REGISTERED",
            metadata=dict(metadata or {}),
        )
        self.nodes[candidate_id] = node
        return node

    def update_status(
        self,
        candidate_id: str,
        status: str,
        holdout_score: Optional[float] = None,
        prior_score: Optional[float] = None,
        regression: Optional[float] = None,
    ) -> CandidateNode:
        """Update evaluation status and scores for a candidate."""
        if candidate_id not in self.nodes:
            raise LineageNotFoundError(f"Candidate {candidate_id} not found")
        node = self.nodes[candidate_id]
        node.status = status
        if holdout_score is not None:
            node.holdout_score = float(holdout_score)
        if prior_score is not None:
            node.prior_score = float(prior_score)
        if regression is not None:
            node.regression = float(regression)

        if status == "ACCEPTED":
            self.active_head_id = candidate_id
        return node

    def get_ancestors(self, candidate_id: str) -> list[str]:
        """Return list of ancestor candidate IDs from immediate parent to root."""
        ancestors: list[str] = []
        curr = candidate_id
        visited: set[str] = set()

        while curr is not None:
            if curr in visited:
                raise LineageCycleError(f"Cycle detected in lineage DAG involving {curr}")
            visited.add(curr)
            if curr not in self.nodes:
                break
            parent = self.nodes[curr].parent_id
            if parent is not None:
                ancestors.append(parent)
            curr = parent
        return ancestors

    def rollback_to(self, target_id: str) -> CandidateNode:
        """Roll back active head to target_id.
        
        Requires target_id to be an accepted ancestor of active_head_id.
        """
        if target_id not in self.nodes:
            raise LineageNotFoundError(f"Rollback target {target_id} not found")
        if self.active_head_id is None:
            raise ValueError("Cannot rollback: no active head set")

        target_node = self.nodes[target_id]
        if target_node.status != "ACCEPTED" and target_id != self.root_id:
            raise ValueError(f"Rollback target {target_id} is not an ACCEPTED candidate")

        if target_id == self.active_head_id:
            return target_node

        ancestors = self.get_ancestors(self.active_head_id)
        if target_id not in ancestors:
            raise ValueError(
                f"Cannot rollback to {target_id}: not an ancestor of active head {self.active_head_id}"
            )

        # Mark previous active head as ROLLED_BACK
        prev_head = self.nodes[self.active_head_id]
        prev_head.status = "ROLLED_BACK"

        # Update active head
        self.active_head_id = target_id
        return target_node

    def lineage_digest(self) -> str:
        """Deterministic SHA-256 digest over the lineage DAG."""
        serialized = json.dumps(
            {cid: node.to_dict() for cid, node in sorted(self.nodes.items())},
            sort_keys=True,
            ensure_ascii=True,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize lineage graph to dictionary."""
        return {
            "root_id": self.root_id,
            "active_head_id": self.active_head_id,
            "lineage_digest": self.lineage_digest(),
            "nodes": {cid: node.to_dict() for cid, node in sorted(self.nodes.items())},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LineageGraph:
        """Construct lineage graph from dictionary."""
        graph = cls(root_id=data.get("root_id"))
        graph.active_head_id = data.get("active_head_id")
        for cid, node_dict in data.get("nodes", {}).items():
            graph.nodes[cid] = CandidateNode.from_dict(node_dict)
        return graph
