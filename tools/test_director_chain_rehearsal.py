"""Periksa bahwa lipatan tertambat menjadi satu-satunya masukan rehearsal A."""
from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from ace_operational.director_executor import execute_proposal
from ace_operational.memory_anchor import check_anchors
from tools import director_fold
from tools.test_director_fold import triage_fixture


class DirectorChainRehearsalTests(unittest.TestCase):
    def test_anchored_representatives_alone_make_dry_run_receipts(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        verified_refs = ["g0", "g2", "g5"]
        store_file = root / "fixture-store.json"
        store_file.write_text(json.dumps({"verified_refs": verified_refs}), encoding="utf-8")
        store_baseline = store_file.read_bytes()
        store = Mock()
        store.verify_ref.side_effect = set(json.loads(store_baseline)["verified_refs"]).__contains__
        boundaries = {"evidence_refs": ["fixture"], "touches_money": False,
                      "touches_publication": False, "touches_external": False, "reversible": True}
        rows = {row["task_id"]: {**row, **boundaries} for row in triage_fixture()}
        proposals = root / "proposals.jsonl"
        proposals.write_text("".join(json.dumps(row) + "\n" for row in rows.values()), encoding="utf-8")

        with redirect_stdout(StringIO()) as output:
            self.assertEqual(director_fold.main([
                str(proposals), "--require-anchored", "--store", str(store_file),
            ]), 0)
        plan = json.loads(output.getvalue())
        self.assertEqual((plan["proposal_count"], len(plan["groups"])), (38, 11))
        eligible = [group for group in plan["groups"] if group["initial_class"] == "A"]
        dangling = {group["representative"] for group in plan["groups"]
                    if group.get("class_reasons") == ["unanchored"] and group["initial_class"] == "B"}
        self.assertEqual([group["representative"] for group in eligible], ["largest-0", "g2-0", "g5-0"])
        self.assertEqual(dangling, {"g1-0", "g3-0", "g4-0", "g6-0", "g7-0", "g8-0", "g9-0"})

        action = Mock()
        live_path, rehearsal_path = root / "live.jsonl", root / "rehearsal.jsonl"
        with patch.dict(os.environ, {}, clear=True), rehearsal_path.open("x", encoding="utf-8") as receipt_file:
            for group in eligible:
                task_id = group["representative"]
                checkpoint = {**rows[task_id], "action": "close_gap"}
                result = execute_proposal({"kind": "director_proposal", "task_id": task_id,
                                           "checkpoint": checkpoint},
                                          actions={"close_gap": action}, receipt_path=live_path, daily_cap=38)
                receipt_file.write(json.dumps({"task_id": task_id, "based_on": checkpoint["based_on"],
                                               **result}) + "\n")

        receipts = [json.loads(line) for line in rehearsal_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([receipt["task_id"] for receipt in receipts],
                         [group["representative"] for group in eligible])
        self.assertTrue(dangling.isdisjoint(receipt["task_id"] for receipt in receipts))
        for receipt in receipts:
            self.assertEqual((receipt["status"], receipt["reason"]), ("dry_run", "disabled"))
            self.assertEqual(receipt["based_on"], rows[receipt["task_id"]]["based_on"])
            self.assertEqual(check_anchors(receipt["based_on"], store)["status"], "anchored")
        self.assertEqual(store_file.read_bytes(), store_baseline)
        action.execute.assert_not_called()
        self.assertFalse(live_path.exists())
