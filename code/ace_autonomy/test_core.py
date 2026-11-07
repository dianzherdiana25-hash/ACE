"""Adversarial unit tests and integration with actual ACE Runtime on CI."""
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from .core import Autonomy, IntegrityError, PolicyError


def make_goal(*steps):
    return {"schema": "ace.goal.v01", "name": "bounded inspection", "steps": list(steps)}


def worker(workspace, root, gid, out):
    with Autonomy(workspace, root) as engine:
        out.put(engine.run_one(gid))


def crash_worker(workspace, root, gid):
    with Autonomy(workspace, root) as engine:
        original = engine._dispatch
        def die_after_read(action):
            original(action)
            os._exit(17)
        engine._dispatch = die_after_read
        engine.run_one(gid)


class AutonomyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "checkout"
        self.root.mkdir()
        (self.root / "ace.py").write_text("# test checkout")
        (self.root / "README.md").write_text("immutable trusted source")
        (self.root / "code/ace_runtime").mkdir(parents=True)
        (self.root / "code/ace_runtime/engine.py").write_text("# fixed engine source")
        self.ws = Path(self.tmp.name) / "workspace"

    def open(self):
        return Autonomy(self.ws, self.root)

    def test_idempotent_goal_and_restart(self):
        goal = make_goal({"tool": "inspect_file", "path": "README.md"}, {"tool": "inspect_file", "path": "ace.py"})
        with self.open() as a:
            gid = a.enqueue(goal)
            self.assertEqual(gid, a.enqueue(goal))
            self.assertEqual(a.run_one(gid)["status"], "RUNNING")
        with self.open() as a:
            self.assertEqual(a.run_one(gid)["status"], "SUCCEEDED")
            self.assertIsNone(a.run_one(gid))
            self.assertEqual(len(a.report(gid)["results"]), 2)

    def test_policy_rejection(self):
        with self.open() as a:
            for path in ("../ace.py", "/etc/passwd"):
                with self.assertRaises(PolicyError):
                    a.enqueue(make_goal({"tool": "inspect_file", "path": path}))
            with self.assertRaises(PolicyError):
                a.enqueue(make_goal({"tool": "shell", "cmd": "ls"}))
            (self.root / "escape").symlink_to(Path(self.tmp.name))
            gid = a.enqueue(make_goal({"tool": "inspect_file", "path": "escape/README.md"}))
            self.assertEqual(a.run_one(gid)["status"], "FAILED")

    def test_tamper_fail_closed(self):
        with self.open() as a:
            gid = a.enqueue(make_goal({"tool": "inspect_file", "path": "README.md"}))
        db = sqlite3.connect(self.ws / "goals.sqlite3")
        db.execute("UPDATE goals SET status='SUCCEEDED' WHERE id=?", (gid,))
        db.commit()
        db.close()
        with self.assertRaises(IntegrityError):
            self.open()

    def test_receipt_tamper_fail_closed(self):
        with self.open() as a:
            a.enqueue(make_goal({"tool": "inspect_file", "path": "README.md"}))
        db = sqlite3.connect(self.ws / "goals.sqlite3")
        db.execute("UPDATE events SET signature='0'")
        db.commit()
        db.close()
        with self.assertRaises(IntegrityError):
            self.open()

    def test_engine_change_fail_closed(self):
        with self.open() as a:
            a.enqueue(make_goal({"tool": "inspect_file", "path": "README.md"}))
        (self.root / "code/ace_runtime/engine.py").write_text("# different engine source")
        with self.assertRaises(IntegrityError):
            self.open()

    def test_cancelled_goal(self):
        with self.open() as a:
            gid = a.enqueue(make_goal({"tool": "inspect_file", "path": "README.md"}))
            self.assertEqual(a.cancel(gid)["status"], "CANCELLED")
            self.assertIsNone(a.run_one(gid))

    def test_atomic_rollback_on_interruption(self):
        with self.open() as a:
            gid = a.enqueue(make_goal({"tool": "inspect_file", "path": "README.md"}))
            with patch.object(a, "_append", side_effect=RuntimeError("injected failure")):
                with self.assertRaises(RuntimeError):
                    a.run_one(gid)
            self.assertEqual(a.report(gid)["status"], "QUEUED")

    def test_actual_subprocess_death_rolls_back_and_resumes(self):
        goal = make_goal({"tool": "inspect_file", "path": "README.md"})
        with self.open() as a:
            gid = a.enqueue(goal)
        ctx = multiprocessing.get_context("spawn")
        p = ctx.Process(target=crash_worker, args=(str(self.ws), str(self.root), gid))
        p.start()
        p.join(timeout=20)
        self.assertEqual(p.exitcode, 17)
        with self.open() as a:
            self.assertEqual(a.report(gid)["status"], "QUEUED")
            self.assertEqual(a.run_one(gid)["status"], "SUCCEEDED")
            self.assertEqual(a.db.execute("SELECT count(*) FROM events").fetchone()[0], 2)

    def test_two_processes_do_not_duplicate_step(self):
        goal = make_goal({"tool": "inspect_file", "path": "README.md"})
        with self.open() as a:
            gid = a.enqueue(goal)
        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        children = [ctx.Process(target=worker, args=(str(self.ws), str(self.root), gid, q)) for _ in range(2)]
        for p in children: p.start()
        for p in children: p.join(timeout=20)
        self.assertTrue(all(p.exitcode == 0 for p in children))
        with self.open() as a:
            self.assertEqual(a.report(gid)["status"], "SUCCEEDED")
            self.assertEqual(a.db.execute("SELECT count(*) FROM events").fetchone()[0], 2)

    def test_no_implicit_model_or_phenomenal_consciousness(self):
        with self.open() as a:
            gid = a.enqueue(make_goal({"tool": "inspect_file", "path": "README.md"}))
            report = a.run_one(gid)
            self.assertNotIn("conscious", json.dumps(report).lower())


class RealACEIntegration(unittest.TestCase):
    def test_actual_runtime_demo(self):
        # Must execute on actual repository checkout, with PYTHONPATH=code.
        from ace_runtime.engine import Runtime
        from ace_runtime.cli import demo
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(__file__).resolve().parents[2]
            with Autonomy(tmp, root) as a:
                goal = make_goal({"tool": "ace_demo"}, {"tool": "ace_status"})
                gid = a.enqueue(goal)
                self.assertEqual(a.run_one(gid)["status"], "RUNNING")
                report = a.run_one(gid)
                self.assertEqual(report["status"], "SUCCEEDED")
                self.assertEqual(report["results"][0]["evidence"]["tasks"], 3)
                self.assertEqual(report["results"][0]["evidence"]["capabilities"], 2)
                self.assertEqual(report["results"][1]["evidence"]["completed"], 3)


if __name__ == "__main__":
    unittest.main()
