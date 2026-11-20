"""Pembangun konteks receipt eksekusi usulan per organ untuk director (AG69).

Membaca log receipt JSONL dengan semantik ekor robek AG11 dan menggabungkannya
dengan metadata usulan dari store (lewat ``Protocol``) untuk membentuk
ringkasan hasil per organ (``completed`` / ``failed`` / ``undo`` + alasan pagar)
yang siap disisipkan ke konteks usulan berikutnya. Tanpa impor engine.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence


SCHEMA = "ace.director-receipt-context.v1"
TORN_SENTINEL = "<torn_receipt>"


class ProposalOriginLookup(Protocol):
    def get_proposal_meta(self, task_id: str) -> Mapping[str, Any] | None: ...


def _read_receipts_ag11(receipts_path: Path) -> tuple[list[dict[str, Any]], bool, list[str]]:
    with Path(receipts_path).open("r", encoding="utf-8") as stream:
        lines = stream.readlines()

    events: list[dict[str, Any]] = []
    started: set[str] = set()
    pending: set[str] = set()
    torn_tail = False

    for idx, raw_line in enumerate(lines):
        is_last = idx == len(lines) - 1
        if is_last and not raw_line.endswith("\n"):
            torn_tail = True
            pending.add(TORN_SENTINEL)
            break
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError:
            if is_last:
                torn_tail = True
                pending.add(TORN_SENTINEL)
                break
            raise ValueError(f"Baris receipt tengah ke-{idx + 1} bukan JSON sah.")

        if not isinstance(record, dict):
            raise ValueError(f"Baris receipt ke-{idx + 1} wajib berupa objek JSON.")

        task_id = record.get("task_id")
        at = record.get("at")
        status = record.get("status")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError(f"Baris receipt ke-{idx + 1} memiliki task_id tidak sah.")
        if not isinstance(at, str) or not at.strip():
            raise ValueError(f"Baris receipt ke-{idx + 1} kekurangan timestamp 'at'.")
        instant = datetime.fromisoformat(at)
        if instant.tzinfo is None:
            raise ValueError(f"Timestamp 'at' tanpa offset zona waktu pada baris {idx + 1}.")

        if status == "started":
            if task_id in started:
                raise ValueError(f"Event 'started' ganda untuk task_id {task_id!r}.")
            started.add(task_id)
            pending.add(task_id)
        elif status in {"completed", "failed"}:
            if task_id not in pending:
                raise ValueError(f"Urutan receipt tidak sah untuk task_id {task_id!r}: {status!r}.")
            pending.remove(task_id)
        elif status in {"undone", "blocked"}:
            # Event purna-eksekusi (undo) atau blokir pagar tetap diterima dengan task_id sah.
            pending.discard(task_id)
        else:
            raise ValueError(f"Status receipt tidak dikenal: {status!r}.")
        events.append(record)

    return events, torn_tail, sorted(pending)


def build_receipt_context(
    receipts_path: Path,
    store: ProposalOriginLookup | Mapping[str, Mapping[str, Any]] | None = None,
    *,
    max_recent: int = 10,
) -> dict[str, Any]:
    """Bangun ringkasan terstruktur hasil eksekusi per organ siap sisip konteks."""
    events, torn_tail, pending_tasks = _read_receipts_ag11(Path(receipts_path))

    def _meta(tid: str) -> Mapping[str, Any]:
        if store is None:
            return {}
        if isinstance(store, Mapping):
            val = store.get(tid)
            return val if isinstance(val, Mapping) else {}
        val = store.get_proposal_meta(tid)
        return val if isinstance(val, Mapping) else {}

    organ_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "completed": 0,
            "failed": 0,
            "undo": 0,
            "gate_reasons": Counter(),
        }
    )
    task_organ: dict[str, str] = {}
    recent_notes: list[dict[str, Any]] = []

    for rec in events:
        tid = str(rec["task_id"])
        meta = _meta(tid)
        organ = str(
            rec.get("organ")
            or rec.get("provider")
            or meta.get("organ")
            or task_organ.get(tid)
            or "unknown"
        ).strip() or "unknown"
        task_organ[tid] = organ

        status = str(rec["status"])
        bucket = organ_stats[organ]
        has_undo = bool(rec.get("undo_executed")) or status == "undone"
        gate_reason = rec.get("gate_reason") or rec.get("reason") or meta.get("gate_reason")

        if status == "completed":
            bucket["completed"] += 1
        elif status == "failed":
            bucket["failed"] += 1
        if has_undo:
            bucket["undo"] += 1
        if isinstance(gate_reason, str) and gate_reason.strip():
            bucket["gate_reasons"][gate_reason.strip()] += 1

        if status != "started":
            note: dict[str, Any] = {
                "task_id": tid,
                "organ": organ,
                "status": "undo" if status == "undone" else status,
                "at": rec["at"],
            }
            if has_undo and status != "undone":
                note["undo"] = True
            if isinstance(gate_reason, str) and gate_reason.strip():
                note["gate_reason"] = gate_reason.strip()
            recent_notes.append(note)

    by_organ: dict[str, dict[str, Any]] = {}
    for organ in sorted(organ_stats):
        st = organ_stats[organ]
        reasons_sorted = dict(sorted(st["gate_reasons"].items()))
        by_organ[organ] = {
            "completed": st["completed"],
            "failed": st["failed"],
            "undo": st["undo"],
            "gate_reasons": reasons_sorted,
        }

    if max_recent > 0:
        recent_slice = recent_notes[-max_recent:]
    else:
        recent_slice = []

    context_obj = {
        "schema": SCHEMA,
        "torn_tail": torn_tail,
        "pending_tasks": pending_tasks,
        "by_organ": by_organ,
        "recent_outcomes": recent_slice,
    }
    context_obj["context_block"] = render_context_block(context_obj)
    return context_obj


def render_context_block(context_doc: Mapping[str, Any]) -> str:
    """Format ringkasan receipt per organ menjadi blok teks ringkas siap sisip prompt."""
    lines = ["[RINGKASAN RECEIPT DIRECTOR PER ORGAN]"]
    if context_doc.get("torn_tail"):
        lines.append("- PERINGATAN: baris receipt terakhir robek (tail_pending=<torn_receipt>).")
    by_organ = context_doc.get("by_organ") or {}
    if not by_organ:
        lines.append("- Belum ada riwayat eksekusi organ.")
    for organ in sorted(by_organ):
        st = by_organ[organ]
        reason_text = ", ".join(f"{k}={v}" for k, v in st.get("gate_reasons", {}).items()) or "-"
        lines.append(
            f"- {organ}: completed={st['completed']}, failed={st['failed']}, "
            f"undo={st['undo']}, alasan_pagar=[{reason_text}]"
        )
    return "\n".join(lines)
