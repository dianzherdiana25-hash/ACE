"""Actual learned transfer, failure custody, process recovery and concurrency."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ace_capability_evolution import compositional as c
from .engine import Runtime, IntegrityError, program_from_data

ROOT = Path(__file__).resolve().parents[2]


def task(name="source", family="equal", seed=20261106):
    train, validation, terminal = c.bank(family, seed)
    return {"name": name, "train": train, "validation": validation}, terminal


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ace-runtime-")
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name) / "state"

    def process(self, script, *args):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "code"))
        return subprocess.run([sys.executable, "-c", script, str(self.workspace), *args],
                              cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)

    def test_learns_then_validates_inheritance_without_refitting(self):
        with Runtime(self.workspace) as runtime:
            first, terminal = task()
            original = runtime.enqueue(first)
            learned = runtime.run()[0]
            self.assertEqual(learned["phase"], "LEARNED_STAGED")
            self.assertTrue(learned["learning_called"])
            second, _ = task("successor", seed=20261107)
            successor = runtime.enqueue(second)
            with patch.object(c, "fit", side_effect=AssertionError("must not refit")):
                reused = runtime.run()[0]
            self.assertEqual(reused["phase"], "REUSE_VALIDATED")
            self.assertFalse(reused["learning_called"])
            self.assertEqual(learned["model_id"], reused["model_id"])
            self.assertTrue(runtime.predict(successor, "aabb"))
            self.assertFalse(runtime.predict(successor, "aab"))
            self.assertEqual(runtime.evaluate(original, terminal)["correct"], 128)
            self.assertEqual(runtime.status()["capabilities"], 1)

    def test_negative_transfer_is_rejected_and_old_model_retained(self):
        with Runtime(self.workspace) as runtime:
            source, _ = task()
            source_id = runtime.enqueue(source)
            before = runtime.run()[0]
            changed, _ = task("new_semantics", "ends")
            changed_id = runtime.enqueue(changed)
            result = runtime.run()[0]
            self.assertFalse(result["inherited_selection"]["admitted"])
            self.assertTrue(result["learning_called"])
            self.assertEqual(result["phase"], "LEARNED_STAGED")
            self.assertNotEqual(result["model_id"], before["model_id"])
            self.assertTrue(runtime.predict(source_id, "ba"))
            self.assertFalse(runtime.predict(changed_id, "ba"))
            self.assertEqual(runtime.status()["capabilities"], 2)

    def test_unvalidated_model_is_never_predictable_or_evaluable(self):
        with Runtime(self.workspace) as runtime:
            data, terminal = task(family="starts")
            identity = runtime.enqueue(data)
            result = runtime.run()[0]
            self.assertEqual(result["phase"], "NO_VALIDATED_MODEL")
            self.assertEqual(runtime.status()["capabilities"], 0)
            with self.assertRaises(ValueError):
                runtime.predict(identity, "ab")
            with self.assertRaises(ValueError):
                runtime.evaluate(identity, terminal)

    def test_queue_is_idempotent_and_bounded_across_restarts(self):
        first, _ = task()
        second, _ = task("second", seed=20261107)
        with Runtime(self.workspace) as runtime:
            first_id = runtime.enqueue(first)
            self.assertEqual(runtime.enqueue(first), first_id)
            runtime.enqueue(second)
            self.assertEqual(len(runtime.run(max_tasks=1)), 1)
            self.assertEqual(runtime.status()["pending"], 1)
        with Runtime(self.workspace) as runtime:
            self.assertEqual(len(runtime.run(max_tasks=1)), 1)
            self.assertEqual(runtime.run(), [])
            self.assertEqual(runtime.status()["events"], 4)
            for bad in (True, 0, 257, "1"):
                with self.assertRaises(ValueError):
                    runtime.run(bad)

    def test_actual_process_exit_rolls_back_trial_and_resumes(self):
        data, _ = task()
        with Runtime(self.workspace) as runtime:
            runtime.enqueue(data)
        script = """
import os,sys
from ace_runtime import Runtime
r=Runtime(sys.argv[1])
original=r._solve
def interrupted(*args):
    original(*args)
    os._exit(73)
r._solve=interrupted
r.run()
"""
        result = self.process(script)
        self.assertEqual(result.returncode, 73, result.stderr)
        with Runtime(self.workspace) as runtime:
            self.assertEqual(runtime.status()["pending"], 1)
            self.assertEqual(runtime.status()["capabilities"], 0)
            self.assertEqual(runtime.status()["events"], 1)
            self.assertTrue(runtime.run()[0]["staged"])

    def test_receipt_failure_rolls_back_model_and_task_atomically(self):
        data, _ = task()
        with Runtime(self.workspace) as runtime:
            runtime.enqueue(data)
            original = runtime._append
            def failure(kind, *args):
                if kind == "completed":
                    raise OSError("simulated journal write failure")
                return original(kind, *args)
            with patch.object(runtime, "_append", side_effect=failure), self.assertRaises(OSError):
                runtime.run()
            self.assertEqual(runtime.status()["capabilities"], 0)
            self.assertEqual(runtime.status()["pending"], 1)
            self.assertTrue(runtime.run()[0]["staged"])

    def test_failed_trial_cannot_leave_orphaned_capabilities(self):
        data, _ = task()
        with Runtime(self.workspace) as runtime:
            runtime.enqueue(data)
            original = runtime._solve
            def failure(*args):
                original(*args)
                raise RuntimeError("simulated failure after model insert")
            with patch.object(runtime, "_solve", side_effect=failure):
                result = runtime.run()[0]
            self.assertEqual(result["status"], "failed")
            self.assertEqual(runtime.status()["failed"], 1)
            self.assertEqual(runtime.status()["capabilities"], 0)

    def test_two_processes_cannot_complete_the_same_task(self):
        with Runtime(self.workspace) as runtime:
            for index in range(2):
                data, _ = task(str(index), seed=20261106 + index)
                runtime.enqueue(data)
        script = """
import json,sys
from ace_runtime import Runtime
with Runtime(sys.argv[1]) as r:
    print(json.dumps([x['task_id'] for x in r.run(1)]))
"""
        env = dict(os.environ, PYTHONPATH=str(ROOT / "code"))
        processes = [subprocess.Popen([sys.executable, "-c", script, str(self.workspace)],
                                     cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True) for _ in range(2)]
        completed = []
        for process in processes:
            out, err = process.communicate(timeout=30)
            self.assertEqual(process.returncode, 0, err)
            completed.extend(json.loads(out))
        self.assertEqual(len(completed), 2)
        self.assertEqual(len(set(completed)), 2)
        with Runtime(self.workspace) as runtime:
            self.assertEqual(runtime.status()["completed"], 2)
            self.assertEqual(runtime.status()["events"], 4)

    def test_terminal_evaluation_is_separate_and_bound_once(self):
        data, terminal = task()
        with Runtime(self.workspace) as runtime:
            identity = runtime.enqueue(data)
            runtime.run()
            before = runtime.report(identity)
            with self.assertRaises(ValueError):
                runtime.evaluate(identity, data["train"])
            report = runtime.evaluate(identity, terminal)
            self.assertEqual(report, runtime.evaluate(identity, terminal))
            with self.assertRaises(ValueError):
                runtime.evaluate(identity, [(w, not y) for w, y in terminal])
            self.assertEqual(runtime.report(identity), before)
            self.assertEqual(runtime.status()["evaluations"], 1)
            self.assertEqual(runtime.status()["events"], 3)

    def test_invalid_task_types_and_budgets_are_rejected(self):
        good, _ = task()
        invalid = [dict(good, oracle="not allowed"), dict(good, train=[["a", 1]]),
                   dict(good, train=[["a", True], ["a", False]]),
                   dict(good, validation=[["a", True]]), dict(good, train=[["c", True]]),
                   dict(good, train=[["a" * 63, True]])]
        with Runtime(self.workspace) as runtime:
            for data in invalid:
                with self.subTest(data=str(data)[:100]), self.assertRaises(ValueError):
                    runtime.enqueue(data)
            self.assertEqual(runtime.status()["events"], 0)

    def test_closed_decoder_rejects_code_bool_aliases_and_bad_graphs(self):
        program = c.Program("counter", (1, -1)).data()
        self.assertEqual(program_from_data(program).data(), program)
        bad = copy.deepcopy(program)
        bad["counter_ast"][0] = "exec"
        with self.assertRaises(IntegrityError):
            program_from_data(bad)
        bad = copy.deepcopy(program)
        bad["weights"][0] = True
        with self.assertRaises(IntegrityError):
            program_from_data(bad)
        graph = {"kind": "dfa", "weights": None, "counter_ast": None,
                 "fixed_guard": "true", "dfa": [[True, [["a", True]]]]}
        with self.assertRaises(IntegrityError):
            program_from_data(graph)

    def test_event_and_model_corruption_fail_on_reopen(self):
        data, _ = task()
        with Runtime(self.workspace) as runtime:
            runtime.enqueue(data)
            runtime.run()
            runtime.db.execute("UPDATE events SET hash='corrupted' WHERE seq=2")
        with self.assertRaises(IntegrityError):
            Runtime(self.workspace)

    def test_queue_order_is_bound_to_enqueue_receipts(self):
        with Runtime(self.workspace) as runtime:
            first, _ = task()
            second, _ = task("second", seed=20261107)
            identity = runtime.enqueue(first)
            runtime.enqueue(second)
            runtime.db.execute("UPDATE tasks SET ordinal=10 WHERE id=?", (identity,))
            with self.assertRaises(IntegrityError):
                runtime.status()

    def test_model_bytes_and_evaluation_data_are_checked(self):
        data, terminal = task()
        with Runtime(self.workspace) as runtime:
            identity = runtime.enqueue(data)
            runtime.run()
            saved = runtime.db.execute("SELECT id, program FROM library").fetchone()
            bad = json.loads(saved["program"])
            bad["weights"] = [1, -2]
            runtime.db.execute("UPDATE library SET program=? WHERE id=?", (json.dumps(bad), saved["id"]))
            with self.assertRaises(IntegrityError):
                runtime.status()
            runtime.db.execute("UPDATE library SET program=? WHERE id=?", (saved["program"], saved["id"]))
            runtime.evaluate(identity, terminal)
            runtime.db.execute("UPDATE evaluations SET data=?", (json.dumps([(w, not y) for w, y in terminal]),))
            with self.assertRaises(IntegrityError):
                runtime.status()


if __name__ == "__main__":
    unittest.main()
