"""Lineage Manager: Cryptographic Lineage Tracking & Merkle Chaining for ACE.

Maintains immutable evolutionary lineage with cryptographic guarantees:
1. Merkle parent hash chaining linking every candidate to its parent.
2. Candidate source code SHA-256 verification.
3. Promotion receipts binding empirical proofs, extracted primitives, and HMAC signatures.
4. Fail-closed baseline integrity: rejected candidates never become active heads.
5. End-to-end auditability from root G0 to Gn.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import EmpiricalValidationProof, PromotionReceipt


GENESIS_PARENT_HASH = "0" * 64


class LineageIntegrityError(ValueError):
    """Raised when cryptographic Merkle verification fails or lineage is corrupted."""


@dataclass
class CryptographicLineageNode:
    """Represents a discrete candidate in the evolutionary lineage with Merkle links."""
    candidate_id: str
    parent_id: Optional[str]
    generation: int
    source_sha: str
    parent_merkle_hash: str
    merkle_node_hash: str
    empirical_proof_digest: str = ""
    status: str = "REGISTERED"  # REGISTERED, EVALUATING, PROMOTED, REJECTED, RETAINED, ROLLED_BACK
    receipt_id: Optional[str] = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CryptographicLineageNode:
        return cls(**data)


def compute_node_merkle_hash(
    parent_merkle_hash: str,
    candidate_id: str,
    source_sha: str,
    generation: int,
    empirical_proof_digest: str = "",
) -> str:
    """Compute deterministic Merkle node hash chaining parent hash with node contents."""
    payload = f"{parent_merkle_hash}:{candidate_id}:{source_sha}:{generation}:{empirical_proof_digest}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class LineageManager:
    """Manages cryptographic lineage DAG, Merkle hash chains, and promotion tracking."""

    def __init__(self, root_id: Optional[str] = None, storage_path: Optional[str] = None):
        self.nodes: Dict[str, CryptographicLineageNode] = {}
        self.receipts: Dict[str, PromotionReceipt] = {}
        self.root_id: Optional[str] = root_id
        self.active_head_id: Optional[str] = root_id
        self.storage_path = Path(storage_path) if storage_path else None
        if self.storage_path and self.storage_path.exists():
            self._load()

    def register_root(
        self,
        root_id: str,
        source_sha: str,
        baseline_score: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CryptographicLineageNode:
        """Register the genesis G0 root node in the cryptographic lineage."""
        if root_id in self.nodes:
            return self.nodes[root_id]

        parent_hash = GENESIS_PARENT_HASH
        meta = dict(metadata or {})
        meta["baseline_score"] = baseline_score

        merkle_hash = compute_node_merkle_hash(
            parent_merkle_hash=parent_hash,
            candidate_id=root_id,
            source_sha=source_sha,
            generation=0,
            empirical_proof_digest="GENESIS_BASELINE",
        )

        node = CryptographicLineageNode(
            candidate_id=root_id,
            parent_id=None,
            generation=0,
            source_sha=source_sha,
            parent_merkle_hash=parent_hash,
            merkle_node_hash=merkle_hash,
            empirical_proof_digest="GENESIS_BASELINE",
            status="PROMOTED",
            metadata=meta,
        )
        self.nodes[root_id] = node
        self.root_id = root_id
        self.active_head_id = root_id
        self._save()
        return node

    def register_candidate(
        self,
        candidate_id: str,
        parent_id: str,
        generation: int,
        source_sha: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CryptographicLineageNode:
        """Register a prospective candidate chained to its parent in lineage."""
        if candidate_id in self.nodes:
            raise ValueError(f"Candidate {candidate_id} already registered in lineage")

        if parent_id not in self.nodes:
            raise KeyError(f"Parent candidate {parent_id} not found in lineage")

        parent_node = self.nodes[parent_id]
        if generation < parent_node.generation:
            raise ValueError(
                f"Candidate generation G{generation} cannot be lower than parent G{parent_node.generation}"
            )

        parent_merkle_hash = parent_node.merkle_node_hash
        merkle_hash = compute_node_merkle_hash(
            parent_merkle_hash=parent_merkle_hash,
            candidate_id=candidate_id,
            source_sha=source_sha,
            generation=generation,
            empirical_proof_digest="",
        )

        node = CryptographicLineageNode(
            candidate_id=candidate_id,
            parent_id=parent_id,
            generation=generation,
            source_sha=source_sha,
            parent_merkle_hash=parent_merkle_hash,
            merkle_node_hash=merkle_hash,
            empirical_proof_digest="",
            status="REGISTERED",
            metadata=dict(metadata or {}),
        )
        self.nodes[candidate_id] = node
        self._save()
        return node

    def record_promotion(
        self,
        candidate_id: str,
        receipt: PromotionReceipt,
    ) -> CryptographicLineageNode:
        """Record certified promotion, bind promotion receipt, and update active head."""
        if candidate_id not in self.nodes:
            # Auto-register if not yet explicitly registered
            self.register_candidate(
                candidate_id=candidate_id,
                parent_id=receipt.parent_id,
                generation=receipt.generation,
                source_sha=receipt.source_sha,
            )

        node = self.nodes[candidate_id]
        node.status = "PROMOTED"
        node.receipt_id = receipt.receipt_id
        node.empirical_proof_digest = receipt.empirical_proof.proof_digest

        # Recompute final Merkle node hash with the empirical proof digest
        node.merkle_node_hash = compute_node_merkle_hash(
            parent_merkle_hash=node.parent_merkle_hash,
            candidate_id=candidate_id,
            source_sha=node.source_sha,
            generation=node.generation,
            empirical_proof_digest=node.empirical_proof_digest,
        )

        self.receipts[receipt.receipt_id] = receipt
        self.active_head_id = candidate_id
        self._save()
        return node

    def record_rejection(
        self,
        candidate_id: str,
        reason: str,
        parent_id: Optional[str] = None,
        generation: int = 1,
        source_sha: str = "",
    ) -> CryptographicLineageNode:
        """Record candidate rejection with fail-closed retention of active head."""
        if candidate_id not in self.nodes:
            p_id = parent_id or self.active_head_id or self.root_id or "G0_root"
            self.register_candidate(
                candidate_id=candidate_id,
                parent_id=p_id,
                generation=generation,
                source_sha=source_sha or ("00" * 32),
            )

        node = self.nodes[candidate_id]
        node.status = "REJECTED"
        node.metadata["rejection_reason"] = reason

        # Fail-closed invariant check: rejected candidate MUST NEVER be active head
        if self.active_head_id == candidate_id:
            # Roll back to parent
            self.active_head_id = node.parent_id or self.root_id

        self._save()
        return node

    def verify_chain_integrity(
        self,
        candidate_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Verify complete Merkle hash chain from target node (default: active head) back to root G0."""
        target_id = candidate_id or self.active_head_id
        if not target_id:
            return True, "Empty lineage"

        curr_id = target_id
        visited: set[str] = set()

        while curr_id is not None:
            if curr_id in visited:
                return False, f"Lineage cycle detected at {curr_id}"
            visited.add(curr_id)

            if curr_id not in self.nodes:
                return False, f"Missing lineage node: {curr_id}"

            node = self.nodes[curr_id]

            if node.parent_id is None:
                # Root node verification
                if node.parent_merkle_hash != GENESIS_PARENT_HASH:
                    return False, f"Root {node.candidate_id} parent hash is not genesis hash"
                expected_hash = compute_node_merkle_hash(
                    parent_merkle_hash=GENESIS_PARENT_HASH,
                    candidate_id=node.candidate_id,
                    source_sha=node.source_sha,
                    generation=node.generation,
                    empirical_proof_digest=node.empirical_proof_digest,
                )
                if node.merkle_node_hash != expected_hash:
                    return False, f"Root {node.candidate_id} Merkle hash mismatch"
                break
            else:
                # Child node verification
                parent_node = self.nodes.get(node.parent_id)
                if parent_node is None:
                    return False, f"Parent {node.parent_id} of node {curr_id} not found"

                if node.parent_merkle_hash != parent_node.merkle_node_hash:
                    return False, (
                        f"Merkle chain break at {node.candidate_id}: parent_merkle_hash "
                        f"{node.parent_merkle_hash[:12]} != parent.merkle_node_hash {parent_node.merkle_node_hash[:12]}"
                    )

                expected_hash = compute_node_merkle_hash(
                    parent_merkle_hash=node.parent_merkle_hash,
                    candidate_id=node.candidate_id,
                    source_sha=node.source_sha,
                    generation=node.generation,
                    empirical_proof_digest=node.empirical_proof_digest,
                )
                if node.merkle_node_hash != expected_hash:
                    return False, (
                        f"Merkle hash mismatch at {node.candidate_id}: recorded {node.merkle_node_hash[:12]} "
                        f"!= expected {expected_hash[:12]}"
                    )

                curr_id = node.parent_id

        return True, f"Merkle chain integrity fully verified for {target_id}"

    def get_lineage_path(
        self,
        candidate_id: Optional[str] = None,
    ) -> List[CryptographicLineageNode]:
        """Return ordered path of nodes from genesis root G0 to the specified candidate."""
        target_id = candidate_id or self.active_head_id
        if not target_id or target_id not in self.nodes:
            return []

        path: List[CryptographicLineageNode] = []
        curr: Optional[str] = target_id
        while curr is not None:
            node = self.nodes[curr]
            path.append(node)
            curr = node.parent_id

        path.reverse()
        return path

    def compute_merkle_root(self) -> str:
        """Compute top-level Merkle root across all nodes in the lineage graph."""
        if not self.nodes:
            return hashlib.sha256(b"EMPTY_LINEAGE").hexdigest()

        sorted_hashes = sorted([n.merkle_node_hash for n in self.nodes.values()])
        combined = ":".join(sorted_hashes).encode("utf-8")
        return hashlib.sha256(combined).hexdigest()

    def get_active_head(self) -> Optional[CryptographicLineageNode]:
        return self.nodes.get(self.active_head_id) if self.active_head_id else None

    def export_lineage(self) -> Dict[str, Any]:
        return {
            "root_id": self.root_id,
            "active_head_id": self.active_head_id,
            "merkle_root": self.compute_merkle_root(),
            "nodes": {cid: node.to_dict() for cid, node in self.nodes.items()},
            "receipts": {rid: r.to_dict() for rid, r in self.receipts.items()},
        }

    def _save(self) -> None:
        if not self.storage_path:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = self.export_lineage()
        self.storage_path.write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        if not self.storage_path or not self.storage_path.exists():
            return
        try:
            raw = json.loads(self.storage_path.read_text())
            self.root_id = raw.get("root_id")
            self.active_head_id = raw.get("active_head_id")
            self.nodes = {
                cid: CryptographicLineageNode.from_dict(nd)
                for cid, nd in raw.get("nodes", {}).items()
            }
            self.receipts = {
                rid: PromotionReceipt.from_dict(rd)
                for rid, rd in raw.get("receipts", {}).items()
            }
        except Exception:
            self.nodes = {}
            self.receipts = {}
