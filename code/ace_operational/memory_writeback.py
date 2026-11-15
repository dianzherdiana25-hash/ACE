"""Event-time write-back of verified events into cognitive memory.

Absorption audit (PR #231) item #8 — design:
`handover/MEMORY_WRITE_PATH_DESIGN_20261115.md`.

ACE's cognitive memory (mission 0002) held only the two
operator seed records, because nothing ever wrote verified
outcomes into it: ratifications, sealed verdicts, verified
skills and HIGH findings all lived in journals and state
files instead. This module is the write path, v1. Per the
hub's decision it starts at ratification points controlled
by Ian + hub — the evolution verifier's ratification seam
and the operator CLI (`tools/memory_writeback.py`) — not
inside the autonomous engine; that line can adopt the same
helper through its own ratification later.

Rules (design sections 3–4):
- Only events carrying external verification evidence are
  written. The evidence bytes are anchored in the store
  first and the record's `source_ref` is the anchor digest;
  the store fail-closes evidence records without one.
- Writes are replay-safe: the helper checks for an existing
  record with the same content and evidence digest before
  writing and returns its ID. (The store's own IDs are
  content-derived but embed `written_seq`, so its built-in
  dedup cannot fire across sessions — the pre-check here
  is what makes replay idempotent.)
- A failed write is logged and reported as ``None``; it
  never blocks or falsifies the caller's own verdict.
- Record content is a one-line summary plus references —
  never the evidence payload itself.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .cognitive_memory import CognitiveMemory

logger = logging.getLogger(__name__)

# Event class -> (record kind, default confidence). Design §3.
EVENT_CLASSES: dict[str, tuple[str, float]] = {
    "skill_verified": ("procedural", 0.90),
    "verdict_sealed": ("semantic", 0.95),
    "mission_ratified": ("episodic", 0.95),
    "finding_high_opened": ("episodic", 0.90),
    "finding_high_closed": ("episodic", 0.90),
}


def record_verified_event(
    memory_root: str | Path,
    *,
    event: str,
    summary: str,
    evidence_bytes: bytes,
    confidence: float | None = None,
    content_extra: dict[str, Any] | None = None,
) -> str | None:
    """Anchor `evidence_bytes` and write one record for a
    verified event. Returns the record ID, or None when the
    write failed (the failure is logged, never silent).

    Raises ValueError for an unknown event class — that is a
    programming error, not a runtime condition.
    """
    if event not in EVENT_CLASSES:
        raise ValueError(f"unknown memory event class {event!r}")
    kind, default_confidence = EVENT_CLASSES[event]
    content: dict[str, Any] = {"event": summary, "class": event}
    if content_extra:
        content.update(content_extra)
    try:
        memory = CognitiveMemory(memory_root)
        digest = memory.anchor_evidence(evidence_bytes)
        for existing in memory._records.values():
            if (existing["content"] == content
                    and existing["source"].get("ref") == digest):
                return existing["id"]
        return memory.remember(
            kind=kind,
            content=content,
            source_kind="evidence",
            source_ref=digest,
            confidence=default_confidence if confidence is None else confidence,
            sensitivity="internal",
        )
    except Exception as exc:
        logger.warning("memory write-back failed (%s): %s", event, exc)
        return None


def recall_context(
    memory_root: str | Path,
    query: str,
    *,
    kinds: list[str] | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Recall records relevant to `query` (the read side of
    the loop: surface past verified outcomes before a
    verify/repair cycle decides). Returns [] on failure,
    logged."""
    try:
        memory = CognitiveMemory(memory_root)
        return memory.recall(query, kinds=kinds, limit=limit)["results"]
    except Exception as exc:
        logger.warning("memory recall failed: %s", exc)
        return []


def record_event_outcomes(
    memory_root: str | Path,
    records: list[dict[str, Any]],
    *,
    context: str,
    success: bool,
) -> int:
    """Close the read loop: attach the cycle's outcome to
    the records it recalled. The store attaches outcomes
    only to procedural records, so other kinds are context
    only and are skipped. Returns how many outcomes were
    recorded; failures are logged per record."""
    try:
        memory = CognitiveMemory(memory_root)
    except Exception as exc:
        logger.warning("memory outcome recording failed: %s", exc)
        return 0
    recorded = 0
    for record in records:
        if record.get("kind") != "procedural":
            continue
        try:
            memory.record_outcome(record["id"], context=context,
                                  success=success)
            recorded += 1
        except Exception as exc:
            logger.warning("memory outcome failed for %s: %s",
                           record.get("id"), exc)
    return recorded
