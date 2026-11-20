"""Cegah PID daur ulang dianggap milik bridge tanpa identitas yang cocok."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from tools.bridge_home import markdown, plan_home
from tools.test_bridge_home import CONFIG


class BridgePIDReuseTests(unittest.TestCase):
    def setUp(self):
        path = Path(self.enterContext(TemporaryDirectory())) / "bridge.pid"
        path.write_text("900", encoding="utf-8")
        self.config = {**CONFIG, "pid_file": str(path), "expected_process_name": "bridge-fixture"}

    def test_stale_does_not_probe_identity(self):
        identity = Mock()
        plan = plan_home(self.config, pid_probe=lambda _: False, identity_probe=identity)
        identity.assert_not_called()
        self.assertEqual(plan["preflight"]["pid_file"], {"state": "stale", "safe_to_continue": True})

    def test_live_match_is_safe_for_pid_check(self):
        identity = Mock(return_value="bridge-fixture")
        plan = plan_home(self.config, pid_probe=lambda _: True, identity_probe=identity)
        identity.assert_called_once_with(900)
        self.assertTrue(plan["preflight"]["pid_file"]["safe_to_continue"])

    def test_reused_pid_requires_operator(self):
        plan = plan_home(self.config, pid_probe=lambda _: True, identity_probe=lambda _: "other")
        self.assertEqual(plan["preflight"]["pid_file"],
                         {"state": "identity_mismatch", "safe_to_continue": False})
        self.assertIn("perlu pemeriksaan operator", markdown(plan))

    def test_unverified_identity_requires_operator(self):
        for identity in (Mock(return_value=None), Mock(side_effect=PermissionError)):
            with self.subTest(identity=identity):
                plan = plan_home(self.config, pid_probe=lambda _: True, identity_probe=identity)
                self.assertEqual(plan["preflight"]["pid_file"]["state"], "unverified")
                self.assertFalse(plan["preflight"]["pid_file"]["safe_to_continue"])
