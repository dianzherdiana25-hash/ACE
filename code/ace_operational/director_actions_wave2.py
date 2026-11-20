"""Aksi director gelombang 2 yang berdiri sendiri dan dapat di-undo (AG44).

Menyediakan ``SchedulePractice`` dan ``ArchiveProposal`` mengikuti protokol
``Action`` di ``director_actions.py`` / ``director_executor.py``. Hanya bergantung
pada ``Protocol`` store tanpa mengimpor engine agar belum terhubung langsung
ke loop eksekusi live.
"""

from __future__ import annotations

from typing import Mapping, Protocol


class PracticeScheduleStore(Protocol):
    def verify_ref(self, ref: str) -> bool: ...
    def get_practice_status(self, practice_id: str) -> str | None: ...
    def set_practice_status(self, practice_id: str, status: str) -> None: ...


class ProposalArchiveStore(Protocol):
    def verify_ref(self, ref: str) -> bool: ...
    def get_proposal_status(self, proposal_id: str) -> str | None: ...
    def set_proposal_status(self, proposal_id: str, status: str) -> None: ...


def _extract_checkpoint(task: Mapping) -> Mapping:
    if not isinstance(task, Mapping):
        raise ValueError("Task harus berupa mapping.")
    checkpoint = task.get("checkpoint")
    if not isinstance(checkpoint, Mapping):
        raise ValueError("checkpoint wajib berupa mapping.")
    return checkpoint


def _validate_evidence_refs(checkpoint: Mapping, store: object) -> list[str]:
    refs = checkpoint.get("evidence_refs")
    if not isinstance(refs, list) or not refs or not all(
        isinstance(ref, str) and ref.strip() for ref in refs
    ):
        raise ValueError("evidence_refs wajib memuat daftar ref tak-kosong.")
    verified: list[str] = []
    for ref in dict.fromkeys(r.strip() for r in refs):
        if store.verify_ref(ref) is not True:  # type: ignore[attr-defined]
            raise ValueError(f"Bukti ref gagal diverifikasi: {ref!r}")
        verified.append(ref)
    return verified


class SchedulePractice:
    """Jadwalkan tugas praktik secara terverifikasi dan pulihkan status asal saat undo."""

    TARGET_STATUS = "SCHEDULED"

    def __init__(self, store: PracticeScheduleStore):
        self.store = store

    def execute(self, task: Mapping) -> dict:
        checkpoint = _extract_checkpoint(task)
        practice_id = checkpoint.get("practice_id")
        if not isinstance(practice_id, str) or not practice_id.strip():
            raise ValueError("practice_id wajib diisi.")
        pid = practice_id.strip()
        _validate_evidence_refs(checkpoint, self.store)

        previous_status = self.store.get_practice_status(pid)
        if not isinstance(previous_status, str) or not previous_status.strip():
            raise ValueError(f"Status awal practice_id tidak ditemukan: {pid!r}")

        self.store.set_practice_status(pid, self.TARGET_STATUS)
        return {
            "action": "schedule_practice",
            "practice_id": pid,
            "previous_status": previous_status.strip(),
        }

    def undo(self, payload: Mapping) -> None:
        if not isinstance(payload, Mapping):
            raise ValueError("Payload undo schedule_practice harus berupa mapping.")
        if payload.get("action") != "schedule_practice":
            raise ValueError("Payload undo bukan milik schedule_practice.")
        practice_id = payload.get("practice_id")
        previous_status = payload.get("previous_status")
        if (
            not isinstance(practice_id, str)
            or not practice_id.strip()
            or not isinstance(previous_status, str)
            or not previous_status.strip()
        ):
            raise ValueError("Payload undo schedule_practice tidak sah.")
        self.store.set_practice_status(practice_id.strip(), previous_status.strip())


class ArchiveProposal:
    """Arsipkan proposal usang secara terverifikasi dan pulihkan status asal saat undo."""

    TARGET_STATUS = "ARCHIVED"

    def __init__(self, store: ProposalArchiveStore):
        self.store = store

    def execute(self, task: Mapping) -> dict:
        checkpoint = _extract_checkpoint(task)
        proposal_id = checkpoint.get("proposal_id")
        if not isinstance(proposal_id, str) or not proposal_id.strip():
            raise ValueError("proposal_id wajib diisi.")
        prop_id = proposal_id.strip()
        _validate_evidence_refs(checkpoint, self.store)

        previous_status = self.store.get_proposal_status(prop_id)
        if not isinstance(previous_status, str) or not previous_status.strip():
            raise ValueError(f"Status awal proposal_id tidak ditemukan: {prop_id!r}")

        self.store.set_proposal_status(prop_id, self.TARGET_STATUS)
        return {
            "action": "archive_proposal",
            "proposal_id": prop_id,
            "previous_status": previous_status.strip(),
        }

    def undo(self, payload: Mapping) -> None:
        if not isinstance(payload, Mapping):
            raise ValueError("Payload undo archive_proposal harus berupa mapping.")
        if payload.get("action") != "archive_proposal":
            raise ValueError("Payload undo bukan milik archive_proposal.")
        proposal_id = payload.get("proposal_id")
        previous_status = payload.get("previous_status")
        if (
            not isinstance(proposal_id, str)
            or not proposal_id.strip()
            or not isinstance(previous_status, str)
            or not previous_status.strip()
        ):
            raise ValueError("Payload undo archive_proposal tidak sah.")
        self.store.set_proposal_status(proposal_id.strip(), previous_status.strip())
