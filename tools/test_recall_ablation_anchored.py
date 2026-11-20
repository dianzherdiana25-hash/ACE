"""Bandingkan lengan anchored dan kunci byte keluaran ablation asli."""
import hashlib
import json
import unittest

from tools.recall_ablation import run_ablation
from tools.test_recall_ablation import TASK


class AnchoredTests(unittest.TestCase):
    def test_clean_matches_active_and_dangling_matches_off(self):
        tasks = [{**TASK, "id": name, "query": name} for name in ("clean", "dangling")]
        store = {
            "records": {
                "clean": [{"decision": "warm", "based_on": ["r1"]}],
                "dangling": [{"decision": "warm", "based_on": ["r1", "r-absent"]}],
            },
            "verified_refs": ["r1"],
        }
        rows, result = run_ablation(store, tasks, anchored=True)
        decisions = {}
        for line in rows.splitlines():
            record = json.loads(line)
            decisions[(record["task_id"], record["arm"])] = (record["decision"], record["recalled_count"])
        self.assertEqual(decisions["clean", "anchored"], decisions["clean", "active"])
        self.assertEqual(decisions["dangling", "anchored"], decisions["dangling", "off"])
        self.assertEqual(result["anchored_delta"], 0.5)
        self.assertEqual(result["delta"], 1.0)

    def test_two_arm_legacy_matches_exact_fixture_hash(self):
        data, summary = run_ablation({"q": ["warm"]}, [TASK, {**TASK, "id": "t2"}], seed=23)
        expected_hash = "3cfcfba7521cd003cfde0d11b7ff3cdcbb23feaa406daea7f7fade5ad0910c8b"
        self.assertEqual(hashlib.sha256(data).hexdigest(), expected_hash)
        expected = {"schema": "ace.recall-ablation.v1", "tasks": 2, "seed": 23,
                    "scores": {"active": 2, "off": 0}, "delta": 1.0, "results_sha256": expected_hash}
        self.assertEqual(json.dumps(summary, sort_keys=True, indent=2),
                         json.dumps(expected, sort_keys=True, indent=2))
