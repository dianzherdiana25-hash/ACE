"""Periksa bahwa rehearsal kering hanya meneruskan wakil lipatan."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from ace_operational.director_executor import execute_proposal
from tools.director_fold import fold_proposals
from tools.test_director_fold import triage_fixture


class DirectorFoldRehearsalTests(unittest.TestCase):
    def test_disabled_executor_receipts_are_only_for_representatives(self):
        rows = triage_fixture()
        proposals = {row["task_id"]: row for row in rows}
        plan = fold_proposals(rows)
        self.assertEqual(plan["proposal_count"], 38)
        representatives = [group["representative"] for group in plan["groups"]]
        duplicates = {task_id for group in plan["groups"] for task_id in group["duplicates"]}
        self.assertEqual((len(representatives), len(duplicates)), (11, 27))

        root = Path(self.enterContext(TemporaryDirectory()))
        dry_receipts = root / "rehearsal.jsonl"
        live_receipts = root / "executor.jsonl"
        action = Mock()
        store = {"g0": "open", "g1": "open"}
        initial_store = store.copy()

        def close_in_fixture(_task):
            store["g0"] = "closed"
            return {"gap_id": "g0"}

        action.execute.side_effect = close_in_fixture
        with patch.dict(os.environ, {}, clear=True), dry_receipts.open("w", encoding="utf-8") as output:
            for task_id in representatives:
                task = {"kind": "director_proposal", "task_id": task_id,
                        "checkpoint": {**proposals[task_id], "action": "close_gap"}}
                result = execute_proposal(task, actions={"close_gap": action},
                                          receipt_path=live_receipts, daily_cap=38)
                self.assertEqual(result, {"status": "dry_run", "reason": "disabled"})
                output.write(json.dumps({"task_id": task_id, **result}) + "\n")

        receipts = [json.loads(line) for line in dry_receipts.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(receipts, [
            {"task_id": task_id, "status": "dry_run", "reason": "disabled"} for task_id in representatives
        ])
        self.assertTrue(duplicates.isdisjoint(receipt["task_id"] for receipt in receipts))
        action.execute.assert_not_called()
        self.assertEqual(store, initial_store)
        self.assertFalse(live_receipts.exists())
