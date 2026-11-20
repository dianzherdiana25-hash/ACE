"""Batasi eksekusi proposal lokal dan sisakan jejak bila proses terputus."""

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
from typing import Protocol

try:
    from .director_classes import classify_proposal
except ModuleNotFoundError as exc:
    if exc.name != f"{__package__}.director_classes":
        raise
    classify_proposal = None


class Action(Protocol):
    def execute(self, task: Mapping) -> dict:
        """Jalankan perubahan dan kembalikan payload undo JSON tanpa rahasia."""


Classifier = Callable[[Mapping], Mapping]


def _append(stream, receipt):
    line = json.dumps(receipt, allow_nan=False, separators=(",", ":"))
    stream.write(line + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def _read_receipts(stream):
    started = {}
    pending = set()
    stream.seek(0)
    lines = stream.readlines()
    for index, line in enumerate(lines):
        is_last = index == len(lines) - 1
        if is_last and not line.endswith("\n"):
            pending.add("<torn_receipt>")
            break
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            if is_last:
                pending.add("<torn_receipt>")
                break
            raise
        if not isinstance(record, dict):
            raise ValueError("receipt invalid")
        task_id, timestamp, status = record["task_id"], record["at"], record["status"]
        instant = datetime.fromisoformat(timestamp)
        if instant.tzinfo is None or not isinstance(task_id, str) or not task_id:
            raise ValueError("receipt invalid")
        if status == "started" and task_id not in started:
            started[task_id] = instant.astimezone(timezone.utc).date()
            pending.add(task_id)
        elif status in {"completed", "failed"} and task_id in pending:
            pending.remove(task_id)
        else:
            raise ValueError("receipt sequence invalid")
    return started, pending


def execute_proposal(task: Mapping, *, actions: Mapping[str, Action], receipt_path: Path,
                     daily_cap: int, classifier: Classifier | None = None) -> dict:
    """Eksekusi aksi A dengan lock Linux dan dua baris receipt per percobaan.

    `started` memesan kuota sebelum efek aksi. Receipt terminal menyimpan undo
    atau galat generik. Percobaan tanpa terminal memerlukan rekonsiliasi
    operator. Classifier eksplisit hanya dipakai sampai impor A1 tersedia.
    """
    if os.environ.get("ACE_DIRECTOR_EXEC_A") != "1":
        return {"status": "dry_run", "reason": "disabled"}
    if type(daily_cap) is not int or daily_cap < 0:
        return {"status": "refused", "reason": "invalid_cap"}
    classify = classify_proposal or classifier
    try:
        if classify is None or classify(task).get("class") != "A":
            return {"status": "refused", "reason": "not_class_a"}
        task_id = task["task_id"]
        checkpoint = task["checkpoint"]
        action_id = checkpoint["action"]
        evidence = checkpoint["evidence_refs"]
        action = actions[action_id]
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("missing task id")
        if not isinstance(evidence, list) or not evidence or not all(
            isinstance(ref, str) and ref.strip() for ref in evidence
        ):
            raise ValueError("missing evidence")
    except Exception:
        return {"status": "refused", "reason": "invalid_task_or_action"}

    execution_started = False
    try:
        with os.fdopen(os.open(receipt_path, os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW,
                               0o600), "a+", encoding="utf-8") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            started, pending = _read_receipts(stream)
            now = datetime.now(timezone.utc)
            if pending:
                return {"status": "refused", "reason": "pending_receipt"}
            if task_id in started:
                return {"status": "refused", "reason": "duplicate_task"}
            if sum(day == now.date() for day in started.values()) >= daily_cap:
                return {"status": "refused", "reason": "daily_cap"}
            receipt = {"task_id": task_id, "action": action_id, "evidence_refs": list(evidence)}
            _append(stream, {**receipt, "status": "started", "at": now.isoformat(), "undo": None})
            execution_started = True
            try:
                undo = action.execute(task)
            except Exception:
                terminal = {**receipt, "status": "failed", "undo": None,
                            "reason": "action_failed", "effects": "unknown"}
            else:
                if not isinstance(undo, dict):
                    raise ValueError("invalid undo")
                terminal = {**receipt, "status": "completed", "undo": undo}
            terminal["at"] = datetime.now(timezone.utc).isoformat()
            _append(stream, terminal)
            return terminal
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        if execution_started:
            return {"status": "uncertain", "reason": "terminal_receipt_failed"}
        return {"status": "refused", "reason": "receipt_unavailable"}
