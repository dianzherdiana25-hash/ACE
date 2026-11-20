"""Tes fixture identitas boot (boot_id) untuk tools.bridge_home (AG7)."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from tools.bridge_home import (
    BUNDLE_MANIFEST_SCHEMA,
    REQUIRED_ENTRY_NAMES,
    _pid_boot_id,
    plan_home,
)
from tools.test_bridge_home import CONFIG


class BridgeHomeBootIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(self.enterContext(TemporaryDirectory()))
        self.pid_file = root / "bridge.pid"
        self.pid_file.write_text("900", encoding="utf-8")
        self.bundle = root / "manifest.json"
        self.bundle.write_text(
            json.dumps(
                {
                    "schema": BUNDLE_MANIFEST_SCHEMA,
                    "entries": [{"name": name} for name in REQUIRED_ENTRY_NAMES],
                }
            ),
            encoding="utf-8",
        )
        self.base_config = {
            **CONFIG,
            "pid_file": str(self.pid_file),
            "expected_process_name": "bridge-fixture",
            "expected_process_starttime": 120,
        }

    def test_tick_from_different_boot_marked_unverified_not_matched(self) -> None:
        config = {**self.base_config, "expected_boot_id": "boot-aaaa-1111"}
        # Walaupun PID, comm, dan tick starttime sama-sama persis (mis. 120 setelah reboot),
        # boot_id yang berbeda WAJIB menghasilkan unverified dan bukan live/matched.
        boot_probe = Mock(side_effect=["boot-bbbb-2222", "boot-bbbb-2222"])
        plan = plan_home(
            config,
            bundle_manifest=self.bundle,
            pid_probe=lambda _: True,
            identity_probe=lambda _: "bridge-fixture",
            starttime_probe=lambda _: 120,
            boot_id_probe=boot_probe,
        )
        self.assertEqual(boot_probe.call_count, 2)
        self.assertEqual(
            plan["preflight"]["pid_file"],
            {"state": "unverified", "safe_to_continue": False, "reason": "boot_id_mismatch"},
        )
        self.assertFalse(plan["preflight"]["safe_to_continue"])
        self.assertNotIn("Gunakan kembali", plan["steps"][1]["action"])

    def test_matching_boot_id_and_starttime_allows_reuse(self) -> None:
        config = {**self.base_config, "expected_boot_id": "boot-aaaa-1111"}
        plan = plan_home(
            config,
            bundle_manifest=self.bundle,
            pid_probe=lambda _: True,
            identity_probe=lambda _: "bridge-fixture",
            starttime_probe=lambda _: 120,
            boot_id_probe=lambda: "boot-aaaa-1111",
        )
        self.assertEqual(
            plan["preflight"]["pid_file"],
            {"state": "live", "safe_to_continue": True, "reason": "identity_matched"},
        )
        self.assertTrue(plan["preflight"]["safe_to_continue"])

    def test_unreadable_or_flaky_boot_id_probe_marks_unverified(self) -> None:
        config = {**self.base_config, "expected_boot_id": "boot-aaaa-1111"}
        for probe_obj in (
            Mock(side_effect=FileNotFoundError),
            Mock(side_effect=["boot-aaaa-1111", "boot-cccc-3333"]),
        ):
            with self.subTest(probe=probe_obj):
                plan = plan_home(
                    config,
                    bundle_manifest=self.bundle,
                    pid_probe=lambda _: True,
                    identity_probe=lambda _: "bridge-fixture",
                    starttime_probe=lambda _: 120,
                    boot_id_probe=probe_obj,
                )
                self.assertEqual(plan["preflight"]["pid_file"]["state"], "unverified")
                self.assertFalse(plan["preflight"]["pid_file"]["safe_to_continue"])

    def test_plan_without_boot_marker_behaves_unchanged(self) -> None:
        boot_probe = Mock(side_effect=AssertionError("tidak boleh dipanggil tanpa expected_boot_id"))
        plan = plan_home(
            self.base_config,
            bundle_manifest=self.bundle,
            pid_probe=lambda _: True,
            identity_probe=lambda _: "bridge-fixture",
            starttime_probe=lambda _: 120,
            boot_id_probe=boot_probe,
        )
        boot_probe.assert_not_called()
        self.assertEqual(
            plan["preflight"]["pid_file"],
            {"state": "live", "safe_to_continue": True, "reason": "identity_matched"},
        )
        self.assertTrue(plan["preflight"]["safe_to_continue"])

    def test_default_boot_id_reader_reads_proc_kernel_boot_id(self) -> None:
        with patch("tools.bridge_home.Path.read_text", return_value="11111111-2222-3333-4444-555555555555\n") as rd:
            self.assertEqual(_pid_boot_id(), "11111111-2222-3333-4444-555555555555")
        rd.assert_called_once_with(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
