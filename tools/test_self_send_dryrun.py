"""Jaga agar preflight tidak mencapai jaringan atau membaca nilai token."""
from contextlib import redirect_stdout
from io import StringIO
import json
import os
import unittest
from unittest.mock import patch

from tools import self_send


class SelfSendDryRunTests(unittest.TestCase):
    def test_main_refused_and_valid_branch_accepted(self):
        for branch, passed in (("main", False), ("ace-auto/20261120-example", True)):
            with self.subTest(branch=branch):
                result = self_send.check_envelope(branch, merge_authority=False,
                                                  environ={"GH_TOKEN": "fixture"})
                self.assertEqual(result["checks"]["target_branch"]["passed"], passed)
                self.assertEqual(result["passed"], passed)
        result = self_send.check_envelope("ace-auto/20261120-example", merge_authority=True,
                                          environ={"GH_TOKEN": "fixture"})
        self.assertFalse(result["checks"]["merge_authority"]["passed"])

    def test_absent_credential_reported_without_core_calls(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(self_send._core, "_main") as core:
            with redirect_stdout(StringIO()) as output:
                status = self_send.main(["--dry-run", "--branch", "ace-auto/20261120-example"])
        core.assert_not_called()
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(output.getvalue())["checks"]["credential"]["reason"], "absent")

    def test_value_not_read(self):
        class MarkerOnly(dict):
            def __getitem__(self, name):
                raise AssertionError("credential value read")
        result = self_send.check_envelope("ace-auto/20261120-example",
                                          merge_authority=False, environ=MarkerOnly(GH_TOKEN=None))
        self.assertTrue(result["passed"])

    def test_normal_mode_delegates_unchanged_argv(self):
        args = ["flush", "--memory-root", "fixture", "--repo", "repo", "--home", "home"]
        with patch.object(self_send._core, "_main", return_value=7) as core:
            self.assertEqual(self_send.main(args), 7)
        core.assert_called_once_with(args)


if __name__ == "__main__":
    unittest.main()
