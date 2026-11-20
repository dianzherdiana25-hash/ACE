"""Tes langkah eksekusi director EVO 0012 M2 (director_execution).

Store palsu in-memory meniru permukaan OperationalStore yang dipakai
wiring: list_gaps/list_tasks/list_frontier/update_gap/update_task.
Kontrak yang dikunci: flag mati = tidak ada yang disentuh; eksekusi
hanya terjadi untuk proposal satu-gap dengan bukti frontier
KNOWN_AND_TESTED yang tertambat; cap harian executor dihormati.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from ace_operational import director_execution as dx


class FakeStore:
    def __init__(self, gaps, tasks, frontier):
        self.gaps = {g["gap_id"]: dict(g) for g in gaps}
        self.tasks = {t["task_id"]: dict(t) for t in tasks}
        self.frontier = [dict(c) for c in frontier]
        self.task_updates = []

    def list_gaps(self, status=None):
        return [g for g in self.gaps.values()
                if status is None or g["status"] == status]

    def list_tasks(self, limit=50):
        return list(self.tasks.values())[:limit]

    def list_frontier(self):
        return list(self.frontier)

    def update_gap(self, gap_id, *, status=None, linked_learning_task_id=None):
        if status is not None:
            self.gaps[gap_id]["status"] = status
        return self.gaps[gap_id]

    def update_task(self, task_id, **kwargs):
        self.task_updates.append((task_id, kwargs))
        if kwargs.get("status") is not None:
            self.tasks[task_id]["status"] = kwargs["status"]
        if kwargs.get("checkpoint") is not None:
            self.tasks[task_id]["checkpoint"] = kwargs["checkpoint"]
        return self.tasks[task_id]


def _gap(gap_id="gap_1", fingerprint="abcdef0123456789", description_id="skill_x"):
    return {"gap_id": gap_id, "fingerprint": fingerprint,
            "description_id": description_id, "status": "OPEN"}


def _proposal(task_id="task_1", based_on=("gap_1",)):
    return {"task_id": task_id, "kind": "director_proposal",
            "status": "WAITING_FOR_DEPENDENCY",
            "checkpoint": {"stage": "director_review",
                           "proposal": {"based_on": list(based_on),
                                        "title": "t", "rationale": "r"}}}


def _cap(evidence_ref="rcpt-1", status="KNOWN_AND_TESTED",
         capability_id="cap_abcdef0123", name_id="skill_x"):
    return {"capability_id": capability_id, "name_id": name_id,
            "status": status, "evidence_ref": evidence_ref}


class DirectorExecutionStep(unittest.TestCase):
    def setUp(self):
        d = TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.ws = Path(d.name)

    def _run(self, store):
        with mock.patch.dict(os.environ, {"ACE_DIRECTOR_EXEC_A": "1"}):
            return dx.run_execution_step(store, self.ws)

    def test_disabled_without_flag_touches_nothing(self):
        store = FakeStore([_gap()], [_proposal()], [_cap()])
        result = dx.run_execution_step(store, self.ws, environ={})
        self.assertEqual(result, {"status": "disabled"})
        self.assertEqual(store.gaps["gap_1"]["status"], "OPEN")
        self.assertEqual(store.task_updates, [])
        self.assertFalse((self.ws / dx.RECEIPT_NAME).exists())

    def test_executes_single_gap_proposal_with_verified_evidence(self):
        store = FakeStore([_gap()], [_proposal()], [_cap()])
        result = self._run(store)
        self.assertEqual(result["executed"], 1)
        self.assertEqual(store.gaps["gap_1"]["status"], "RESOLVED")
        self.assertEqual(store.tasks["task_1"]["status"], "COMPLETED")
        lines = (self.ws / dx.RECEIPT_NAME).read_text(encoding="utf-8").splitlines()
        records = [json.loads(line) for line in lines]
        self.assertEqual([r["status"] for r in records], ["started", "completed"])
        self.assertEqual(records[-1]["undo"], {"gap_id": "gap_1", "status": "OPEN"})

    def test_no_frontier_evidence_skips(self):
        store = FakeStore([_gap()], [_proposal()], [])
        result = self._run(store)
        self.assertEqual(result["executed"], 0)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(store.gaps["gap_1"]["status"], "OPEN")
        self.assertFalse((self.ws / dx.RECEIPT_NAME).exists())

    def test_untested_capability_is_not_evidence(self):
        store = FakeStore([_gap()], [_proposal()],
                          [_cap(status="IMPLEMENTED_UNVERIFIED")])
        result = self._run(store)
        self.assertEqual(result["executed"], 0)
        self.assertEqual(store.gaps["gap_1"]["status"], "OPEN")

    def test_multi_gap_proposal_skips(self):
        store = FakeStore(
            [_gap(), _gap("gap_2", "1234567890abcdef", "skill_y")],
            [_proposal(based_on=("gap_1", "gap_2"))],
            [_cap()],
        )
        result = self._run(store)
        self.assertEqual(result["executed"], 0)
        self.assertEqual(result["skipped"], 1)

    def test_daily_cap_refuses_fourth_execution(self):
        receipt = self.ws / dx.RECEIPT_NAME
        now = datetime.now(timezone.utc).isoformat()
        lines = []
        for i in range(dx.DAILY_CAP):
            base = {"task_id": f"old_{i}", "action": "close_gap",
                    "evidence_refs": ["rcpt-x"], "at": now}
            lines.append(json.dumps({**base, "status": "started", "undo": None}))
            lines.append(json.dumps({**base, "status": "completed",
                                     "undo": {"gap_id": "g", "status": "OPEN"}}))
        receipt.write_text("\n".join(lines) + "\n", encoding="utf-8")
        store = FakeStore([_gap()], [_proposal()], [_cap()])
        result = self._run(store)
        self.assertEqual(result["considered"], 1)
        self.assertEqual(result["executed"], 0)
        self.assertEqual(result["refused"], 1)
        self.assertEqual(store.gaps["gap_1"]["status"], "OPEN")


if __name__ == "__main__":
    unittest.main()
