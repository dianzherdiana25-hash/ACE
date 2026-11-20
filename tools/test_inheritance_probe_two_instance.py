"""Uji skor dua-instance dari fixture dan ikatan manifest sebelum lari."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import inheritance_probe as probe


class TwoInstanceTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        self.manifest = root / "manifest.json"
        self.warm = root / "warm.json"
        cold, tasks = root / "cold.json", root / "tasks.json"
        self.warm.write_text('{"records":{"q1":"yes"}}')
        cold.write_text("{}")
        tasks.write_text(json.dumps([
            {"id": "a", "query": "q1", "expected": "yes", "cold_decision": "no"},
            {"id": "b", "query": "q2", "expected": "yes", "cold_decision": "yes"},
        ]))
        self.argv = ["--two-instance", "--inherited", str(self.warm), "--cold", str(cold),
                     "--tasks", str(tasks)]

    def run_probe(self, flag):
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(probe.main([*self.argv, flag, str(self.manifest)]), 0)
        return json.loads(output.getvalue())

    def test_two_instance_scores_bound_to_manifest(self):
        with patch.object(probe, "_run_command") as runner:
            result = self.run_probe("--manifest")
            self.assertEqual(self.run_probe("--verify-manifest"), result)
        runner.assert_not_called()
        self.assertEqual([row["delta_score"] for row in result["tasks"]], [1, 0])
        self.assertEqual((result["score_delta_total"], result["delta"]), (1, 0.5))
        self.assertEqual(result["manifest_sha256"], hashlib.sha256(self.manifest.read_bytes()).hexdigest())

    def test_changed_snapshot_refuses_before_evaluation(self):
        self.run_probe("--manifest")
        self.warm.write_bytes(self.warm.read_bytes().replace(b'"yes"', b'"end"'))
        with patch.object(probe, "compare_instances") as run, redirect_stderr(StringIO()) as output:
            with self.assertRaises(SystemExit) as raised:
                probe.main([*self.argv, "--verify-manifest", str(self.manifest)])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("warm.json", output.getvalue())
        run.assert_not_called()
