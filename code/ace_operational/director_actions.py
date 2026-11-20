"""Tutup gap hanya ketika bukti usulan dapat diverifikasi oleh pemanggil."""

from collections.abc import Mapping
from typing import Protocol


class GapStore(Protocol):
    def verify_ref(self, ref: str) -> bool: ...
    def set_gap_status(self, gap_id: str, status: str) -> None: ...


class CloseGap:
    """Aksi dan undo untuk satu gap yang telah ditautkan ke bukti."""

    def __init__(self, store: GapStore):
        self.store = store

    def execute(self, task: Mapping) -> dict:
        checkpoint = task["checkpoint"]
        gap_id, refs = checkpoint.get("gap_id"), checkpoint.get("evidence_refs")
        if not isinstance(gap_id, str) or not gap_id.strip():
            raise ValueError("gap_id wajib diisi.")
        if not isinstance(refs, list) or not refs or not all(
            isinstance(ref, str) and ref.strip() for ref in refs
        ):
            raise ValueError("evidence_refs wajib memuat bukti.")
        for ref in dict.fromkeys(refs):
            if self.store.verify_ref(ref) is not True:
                raise ValueError("Bukti penutupan gap gagal diverifikasi.")
        self.store.set_gap_status(gap_id, "RESOLVED")
        return {"gap_id": gap_id, "status": "OPEN"}

    def undo(self, payload: Mapping) -> None:
        gap_id = payload.get("gap_id")
        if not isinstance(gap_id, str) or not gap_id.strip() or payload.get("status") != "OPEN":
            raise ValueError("Payload undo close_gap tidak sah.")
        self.store.set_gap_status(gap_id, "OPEN")
