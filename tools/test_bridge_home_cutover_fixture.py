"""Uji preflight cutover tanpa meluncurkan proses atau membuka bundle."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.bridge_home import BUNDLE_MANIFEST_SCHEMA, REQUIRED_ENTRY_NAMES, markdown, plan_home
from tools.test_bridge_home import CONFIG


class CutoverFixtureTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.pid = self.root / "bridge.pid"
        self.pid.write_text("31337\n", encoding="utf-8")
        self.manifest = self.root / "manifest.json"
        self.config = {**CONFIG, "pid_file": str(self.pid)}

    def write_entries(self, entries):
        self.manifest.write_text(json.dumps({"schema": BUNDLE_MANIFEST_SCHEMA, "entries": entries}),
                                 encoding="utf-8")

    def test_stale_pid_and_marker_only_ready(self):
        self.write_entries([{"name": name} for name in REQUIRED_ENTRY_NAMES])
        seen = []

        def missing_process(pid):
            seen.append(pid)
            return False

        plan = plan_home(self.config, bundle_manifest=self.manifest, pid_probe=missing_process)
        self.assertEqual(seen, [31337, 31337])
        self.assertEqual(plan["preflight"]["pid_file"], {"state": "stale", "safe_to_continue": True})
        self.assertTrue(plan["preflight"]["safe_to_continue"])
        self.assertIn("stale (aman-untuk-lanjut)", markdown(plan))

    def test_markdown_accepts_a_legacy_v1_plan(self):
        plan = plan_home(self.config, pid_probe=lambda _: False)
        del plan["preflight"]
        self.assertIn("Langkah mundur", markdown(plan))
        self.assertNotIn("PID file", markdown(plan))

    def test_only_presence_of_required_names_controls_credential_marker(self):
        self.write_entries([{"name": "groq-api-key", "extra": "fixture-not-for-report"}])
        plan = plan_home(self.config, bundle_manifest=self.manifest, pid_probe=lambda _: True)
        self.assertEqual(plan["preflight"]["credential_markers"], {
            "state": "missing", "missing_names": ["gemini-api-key", "gonka-api-key"],
        })
        self.assertEqual(plan["preflight"]["pid_file"]["state"], "live")
        self.assertFalse(plan["preflight"]["safe_to_continue"])
        self.assertFalse("fixture-not-for-report" in json.dumps(plan))
        self.assertFalse("fixture-not-for-report" in markdown(plan))


if __name__ == "__main__":
    unittest.main()
