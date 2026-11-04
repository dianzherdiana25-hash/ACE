"""Self-checks for fail-visible ACE process checkpointing."""
import json
import pathlib
import sys
import tempfile
import unittest

import ace_progress_guard as guard


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)

    def options(self, code, timeout=2.0, recover=False):
        return type("Options", (), {
            "state": self.root / "run.json", "cwd": self.root,
            "source_commit": "test-head", "timeout": timeout,
            "heartbeat": 0.05, "recover": recover,
            "command": [sys.executable, "-c", code],
        })()

    def state(self):
        return json.loads((self.root / "run.json").read_text())

    def test_complete_and_deduplicate(self):
        o = self.options("print('ok')")
        self.assertEqual(guard.run(o), 0)
        self.assertEqual(self.state()["status"], "COMPLETE")
        self.assertEqual(guard.run(o), 0)
        self.assertEqual((self.root / "run.stdout").read_text(), "ok\n")

    def test_command_change_requires_recovery(self):
        self.assertEqual(guard.run(self.options("print('a')")), 0)
        self.assertEqual(guard.run(self.options("print('b')")), 3)
        self.assertEqual(guard.run(self.options("print('b')", recover=True)), 0)

    def test_nonzero_is_visible_and_no_retry(self):
        o = self.options("import sys; sys.exit(8)")
        self.assertEqual(guard.run(o), 1)
        self.assertEqual(self.state()["exit_code"], 8)
        self.assertEqual(self.state()["status"], "FAILED")
        self.assertEqual(guard.run(o), 3)

    def test_timeout_is_visible(self):
        self.assertEqual(guard.run(self.options("import time; time.sleep(1)", timeout=0.15)), 124)
        self.assertEqual(self.state()["status"], "TIMEOUT")

    def test_running_state_cannot_be_silently_reexecuted(self):
        o = self.options("print('never')", recover=True)
        guard.write_json_atomic(o.state, {"status": "RUNNING"})
        self.assertEqual(guard.run(o), 4)

    def test_corrupt_output_cannot_be_skipped(self):
        o = self.options("print('ok')")
        self.assertEqual(guard.run(o), 0)
        (self.root / "run.stdout").write_text("altered\n")
        self.assertEqual(guard.run(o), 3)

    def test_invalid_timeout_rejected(self):
        with self.assertRaises(ValueError):
            guard.run(self.options("print(1)", timeout=0))


if __name__ == "__main__":
    unittest.main()
