"""Pustaka checkpoint state langkah berantai hash dengan verifikasi ketat (AG74).

Menulis, memverifikasi, dan memuat state antar langkah secara deterministik
menggunakan rantai hash SHA-256 kanonis serta urutan ``seq`` ketat (``1, 2, ...``).
Setiap perubahan 1 byte, ketidakcocokan ``prev``/``hash``, maupun lompatan
``seq`` akan ditolak oleh pemuat sebelum state dikembalikan. Tanpa impor engine.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "ace.step-checkpoint.v1"
GENESIS_PREV = "GENESIS"


class StepCheckpointError(ValueError):
    """Dilempar bila berkas checkpoint rusak, hash tak cocok, atau urutannya melompat."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_checkpoint_hash(
    *,
    seq: int,
    prev: str,
    step_id: str,
    state: Any,
) -> str:
    """Hitung SHA-256 kanonis atas seq, prev, step_id, dan payload state."""
    payload = _canonical(
        {
            "seq": seq,
            "prev": prev,
            "step_id": step_id,
            "state": state,
        }
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify_and_load_checkpoints(path: Path) -> list[dict[str, Any]]:
    """Verifikasi seluruh rantai checkpoint dari awal dan kembalikan daftar entri sah."""
    target = Path(path)
    if not target.exists():
        return []
    raw_lines = target.read_text(encoding="utf-8").splitlines()

    entries: list[dict[str, Any]] = []
    expected_seq = 1
    expected_prev = GENESIS_PREV

    for line_no, raw_line in enumerate(raw_lines, 1):
        stripped = raw_line.strip()
        if not stripped:
            raise StepCheckpointError(f"Baris kosong tak terduga pada checkpoint baris {line_no}.")
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise StepCheckpointError(
                f"JSON checkpoint rusak pada baris {line_no}: {exc}"
            ) from exc
        if not isinstance(obj, dict):
            raise StepCheckpointError(f"Checkpoint baris {line_no} wajib berupa objek JSON.")

        seq = obj.get("seq")
        prev = obj.get("prev")
        step_id = obj.get("step_id")
        state = obj.get("state")
        digest = obj.get("hash")

        if type(seq) is not int or seq != expected_seq:
            raise StepCheckpointError(
                f"Urutan checkpoint melompat/tidak sah pada baris {line_no}: "
                f"harap {expected_seq}, dapat {seq!r}."
            )
        if not isinstance(prev, str) or prev != expected_prev:
            raise StepCheckpointError(
                f"Rantai prev checkpoint putus pada seq {seq}: "
                f"harap {expected_prev!r}, dapat {prev!r}."
            )
        if not isinstance(step_id, str) or not step_id.strip():
            raise StepCheckpointError(f"Checkpoint seq {seq} kekurangan step_id tak-kosong.")
        if not isinstance(digest, str) or not digest:
            raise StepCheckpointError(f"Checkpoint seq {seq} kehilangan hash.")

        expected_hash = compute_checkpoint_hash(
            seq=seq, prev=prev, step_id=step_id, state=state
        )
        if digest != expected_hash:
            raise StepCheckpointError(
                f"Hash checkpoint seq {seq} tidak cocok (kemungkinan modifikasi data)."
            )

        entries.append(obj)
        expected_seq += 1
        expected_prev = digest

    return entries


def save_step_checkpoint(
    path: Path,
    *,
    step_id: str,
    state: Mapping[str, Any],
) -> dict[str, Any]:
    """Verifikasi rantai existing lalu tambahkan checkpoint langkah berikutnya secara atomik."""
    if not isinstance(step_id, str) or not step_id.strip():
        raise ValueError("step_id wajib berupa string tak-kosong.")
    if not isinstance(state, Mapping):
        raise ValueError("state wajib berupa mapping JSON-serializable.")

    target = Path(path)
    existing = verify_and_load_checkpoints(target)
    seq = len(existing) + 1
    prev = existing[-1]["hash"] if existing else GENESIS_PREV
    clean_state = json.loads(_canonical(dict(state)))
    sid = step_id.strip()
    digest = compute_checkpoint_hash(seq=seq, prev=prev, step_id=sid, state=clean_state)

    new_entry = {
        "schema": SCHEMA,
        "seq": seq,
        "prev": prev,
        "step_id": sid,
        "state": clean_state,
        "hash": digest,
    }
    all_entries = existing + [new_entry]

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.parent / f".{target.name}.tmp"
    with tmp.open("w", encoding="utf-8") as fh:
        for item in all_entries:
            fh.write(_canonical(item) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, target)
    return new_entry


def load_latest_checkpoint(path: Path) -> dict[str, Any] | None:
    """Verifikasi seluruh rantai lalu kembalikan entri checkpoint terakhir (atau None jika belum ada)."""
    entries = verify_and_load_checkpoints(path)
    return entries[-1] if entries else None
