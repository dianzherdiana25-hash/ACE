"""End-to-end checks of the public launcher and persisted runtime interface."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class RuntimeCLITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ace-cli-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.workspace = self.directory / "state"

    def invoke(self, command, *arguments, expected=0):
        result = subprocess.run(
            [sys.executable, str(ROOT / "ace.py"), command,
             "--workspace", str(self.workspace), *map(str, arguments)],
            cwd=ROOT, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(expected, result.returncode, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        return json.loads(result.stdout) if expected == 0 else result

    def test_demo_learns_and_repeated_demo_preserves_task_ids(self):
        first = self.invoke("demo")
        self.assertEqual({"source_equal", "inherited_equal", "changed_ends"},
                         set(first["task_ids"]))
        self.assertEqual(3, len(set(first["task_ids"].values())))
        self.assertEqual(3, len(first["outcomes"]))
        self.assertNotIn("fit_report", first["outcomes"][0])
        self.assertEqual(63, first["outcomes"][0]["train_correct"])
        task_id = first["task_ids"]["source_equal"]
        evidence = self.invoke("report", "--task", task_id)
        self.assertEqual(task_id, evidence["task_id"])
        self.assertIsInstance(evidence["fit_report"], dict)
        self.assertIs(self.invoke("predict", "--task", task_id,
                                  "--word", "ab")["prediction"], True)
        self.assertIs(self.invoke("predict", "--task", task_id,
                                  "--word", "a")["prediction"], False)
        second = self.invoke("demo")
        self.assertEqual(first["task_ids"], second["task_ids"])
        self.assertEqual(first["evaluation"], second["evaluation"])
        self.assertEqual([], second["outcomes"])
        self.assertEqual(evidence, self.invoke("report", "--task", task_id))
        self.assertIsInstance(self.invoke("status"), dict)
        self.assertEqual([], self.invoke("run")["outcomes"])

    def test_task_file_enqueue_resume_and_separate_evaluation(self):
        from ace_capability_evolution.compositional import bank

        train, validation, terminal = bank("equal", 20261106)
        task = self.directory / "task.json"
        task.write_text(json.dumps({"name": "file_equal", "train": train,
                                    "validation": validation}), encoding="utf-8")
        data = self.directory / "terminal.json"
        data.write_text(json.dumps(terminal), encoding="utf-8")
        self.invoke("init")
        queued = self.invoke("enqueue", "--task", task)
        self.assertEqual(queued, self.invoke("enqueue", "--task", task))
        self.assertEqual(1, len(self.invoke("run", "--max-tasks", "1")["outcomes"]))
        evaluation = self.invoke("evaluate", "--task", queued["task_id"], "--data", data)
        self.assertEqual(queued["task_id"], evaluation["task_id"])
        self.assertIsInstance(evaluation["evaluation"], dict)
        self.assertEqual([], self.invoke("run")["outcomes"])

    def test_invalid_json_and_nonboolean_labels_fail_concisely(self):
        task = self.directory / "bad.json"
        task.write_text("{broken", encoding="utf-8")
        result = self.invoke("enqueue", "--task", task, expected=2)
        self.assertTrue(result.stderr.startswith("ace: "))
        self.assertEqual("", result.stdout)
        task.write_text(json.dumps({"name": "bad", "train": [["ab", 1]],
                                    "validation": [["a", False]]}), encoding="utf-8")
        result = self.invoke("enqueue", "--task", task, expected=2)
        self.assertIn("Boolean", result.stderr)
        self.assertFalse(self.workspace.exists())


if __name__ == "__main__":
    unittest.main()
