"""Periksa pemuatan GPG memakai nilai sintetis yang dibuat saat tes."""
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import bridge_secrets, secrets_bundle


@unittest.skipUnless(shutil.which("gpg"), "GPG diperlukan untuk fixture bundel")
class BridgeSecretsTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.bundle = self.root / "bundle"
        self.bundle.mkdir()
        gpg_home = self.root / "gpg"
        gpg_home.mkdir(mode=0o700)
        self.passphrase = secrets.token_hex(12)
        self.value = secrets.token_hex(24)
        self.enterContext(patch.dict(os.environ, {
            "GNUPGHOME": str(gpg_home), "ACE_BUNDLE_S2K_COUNT": "65536",
            "ACE_BUNDLE_PASSPHRASE": self.passphrase,
        }))
        secrets_bundle._store_values(self.passphrase, self.bundle, {
            "schema": secrets_bundle.SCHEMA_BUNDLE,
            "values": dict.fromkeys(bridge_secrets._REQUIRED, self.value),
        })

    def test_child_presence_and_length_and_output_redaction(self):
        script = Path(__file__).with_name("bridge_secrets.py")
        child = (
            "import os,sys; "
            "assert 'ACE_BUNDLE_PASSPHRASE' not in os.environ; "
            "assert all(len(os.environ[k])==48 for k in "
            "('GROQ_API_KEY','GEMINI_API_KEY','GONKA_API_KEY')); "
            "print(os.environ['GROQ_API_KEY']); print(os.environ['GEMINI_API_KEY'],file=sys.stderr)"
        )
        proc = subprocess.run([sys.executable, str(script), "--bundle", str(self.bundle),
                               "--", sys.executable, "-c", child],
                              capture_output=True, text=True, check=True)
        self.assertEqual((proc.stdout, proc.stderr), ("", ""))

    def test_wrong_passphrase_and_missing_bundle(self):
        with self.assertRaisesRegex(bridge_secrets.BridgeSecretsError, "gagal didekripsi") as raised:
            bridge_secrets.bridge_environment(self.bundle, secrets.token_hex(9))
        self.assertNotIn(self.value, str(raised.exception))
        with self.assertRaisesRegex(bridge_secrets.BridgeSecretsError, "tidak ditemukan"):
            bridge_secrets.bridge_environment(self.root / "missing", self.passphrase)


if __name__ == "__main__":
    unittest.main()
