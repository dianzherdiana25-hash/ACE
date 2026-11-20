"""Kunci pemulihan receipt dan kontrak klasifikasi, eksekusi, serta undo."""
import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from ace_operational.director_executor import execute_proposal


DEPS_AVAILABLE = all(importlib.util.find_spec(f"ace_operational.{name}") is not None
                     for name in ("director_classes", "director_actions"))


def proposal(task_id):
    return {"task_id": task_id, "kind": "director_proposal", "checkpoint": {
        "action": "close_gap", "gap_id": "gap-1", "based_on": ["gap-1"],
        "evidence_refs": ["receipt-1"], "reversible": True,
        "touches_money": False, "touches_publication": False, "touches_external": False,
    }}


class FixtureStore:
    def __init__(self):
        self.status = "OPEN"

    def verify_ref(self, ref):
        return ref == "receipt-1"

    def set_gap_status(self, gap_id, status):
        if gap_id != "gap-1":
            raise ValueError("unexpected gap")
        self.status = status


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(self.enterContext(TemporaryDirectory())) / "receipts.jsonl"
        self.enterContext(patch.dict(os.environ, {"ACE_DIRECTOR_EXEC_A": "1"}))

    def test_previous_process_died_after_started(self):
        started = {"task_id": "interrupted", "action": "close_gap", "evidence_refs": ["receipt-1"],
                   "status": "started", "at": "2026-11-19T10:00:00+00:00", "undo": None}
        raw = (json.dumps(started) + "\n").encode()
        self.path.write_bytes(raw)
        last_change = self.path.stat().st_mtime_ns
        action = Mock()
        result = execute_proposal(proposal("new"), actions={"close_gap": action},
                                  receipt_path=self.path, daily_cap=3,
                                  classifier=lambda task: {"class": "A"})
        self.assertEqual(result, {"status": "refused", "reason": "pending_receipt"})
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertEqual(self.path.stat().st_mtime_ns, last_change)
        action.execute.assert_not_called()

    @unittest.skipUnless(DEPS_AVAILABLE, "integrasi memerlukan modul #444 dan #446")
    def test_real_classifier_executor_and_action_with_receipt_undo(self):
        from ace_operational.director_actions import CloseGap

        store = FixtureStore()
        action = CloseGap(store)
        task = proposal("same-task")
        options = {"actions": {"close_gap": action}, "receipt_path": self.path, "daily_cap": 3}
        result = execute_proposal(task, **options)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(store.status, "RESOLVED")
        before = self.path.read_bytes()
        terminal = json.loads(before.splitlines()[-1])
        self.assertEqual(terminal, result)
        action.undo(terminal["undo"])
        self.assertEqual(store.status, "OPEN")
        self.assertEqual(execute_proposal(task, **options),
                         {"status": "refused", "reason": "duplicate_task"})
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(store.status, "OPEN")


if __name__ == "__main__":
    unittest.main()
