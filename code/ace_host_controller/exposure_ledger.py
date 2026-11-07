"""Exposure ledger tracking and benchmark contamination verification for ACE Host Controller.

Maintains an append-only cryptographic journal of every input, query, or feedback item
exposed to the research agent, and mathematically verifies disjointness against sealed holdouts.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable


class ContaminationError(RuntimeError):
    """Raised when benchmark contamination (leakage of holdout inputs into training/search) is detected."""


@dataclass(frozen=True)
class ExposureRecord:
    """Record of an input or query exposed to a research candidate."""

    candidate_id: str
    query_type: str
    query_content: str
    query_hash: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize record to dictionary."""
        return asdict(self)


class ExposureLedger:
    """Append-only exposure ledger preventing benchmark test set contamination."""

    def __init__(self):
        self.records: list[ExposureRecord] = []
        self._exposed_hashes: set[str] = set()
        self._exposed_contents: set[str] = set()

    def record_exposure(
        self, candidate_id: str, query_type: str, content: str
    ) -> ExposureRecord:
        """Record an exposed query or training sample in the append-only ledger."""
        q_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        record = ExposureRecord(
            candidate_id=candidate_id,
            query_type=query_type,
            query_content=content,
            query_hash=q_hash,
        )
        self.records.append(record)
        self._exposed_hashes.add(q_hash)
        self._exposed_contents.add(content)
        return record

    def check_contamination(self, holdout_inputs: Iterable[str]) -> tuple[bool, list[str]]:
        """Check whether any holdout input was exposed in the research process.
        
        Returns:
            (is_contaminated, matching_inputs)
        """
        leaks: list[str] = []
        for inp in holdout_inputs:
            inp_hash = hashlib.sha256(inp.encode("utf-8")).hexdigest()
            if inp_hash in self._exposed_hashes or inp in self._exposed_contents:
                leaks.append(inp)
        return len(leaks) > 0, leaks

    def assert_clean(self, holdout_inputs: Iterable[str]) -> None:
        """Enforce strict non-contamination. Fails closed with ContaminationError if leakage occurred."""
        is_contaminated, leaks = self.check_contamination(holdout_inputs)
        if is_contaminated:
            raise ContaminationError(
                f"Benchmark contamination detected! {len(leaks)} holdout inputs were exposed during search: {leaks[:5]}"
            )

    def ledger_digest(self) -> str:
        """Deterministic SHA-256 digest over the entire exposure journal."""
        serialized = json.dumps(
            [r.to_dict() for r in self.records],
            sort_keys=True,
            ensure_ascii=True,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize exposure ledger to dictionary."""
        return {
            "record_count": len(self.records),
            "ledger_digest": self.ledger_digest(),
            "records": [r.to_dict() for r in self.records],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExposureLedger:
        """Construct exposure ledger from dictionary."""
        ledger = cls()
        for rec_dict in data.get("records", []):
            rec = ExposureRecord(**rec_dict)
            ledger.records.append(rec)
            ledger._exposed_hashes.add(rec.query_hash)
            ledger._exposed_contents.add(rec.query_content)
        return ledger
