"""Pastikan hanya percobaan A berkuota yang mencapai aksi."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from ace_operational import director_executor


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(self.enterContext(tempfile.TemporaryDirectory())) / "receipts.jsonl"
        self.action = Mock()
        self.action.execute.return_value = {"gap_id": "gap1", "status": "OPEN"}
        self.task = {"task_id": "t1", "kind": "director_proposal",
                     "checkpoint": {"action": "close_gap", "evidence_refs": ["r1"]}}
        self.classifier = Mock(return_value={"class": "A"})
        self.enterContext(patch.object(director_executor, "classify_proposal", self.classifier))
        self.enterContext(patch.dict(os.environ, {"ACE_DIRECTOR_EXEC_A": "1"}))

    def execute(self):
        return director_executor.execute_proposal(
            self.task, actions={"close_gap": self.action}, receipt_path=self.path, daily_cap=1,
        )

    def rows(self):
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def test_disabled_has_no_side_effect(self):
        with patch.dict(os.environ, {"ACE_DIRECTOR_EXEC_A": "0"}):
            self.assertEqual(self.execute()["status"], "dry_run")
        self.assertFalse(self.path.exists())
        self.action.execute.assert_not_called()

    def test_non_a_refused(self):
        self.classifier.return_value = {"class": "C"}
        self.assertEqual(self.execute()["reason"], "not_class_a")
        self.assertFalse(self.path.exists())

    def test_complete_receipt_then_cap(self):
        result = self.execute()
        self.assertEqual(result["undo"], {"gap_id": "gap1", "status": "OPEN"})
        self.assertEqual(result, self.rows()[-1])
        for row in self.rows():
            self.assertEqual((row["task_id"], row["action"], row["evidence_refs"]),
                             ("t1", "close_gap", ["r1"]))
            self.assertTrue(row["at"].endswith("+00:00"))
        self.task["task_id"] = "t2"
        self.assertEqual(self.execute()["reason"], "daily_cap")
        self.action.execute.assert_called_once()

    def test_action_failure_is_recorded_without_claiming_effects(self):
        self.action.execute.side_effect = RuntimeError("private fixture")
        result = self.execute()
        self.assertEqual((result["status"], result["effects"]), ("failed", "unknown"))
        self.assertEqual([row["status"] for row in self.rows()], ["started", "failed"])
        self.assertNotIn("private fixture", self.path.read_text())

    def test_invalid_undo_stops_further_actions(self):
        self.action.execute.return_value = {"bad": object()}
        self.assertEqual(self.execute()["status"], "uncertain")
        self.assertEqual(self.execute()["reason"], "pending_receipt")
        self.action.execute.assert_called_once()

    def test_absent_classifier_fail_closed(self):
        with patch.object(director_executor, "classify_proposal", None):
            self.assertEqual(self.execute()["reason"], "not_class_a")
        self.action.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
