"""Pembangun model-diri berbasis sumber kustodi terverifikasi (AG91).

Setiap entri model-diri hanya boleh berasal dari tiga sumber kustodi sah:
1. ``receipt`` — log receipt eksekusi (JSONL).
2. ``memory_chain`` — rantai ingatan kognitif (JSONL berurut ``seq``/``hash``).
3. ``decision_ledger`` — buku besar keputusan (JSON / JSONL).

Semua klaim yang tidak memiliki penunjuk sumber kustodi lengkap
(``source_kind``, ``source_ref``, ``record_id``) ditolak dengan
``SelfModelValidationError``. Modul ini murni pustaka tanpa mengimpor engine.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA = "ace.self-model.v1"
VALID_SOURCE_KINDS = frozenset({"receipt", "memory_chain", "decision_ledger"})


class SelfModelValidationError(ValueError):
    """Galat ketika entri model-diri tidak memiliki penunjuk kustodi yang sah."""


@dataclass(frozen=True)
class CustodyPointer:
    source_kind: str
    source_ref: str
    record_id: str
    record_hash: str | None = None

    def validate(self) -> None:
        if self.source_kind not in VALID_SOURCE_KINDS:
            raise SelfModelValidationError(
                f"source_kind tidak sah: {self.source_kind!r}; wajib salah satu dari {sorted(VALID_SOURCE_KINDS)}."
            )
        if not isinstance(self.source_ref, str) or not self.source_ref.strip():
            raise SelfModelValidationError("custody.source_ref wajib berupa string tidak kosong.")
        if not isinstance(self.record_id, str) or not self.record_id.strip():
            raise SelfModelValidationError("custody.record_id wajib berupa string tidak kosong.")


@dataclass(frozen=True)
class SelfModelEntry:
    entry_id: str
    category: str
    claim: str
    value: Any
    custody: CustodyPointer
    observed_at: str | None = None

    def validate(self) -> None:
        if not isinstance(self.entry_id, str) or not self.entry_id.strip():
            raise SelfModelValidationError("entry_id wajib tidak kosong.")
        if not isinstance(self.category, str) or not self.category.strip():
            raise SelfModelValidationError("category wajib tidak kosong.")
        if not isinstance(self.claim, str) or not self.claim.strip():
            raise SelfModelValidationError("claim wajib tidak kosong.")
        if not isinstance(self.custody, CustodyPointer):
            raise SelfModelValidationError("Entri model-diri wajib memiliki CustodyPointer sah.")
        self.custody.validate()

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "category": self.category,
            "claim": self.claim,
            "value": self.value,
            "custody": asdict(self.custody),
            "observed_at": self.observed_at,
        }


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        parsed = json.loads(line)
        if not isinstance(parsed, dict):
            raise SelfModelValidationError(f"Baris {lineno} di {path} bukan objek JSON.")
        records.append(parsed)
    return records


def _coerce_custody(raw: Any) -> CustodyPointer:
    if isinstance(raw, CustodyPointer):
        raw.validate()
        return raw
    if isinstance(raw, Mapping):
        pointer = CustodyPointer(
            source_kind=str(raw.get("source_kind", "")),
            source_ref=str(raw.get("source_ref", "")),
            record_id=str(raw.get("record_id", "")),
            record_hash=str(raw["record_hash"]) if raw.get("record_hash") is not None else None,
        )
        pointer.validate()
        return pointer
    raise SelfModelValidationError("Penunjuk sumber kustodi tidak ada atau tidak berbentuk objek.")


def validate_self_model_payload(payload: Mapping[str, Any]) -> None:
    """Validasi dokumen model-diri: setiap entri wajib mempunyai kustodi lengkap."""
    if payload.get("schema") != SCHEMA:
        raise SelfModelValidationError(f"Schema model-diri tidak dikenal: {payload.get('schema')!r}.")
    entries = payload.get("entries")
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        raise SelfModelValidationError("entries wajib berupa list.")
    for idx, row in enumerate(entries):
        if not isinstance(row, Mapping):
            raise SelfModelValidationError(f"Entri ke-{idx} bukan objek.")
        if not str(row.get("claim", "")).strip():
            raise SelfModelValidationError(f"Entri ke-{idx} tidak memiliki claim.")
        _coerce_custody(row.get("custody"))


class SelfModelBuilder:
    """Pembangun model-diri yang menegakkan asal-usul kustodi pada setiap klaim."""

    def __init__(self) -> None:
        self._entries: list[SelfModelEntry] = []

    def add_claim(
        self,
        *,
        entry_id: str,
        category: str,
        claim: str,
        value: Any,
        custody: CustodyPointer | Mapping[str, Any] | None,
        observed_at: str | None = None,
    ) -> SelfModelEntry:
        """Tambahkan klaim ke model-diri; klaim tanpa kustodi sah langsung ditolak."""
        pointer = _coerce_custody(custody)
        entry = SelfModelEntry(
            entry_id=entry_id,
            category=category,
            claim=claim,
            value=value,
            custody=pointer,
            observed_at=observed_at,
        )
        entry.validate()
        self._entries.append(entry)
        return entry

    def ingest_receipts_jsonl(self, path: str | Path, *, source_ref: str | None = None) -> int:
        p = Path(path)
        ref = source_ref or str(p)
        count = 0
        for idx, row in enumerate(_iter_jsonl(p)):
            rid = str(row.get("receipt_id") or row.get("id") or f"line:{idx + 1}")
            action = str(row.get("action") or row.get("status") or "execution_receipt")
            self.add_claim(
                entry_id=f"receipt:{rid}",
                category="execution_history",
                claim=f"Eksekusi {action}",
                value={
                    "status": row.get("status"),
                    "class": row.get("class"),
                    "action": row.get("action"),
                },
                custody=CustodyPointer(
                    source_kind="receipt",
                    source_ref=ref,
                    record_id=rid,
                    record_hash=str(row["hash"]) if row.get("hash") else None,
                ),
                observed_at=str(row["timestamp"]) if row.get("timestamp") else None,
            )
            count += 1
        return count

    def ingest_memory_chain_jsonl(self, path: str | Path, *, source_ref: str | None = None) -> int:
        p = Path(path)
        ref = source_ref or str(p)
        count = 0
        for row in _iter_jsonl(p):
            seq = row.get("seq")
            event = row.get("event") if isinstance(row.get("event"), Mapping) else {}
            rid = f"seq:{seq}" if seq is not None else str(row.get("id") or "")
            if not rid:
                raise SelfModelValidationError("Entri memory chain tidak memiliki seq atau id.")
            kind = str(event.get("kind") or "memory_event")
            topic = str(event.get("topic") or event.get("id") or rid)
            self.add_claim(
                entry_id=f"memory:{rid}",
                category="cognitive_memory",
                claim=f"Memori {kind} ({topic})",
                value=dict(event),
                custody=CustodyPointer(
                    source_kind="memory_chain",
                    source_ref=ref,
                    record_id=rid,
                    record_hash=str(row["hash"]) if row.get("hash") else None,
                ),
                observed_at=str(event["recorded_at"]) if event.get("recorded_at") else None,
            )
            count += 1
        return count

    def ingest_decision_ledger(self, path: str | Path, *, source_ref: str | None = None) -> int:
        p = Path(path)
        ref = source_ref or str(p)
        raw_text = p.read_text(encoding="utf-8").strip()
        if not raw_text:
            return 0
        if p.suffix == ".jsonl":
            rows: Iterable[Mapping[str, Any]] = _iter_jsonl(p)
        else:
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict) and isinstance(parsed.get("decisions"), list):
                rows = parsed["decisions"]
            elif isinstance(parsed, list):
                rows = parsed
            else:
                raise SelfModelValidationError(f"Format decision ledger tidak dikenal di {p}.")

        count = 0
        for row in rows:
            did = str(row.get("decision_id") or row.get("id") or "")
            if not did:
                raise SelfModelValidationError("Entri decision ledger tidak memiliki decision_id.")
            decision_text = str(row.get("decision") or row.get("choice") or did)
            self.add_claim(
                entry_id=f"decision:{did}",
                category="decisions",
                claim=decision_text,
                value={
                    "reason": row.get("reason"),
                    "outcome": row.get("outcome"),
                },
                custody=CustodyPointer(
                    source_kind="decision_ledger",
                    source_ref=ref,
                    record_id=did,
                    record_hash=str(row["hash"]) if row.get("hash") else None,
                ),
                observed_at=str(row["decided_at"]) if row.get("decided_at") else None,
            )
            count += 1
        return count

    def build(self) -> dict[str, Any]:
        counts: dict[str, int] = {k: 0 for k in sorted(VALID_SOURCE_KINDS)}
        serialized: list[dict[str, Any]] = []
        for entry in self._entries:
            entry.validate()
            counts[entry.custody.source_kind] += 1
            serialized.append(entry.to_dict())
        report = {
            "schema": SCHEMA,
            "entry_count": len(serialized),
            "by_source_kind": counts,
            "entries": serialized,
        }
        validate_self_model_payload(report)
        return report


__all__ = [
    "CustodyPointer",
    "SCHEMA",
    "SelfModelBuilder",
    "SelfModelEntry",
    "SelfModelValidationError",
    "VALID_SOURCE_KINDS",
    "validate_self_model_payload",
]
