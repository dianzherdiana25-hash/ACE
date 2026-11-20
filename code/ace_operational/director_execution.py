"""Langkah eksekusi director EVO 0012 M2 — menyapu proposal WAITING ke executor.

Env-gated ganda: langkah ini hanya berjalan bila ACE_DIRECTOR_EXEC_A == "1"
(kill-switch), dan director_executor memeriksa flag yang sama sebelum
mengeksekusi. Kandidat dibangun dari FAKTA STORE, bukan klaim otak:

- proposal director berbasis tepat satu gap yang masih OPEN;
- bukti penutupan = capability frontier berstatus KNOWN_AND_TESTED dengan
  evidence_ref tak-kosong yang cocok dengan gap itu (capability_id dari
  fingerprint gap, atau name_id == description_id gap);
- bukti wajib lolos aturan anchor EVO 0013 (check_anchors == anchored)
  lewat adapter yang sama yang memverifikasi ref untuk CloseGap;
- fakta batas untuk classifier ditetapkan wiring untuk aksi close_gap:
  reversible (punya undo), internal, tidak menyentuh uang/publikasi/
  pihak luar.

Proposal yang tidak memenuhi semua itu tidak disentuh: tetap WAITING
(Kelas B secara perilaku). Cap harian diteruskan ke executor.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .director_actions import CloseGap
from .director_executor import execute_proposal
from .memory_anchor import check_anchors

DAILY_CAP = 3
MAX_PER_CYCLE = 10
RECEIPT_NAME = "director_exec_receipts.jsonl"


class GapStoreAdapter:
    """OperationalStore -> protokol GapStore (director_actions) +
    VerifiedReferences (memory_anchor)."""

    def __init__(self, store):
        self._store = store

    def verify_ref(self, ref: str) -> bool:
        """Ref terverifikasi = evidence_ref milik capability KNOWN_AND_TESTED."""
        if not isinstance(ref, str) or not ref.strip():
            return False
        for cap in self._store.list_frontier():
            if cap.get("status") == "KNOWN_AND_TESTED" and cap.get("evidence_ref") == ref:
                return True
        return False

    def set_gap_status(self, gap_id: str, status: str) -> None:
        self._store.update_gap(gap_id, status=status)


def _verified_evidence(store, gap) -> str | None:
    """evidence_ref frontier teruji yang cocok dengan gap ini, bila ada."""
    cap_id = f"cap_{str(gap.get('fingerprint') or '')[:10]}"
    for cap in store.list_frontier():
        if cap.get("status") != "KNOWN_AND_TESTED":
            continue
        ref = cap.get("evidence_ref")
        if not isinstance(ref, str) or not ref.strip():
            continue
        if cap.get("capability_id") == cap_id or cap.get("name_id") == gap.get("description_id"):
            return ref
    return None


def _receipted_task_ids(receipt_path: Path) -> set:
    """task_id yang sudah pernah dicoba executor (receipt bersifat final
    per tugas — executor menolak percobaan ulang sebagai duplicate)."""
    ids = set()
    if not receipt_path.exists():
        return ids
    for line in receipt_path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict) and isinstance(record.get("task_id"), str):
            ids.add(record["task_id"])
    return ids


def run_execution_step(store, workspace, *, environ=None) -> dict:
    """Satu sapuan eksekusi Kelas A atas proposal director WAITING."""
    env = os.environ if environ is None else environ
    if env.get("ACE_DIRECTOR_EXEC_A") != "1":
        return {"status": "disabled"}
    adapter = GapStoreAdapter(store)
    receipt_path = Path(workspace) / RECEIPT_NAME
    already = _receipted_task_ids(receipt_path)
    summary = {"status": "ran", "considered": 0, "executed": 0,
               "refused": 0, "skipped": 0}
    open_gaps = {g["gap_id"]: g for g in store.list_gaps(status="OPEN")}
    for task in store.list_tasks(limit=200):
        if summary["considered"] >= MAX_PER_CYCLE:
            break
        if task.get("kind") != "director_proposal":
            continue
        if task.get("status") != "WAITING_FOR_DEPENDENCY":
            continue
        if task.get("task_id") in already:
            summary["skipped"] += 1
            continue
        checkpoint = task.get("checkpoint") or {}
        proposal = checkpoint.get("proposal") or {}
        based_on = [r for r in (checkpoint.get("based_on")
                                or proposal.get("based_on") or [])
                    if isinstance(r, str)]
        gap_refs = [r for r in based_on if r in open_gaps]
        if len(gap_refs) != 1:
            summary["skipped"] += 1
            continue
        gap = open_gaps[gap_refs[0]]
        evidence_ref = _verified_evidence(store, gap)
        if evidence_ref is None:
            summary["skipped"] += 1
            continue
        # Aturan anchor EVO 0013: bukti wajib tertambat & dapat diambil
        # kembali; yang dangling tidak pernah menjadi Kelas A.
        if check_anchors([evidence_ref], adapter)["status"] != "anchored":
            summary["skipped"] += 1
            continue
        summary["considered"] += 1
        exec_task = {
            "task_id": task["task_id"],
            "kind": "director_proposal",
            "checkpoint": {
                "action": "close_gap",
                "gap_id": gap["gap_id"],
                "based_on": [gap["gap_id"]],
                "evidence_refs": [evidence_ref],
                "reversible": True,
                "touches_money": False,
                "touches_publication": False,
                "touches_external": False,
            },
        }
        result = execute_proposal(
            exec_task,
            actions={"close_gap": CloseGap(adapter)},
            receipt_path=receipt_path,
            daily_cap=DAILY_CAP,
        )
        if result.get("status") == "completed":
            summary["executed"] += 1
            store.update_task(
                task["task_id"],
                status="COMPLETED",
                checkpoint={**checkpoint, "director_execution": {
                    "action": "close_gap",
                    "gap_id": gap["gap_id"],
                    "evidence_refs": [evidence_ref],
                    "receipt_status": "completed",
                }},
                next_action="director_execution_completed",
            )
        else:
            summary["refused"] += 1
    return summary
