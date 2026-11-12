"""OMEGA-07 — Persistent Cognitive Memory.

A durable memory for the lab with three record kinds — episodic (what
happened), semantic (facts), procedural (how to do something) — built on
the programme's truthfulness rules:

* **Provenance is structural.** Every record names its source kind:
  ``evidence`` (anchored to bytes whose digest was registered first),
  ``operator``, ``external`` or ``model``. A model-sourced record is a
  *guess* forever: it cannot upgrade itself, and in a conflict it never
  displaces an evidence-backed fact.
* **Conflicts are kept, not hidden.** A newer semantic fact supersedes
  the older one for the same (subject, predicate); the superseded record
  stays retrievable, marked as such.
* **Forgetting is an auditable act.** Forgetting writes a tombstone:
  the content is destroyed, the tombstone keeps the record ID, the
  reason, and the original content hash. Nothing vanishes silently.
* **Retrieval is bounded and honest.** Recall enforces a record limit
  and a token budget, and reports when it truncated. Private records are
  excluded unless the caller explicitly asks for them. Stale and expired
  records are flagged, never silently presented as current.
* **Negative transfer is surfaced.** Procedural records track outcomes
  per context; recalling a procedure into a context where it has failed
  (or never succeeded) flags the risk instead of recommending blindly.

Persistence is an append-only, hash-chained JSONL log; state is rebuilt
by replay on open, so memory survives process death (OMEGA-04's lesson:
checkpoints on disk are what survive here).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


class MemoryError(Exception):
    """Base class for cognitive-memory rejections."""


class ProvenanceError(MemoryError):
    pass


class ContaminationError(MemoryError):
    pass


class NotFoundError(MemoryError):
    pass


KINDS = ("episodic", "semantic", "procedural")
SOURCE_KINDS = ("evidence", "operator", "external", "model")
_SOURCE_RANK = {"evidence": 0, "operator": 1, "external": 2, "model": 3}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)):
        return hashlib.sha256(bytes(value)).hexdigest()
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _tokens(text: str) -> set[str]:
    import re
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


class CognitiveMemory:
    """Persistent cognitive memory rooted at one directory."""

    def __init__(self, root: str | Path, *, canary_tokens: list[str] | None = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.log_path = self.root / "memory.jsonl"
        if not self.log_path.exists():
            self.log_path.write_text("", encoding="utf-8")
        self.canary_tokens = canary_tokens or []
        self._anchors: set[str] = set()
        self._records: dict[str, dict[str, Any]] = {}
        self._tombstones: dict[str, dict[str, Any]] = {}
        self._seq = 0
        self._chain_ok = True
        self._replay()

    # ------------------------------------------------------------------
    # persistence (append-only, hash-chained)
    # ------------------------------------------------------------------
    def _replay(self) -> None:
        prev = "GENESIS"
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("prev") != prev or entry.get("hash") != _digest(
                    {"prev": prev, "event": entry.get("event")}):
                self._chain_ok = False
            prev = entry.get("hash", prev)
            self._seq = entry.get("seq", self._seq)
            self._apply(entry["event"])

    def _apply(self, event: dict[str, Any]) -> None:
        etype = event.get("type")
        if etype == "anchor":
            self._anchors.add(event["digest"])
        elif etype == "record":
            self._records[event["record"]["id"]] = event["record"]
        elif etype == "supersede":
            record = self._records.get(event["record_id"])
            if record is not None:
                record["status"] = "superseded"
                record["superseded_by"] = event["by"]
        elif etype == "outcome":
            record = self._records.get(event["record_id"])
            if record is not None:
                outcomes = record.setdefault("outcomes", {})
                bucket = outcomes.setdefault(event["context"], {"success": 0, "fail": 0})
                bucket["success" if event["success"] else "fail"] += 1
        elif etype == "tombstone":
            record = self._records.pop(event["record_id"], None)
            self._tombstones[event["record_id"]] = {
                "record_id": event["record_id"], "reason": event["reason"],
                "content_hash": event["content_hash"],
                "kind": record["kind"] if record else None}

    def _append(self, event: dict[str, Any]) -> dict[str, Any]:
        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        prev = "GENESIS"
        if lines:
            prev = json.loads(lines[-1])["hash"]
        self._seq += 1
        entry = {"seq": self._seq, "prev": prev, "event": event}
        entry["hash"] = _digest({"prev": prev, "event": event})
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical(entry) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._apply(event)
        return entry

    # ------------------------------------------------------------------
    # provenance anchors
    # ------------------------------------------------------------------
    def anchor_evidence(self, evidence_bytes: bytes) -> str:
        """Register the digest of real evidence bytes. Returns the digest."""
        digest = _digest(evidence_bytes)
        if digest not in self._anchors:
            self._append({"type": "anchor", "digest": digest})
        return digest

    # ------------------------------------------------------------------
    # writing records
    # ------------------------------------------------------------------
    def remember(self, *, kind: str, content: dict[str, Any], source_kind: str,
                 source_ref: str | None = None, confidence: float = 0.5,
                 sensitivity: str = "internal",
                 valid_until_seq: int | None = None,
                 expires_after_events: int | None = None) -> str:
        """Write one record. Returns its content-derived ID."""
        if kind not in KINDS:
            raise MemoryError(f"unknown kind {kind!r}")
        if source_kind not in SOURCE_KINDS:
            raise MemoryError(f"unknown source kind {source_kind!r}")
        if source_kind == "evidence" and source_ref not in self._anchors:
            raise ProvenanceError(
                "evidence-sourced records require an anchored evidence digest")
        if not 0.0 <= confidence <= 1.0:
            raise MemoryError("confidence must be within 0..1")
        blob = _canonical(content)
        for token in self.canary_tokens:
            if token in blob:
                raise ContaminationError(f"canary token in record content: {token!r}")
        body = {
            "kind": kind, "content": content,
            "source": {"kind": source_kind, "ref": source_ref},
            "confidence": confidence, "sensitivity": sensitivity,
            "valid_until_seq": valid_until_seq,
            "written_seq": self._seq + 1,
            "expires_seq": (self._seq + 1 + expires_after_events
                            if expires_after_events is not None else None),
            "status": "active", "outcomes": {},
        }
        record_id = f"mem_{_digest(body)[:20]}"
        if record_id in self._records:
            return record_id
        record = {"id": record_id, **body}
        self._append({"type": "record", "record": record})
        if kind == "semantic":
            self._resolve_semantic_conflict(record)
        return record_id

    def _resolve_semantic_conflict(self, new: dict[str, Any]) -> None:
        key = (new["content"].get("subject"), new["content"].get("predicate"))
        if None in key:
            return
        for other in list(self._records.values()):
            if (other["id"] == new["id"] or other["kind"] != "semantic"
                    or other.get("status") != "active"):
                continue
            if (other["content"].get("subject"), other["content"].get("predicate")) != key:
                continue
            if other["content"].get("object") == new["content"].get("object"):
                continue
            # Conflict. Evidence beats guesses; then higher confidence;
            # then the newer record. The loser is superseded, never erased.
            def strength(r: dict[str, Any]) -> tuple[int, float, int]:
                return (-_SOURCE_RANK[r["source"]["kind"]], r["confidence"],
                        r["written_seq"])
            loser = other if strength(new) >= strength(other) else new
            winner = new if loser is other else other
            self._append({"type": "supersede", "record_id": loser["id"],
                          "by": winner["id"]})

    def record_outcome(self, record_id: str, *, context: str, success: bool) -> None:
        record = self._records.get(record_id)
        if record is None:
            raise NotFoundError(record_id)
        if record["kind"] != "procedural":
            raise MemoryError("outcomes attach to procedural records")
        self._append({"type": "outcome", "record_id": record_id,
                      "context": context, "success": success})

    def forget(self, record_id: str, *, reason: str) -> dict[str, Any]:
        """Tombstone a record: content destroyed, the act itself audited.

        The log is rewritten once (a redaction pass): the record's event
        is replaced in place by its tombstone and later references to the
        record are dropped, then the chain is rebuilt. Without this, an
        append-only log would keep the "forgotten" content forever.
        """
        record = self._records.get(record_id)
        if record is None:
            raise NotFoundError(record_id)
        content_hash = _digest({k: record[k] for k in ("kind", "content")})
        tombstone = {"type": "tombstone", "record_id": record_id,
                     "reason": reason, "content_hash": content_hash}
        rewritten: list[dict[str, Any]] = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)["event"]
            if event.get("type") == "record" and event["record"]["id"] == record_id:
                rewritten.append(tombstone)
            elif event.get("record_id") == record_id and event.get("type") in (
                    "supersede", "outcome"):
                continue  # dangling references to destroyed content
            else:
                rewritten.append(event)
        prev = "GENESIS"
        lines = []
        for seq, event in enumerate(rewritten, start=1):
            entry = {"seq": seq, "prev": prev, "event": event}
            entry["hash"] = _digest({"prev": prev, "event": event})
            prev = entry["hash"]
            lines.append(_canonical(entry))
        tmp = self.log_path.with_suffix(".tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.replace(tmp, self.log_path)
        self._anchors, self._records, self._tombstones = set(), {}, {}
        self._seq, self._chain_ok = 0, True
        self._replay()
        return self._tombstones[record_id]

    # ------------------------------------------------------------------
    # recall
    # ------------------------------------------------------------------
    def _is_expired(self, record: dict[str, Any]) -> bool:
        return record.get("expires_seq") is not None and self._seq >= record["expires_seq"]

    def _is_stale(self, record: dict[str, Any]) -> bool:
        return (record.get("valid_until_seq") is not None
                and self._seq > record["valid_until_seq"])

    def recall(self, query: str, *, kinds: list[str] | None = None,
               context: str | None = None, limit: int = 10,
               token_budget: int = 2000, include_private: bool = False,
               include_superseded: bool = False) -> dict[str, Any]:
        """Bounded recall. Reports truncation; flags stale/private rules."""
        query_tokens = _tokens(query)
        scored = []
        for record in self._records.values():
            if kinds and record["kind"] not in kinds:
                continue
            if record.get("status") == "superseded" and not include_superseded:
                continue
            if self._is_expired(record):
                continue
            if record.get("sensitivity") == "private" and not include_private:
                continue
            haystack = _tokens(_canonical(record["content"]))
            overlap = len(query_tokens & haystack)
            if query_tokens and overlap == 0:
                continue
            scored.append((record, overlap))
        # Deterministic order: relevance, then evidence before guesses,
        # then confidence, then recency, then ID.
        scored.sort(key=lambda pair: (-pair[1], _SOURCE_RANK[pair[0]["source"]["kind"]],
                                      -pair[0]["confidence"], -pair[0]["written_seq"],
                                      pair[0]["id"]))
        results = []
        used_tokens = 0
        truncated = False
        for record, overlap in scored:
            if len(results) >= limit:
                truncated = True
                break
            cost = max(1, len(_canonical(record["content"])) // 4)
            if used_tokens + cost > token_budget:
                truncated = True
                continue
            used_tokens += cost
            view = json.loads(_canonical(record))
            view["relevance"] = overlap
            view["stale"] = self._is_stale(record)
            view["guess"] = record["source"]["kind"] == "model"
            if record["kind"] == "procedural" and context is not None:
                outcomes = record.get("outcomes", {})
                here = outcomes.get(context, {"success": 0, "fail": 0})
                elsewhere_success = any(
                    v["success"] > 0 for k, v in outcomes.items() if k != context)
                view["negative_transfer_risk"] = bool(
                    here["fail"] > here["success"]
                    or (here["success"] == 0 and elsewhere_success))
            results.append(view)
        return {"results": results, "truncated": truncated,
                "considered": len(scored), "returned": len(results)}

    # ------------------------------------------------------------------
    # audit
    # ------------------------------------------------------------------
    def audit(self) -> dict[str, Any]:
        expired = [r["id"] for r in self._records.values() if self._is_expired(r)]
        return {
            "chain_ok": self._chain_ok,
            "events": self._seq,
            "active_records": len([r for r in self._records.values()
                                    if r.get("status") == "active"]),
            "superseded_records": len([r for r in self._records.values()
                                        if r.get("status") == "superseded"]),
            "expired_record_ids": expired,
            "tombstones": list(self._tombstones.values()),
            "anchored_evidence": len(self._anchors),
        }
