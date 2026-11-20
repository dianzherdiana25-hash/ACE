"""Buktikan preflight membaca penanda dari bundle GPG sintetis."""
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import bridge_home, bridge_secrets, secrets_bundle
from tools.test_bridge_home import CONFIG


@unittest.skipUnless(shutil.which("gpg"), "GPG diperlukan untuk fixture bundel")
class BundleManifestTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        gpg_home = self.root / "gpg"
        gpg_home.mkdir(mode=0o700)
        self.passphrase = secrets.token_hex(12)
        self.env = {**os.environ, "GNUPGHOME": str(gpg_home), "ACE_BUNDLE_S2K_COUNT": "65536",
                    "ACE_BUNDLE_PASSPHRASE": self.passphrase}
        self.config = self.root / "config.json"
        self.config.write_text(json.dumps({**CONFIG, "pid_file": str(self.root / "missing.pid")}),
                               encoding="utf-8")
        self.bundle = self.root / "bundle"
        self.bundle.mkdir()

    def write_bundle(self, values):
        with patch.dict(os.environ, self.env):
            secrets_bundle._store_values(self.passphrase, self.bundle, {
                "schema": secrets_bundle.SCHEMA_BUNDLE, "values": values,
            })

    def run_markers(self, *flags, **env):
        return subprocess.run([sys.executable, str(Path(__file__).with_name("bundle_manifest.py")),
                               "--bundle", str(self.bundle), *flags], env={**self.env, **env},
                              capture_output=True, text=True, timeout=10)

    def test_complete_and_missing_bundles_flow_through_preflight(self):
        for names in (bridge_secrets._REQUIRED, bridge_secrets._REQUIRED[:-1]):
            with self.subTest(names=names):
                values = {name: secrets.token_hex(24) for name in names}
                self.write_bundle(values)
                cipher = self.bundle / "bundle.gpg"
                before = cipher.read_bytes()
                run = self.run_markers()
                self.assertEqual(run.returncode, 0)
                self.assertEqual(run.stderr, "")
                for secret in [*values.values(), self.passphrase]:
                    self.assertFalse(secret in run.stdout or secret in run.stderr)
                self.assertEqual(json.loads(run.stdout), {
                    "schema": bridge_home.BUNDLE_MANIFEST_SCHEMA,
                    "entries": [{"name": name} for name in sorted(names)],
                })
                markers = self.root / "markers.json"
                markers.write_text(run.stdout, encoding="utf-8")
                result = subprocess.run([sys.executable, str(Path(bridge_home.__file__)),
                                         str(self.config), "--bundle-manifest", str(markers),
                                         "--format", "json"], capture_output=True, check=True,
                                        timeout=10)
                preflight = json.loads(result.stdout)["preflight"]
                missing = [name for name in bridge_secrets._REQUIRED if name not in names]
                self.assertEqual(preflight["credential_markers"], {
                    "state": "missing" if missing else "present", "missing_names": missing,
                })
                self.assertEqual(preflight["safe_to_continue"], not missing)
                self.assertTrue(cipher.read_bytes() == before)

    def test_wrong_passphrase_emits_no_manifest_or_values(self):
        secret = secrets.token_hex(24)
        self.write_bundle({bridge_secrets._REQUIRED[0]: secret})
        wrong = secrets.token_hex(12)
        run = self.run_markers(ACE_BUNDLE_PASSPHRASE=wrong)
        self.assertEqual(run.returncode, 2)
        self.assertEqual(run.stdout, "")
        self.assertIn("gagal didekripsi", run.stderr)
        self.assertFalse(any(value in run.stderr for value in (secret, wrong, self.passphrase)))

    def test_diff_and_preflight_agree_on_missing_name(self):
        names = bridge_secrets._REQUIRED
        values = {name: secrets.token_hex(24) for name in names}
        self.write_bundle(values)
        previous = self.root / "old.json"
        result = self.run_markers()
        self.assertEqual(result.returncode, 0)
        previous.write_text(result.stdout, encoding="utf-8")
        result = self.run_markers("--diff", str(previous))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {"added": [], "removed": [], "unchanged": sorted(names)})

        omitted = names[-1]
        extra = "fixture-extra"
        extra_value = secrets.token_hex(24)
        self.write_bundle({**{name: values[name] for name in names[:-1]}, extra: extra_value})
        diff = self.run_markers("--diff", str(previous))
        self.assertEqual(diff.returncode, 0)
        self.assertEqual(diff.stderr, "")
        self.assertFalse(any(secret in diff.stdout for secret in [*values.values(), extra_value, self.passphrase]))
        self.assertEqual(json.loads(diff.stdout),
                         {"added": [extra], "removed": [omitted], "unchanged": sorted(names[:-1])})

        current = self.root / "new.json"
        result = self.run_markers()
        self.assertEqual(result.returncode, 0)
        current.write_text(result.stdout, encoding="utf-8")
        plan = bridge_home.plan_home(json.loads(self.config.read_text()), bundle_manifest=current)
        self.assertFalse(plan["preflight"]["safe_to_continue"])
        self.assertEqual(plan["preflight"]["credential_markers"]["missing_names"],
                         json.loads(diff.stdout)["removed"])

    def test_malformed_old_manifest_returns_generic_error(self):
        self.write_bundle({})
        old = self.root / "old.json"
        marker = secrets.token_hex(24)
        old.write_text(marker, encoding="utf-8")
        run = self.run_markers("--diff", str(old))
        self.assertEqual(run.returncode, 2)
        self.assertEqual(run.stdout, "")
        self.assertFalse(marker in run.stderr)
