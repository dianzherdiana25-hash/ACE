"""Uji selisih recall dan hash hasil pada fixture yang diketahui."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.recall_ablation import main, run_ablation


TASK = {"id": "t1", "query": "q", "cold_decision": "cold", "expected": "warm"}


class RecallAblationTests(unittest.TestCase):
    def test_injected_recall_changes_decision(self):
        data, summary = run_ablation({"answer": "warm"}, [TASK],
                                     recall=lambda query, store: [store["answer"]])
        active, off = map(json.loads, data.splitlines())
        self.assertEqual((active["decision"], active["recalled_count"]), ("warm", 1))
        self.assertEqual((off["decision"], off["recalled_count"]), ("cold", 0))
        self.assertEqual(summary["delta"], 1.0)
        self.assertEqual(summary["results_sha256"], hashlib.sha256(data).hexdigest())

    def test_no_change_is_zero(self):
        _, summary = run_ablation({"q": ["cold"]}, [TASK])
        self.assertEqual(summary["delta"], 0)

    def test_cli_repeat_has_identical_bytes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            store, tasks = root / "store.json", root / "tasks.json"
            store.write_text('{"q":["warm"]}', encoding="utf-8")
            tasks.write_text(json.dumps([TASK, {**TASK, "id": "t2"}]), encoding="utf-8")
            for run in ("one", "two"):
                self.assertEqual(main(["--store", str(store), "--tasks", str(tasks),
                                       "--seed", "23", "--output-dir", str(root / run)]), 0)
            for name in ("results.jsonl", "summary.json"):
                self.assertEqual((root / "one" / name).read_bytes(), (root / "two" / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
