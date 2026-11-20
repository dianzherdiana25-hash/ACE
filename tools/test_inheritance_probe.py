"""Uji delta fixture, data cacat, dan protokol subprocess lokal."""
import sys
import unittest
from unittest.mock import patch

from tools.inheritance_probe import compare


TASKS = [{"id": "a"}, {"id": "b"}]


class InheritanceProbeTests(unittest.TestCase):
    def test_dry_run_advantage(self):
        with patch("tools.inheritance_probe._run_command") as runner:
            result = compare({"passes": {"a": True, "b": True}},
                             {"passes": {"a": True, "b": False}}, TASKS, dry_run=True)
        runner.assert_not_called()
        self.assertEqual(result["delta"], 0.5)
        self.assertEqual(result["tasks"][1], {"id": "b", "inherited": True, "cold": False})

    def test_dry_run_zero(self):
        snapshot = {"passes": {"a": True, "b": False}}
        self.assertEqual(compare(snapshot, snapshot, TASKS, dry_run=True)["delta"], 0)

    def test_dry_run_missing_output_is_error(self):
        snapshot = {"passes": {"a": True}}
        with self.assertRaisesRegex(ValueError, "satu boolean"):
            compare(snapshot, snapshot, TASKS, dry_run=True)

    def test_explicit_argv_runner(self):
        runner = [sys.executable, "-c",
                  "import json,sys; x=json.load(open(sys.argv[1])); "
                  "assert len(json.load(open(sys.argv[2])))==2; print(json.dumps(x['passes']))",
                  "{snapshot}", "{tasks}"]
        snapshot = {"passes": {"a": True, "b": True}}
        result = compare(snapshot, snapshot, TASKS, runner=runner)
        self.assertEqual(result["pass_counts"], {"inherited": 2, "cold": 2})


if __name__ == "__main__":
    unittest.main()
