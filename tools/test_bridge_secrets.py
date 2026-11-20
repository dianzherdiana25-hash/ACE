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

    def test_passphrase_rotation_rehearsal_old_fails_new_succeeds_names_identical_no_leak(self):
        script = Path(__file__).with_name("bridge_secrets.py")
        rot_dir = self.root / "rotation_bundle"
        rot_dir.mkdir()
        old_pw = secrets.token_hex(14)
        new_pw = secrets.token_hex(14)
        entry_values = {
            "groq-api-key": secrets.token_hex(24),
            "gemini-api-key": secrets.token_hex(24),
            "gonka-api-key": secrets.token_hex(24),
            "gemini2-api-key": secrets.token_hex(24),
        }
        secrets_bundle._store_values(old_pw, rot_dir, {
            "schema": secrets_bundle.SCHEMA_BUNDLE,
            "values": dict(entry_values),
        })
        secrets_bundle._save_manifest(rot_dir, {
            "schema": secrets_bundle.SCHEMA_MANIFEST,
            "created_at": "2026-11-19T00:00:00Z",
            "entries": [
                {"name": name, "service": name.split("-")[0], "note": "", "updated_at": "2026-11-19T00:00:00Z"}
                for name in entry_values
            ],
        })

        names_before = tuple(sorted(
            secrets_bundle._load_values(old_pw, rot_dir)["values"].keys()
        ))
        manifest_names_before = tuple(
            e["name"] for e in secrets_bundle._load_manifest(rot_dir)["entries"]
        )
        self.assertEqual(names_before, manifest_names_before)

        rotated_names = bridge_secrets.rotate_bundle_passphrase(rot_dir, old_pw, new_pw)
        self.assertEqual(rotated_names, names_before)

        # Passphrase lama wajib gagal baik lewat API maupun CLI
        with self.assertRaisesRegex(bridge_secrets.BridgeSecretsError, "gagal didekripsi") as old_err:
            bridge_secrets.bridge_environment(rot_dir, old_pw, environ={})
        old_cli = subprocess.run(
            [sys.executable, str(script), "--bundle", str(rot_dir), "--", sys.executable, "-c", "pass"],
            env={**os.environ, "ACE_BUNDLE_PASSPHRASE": old_pw},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(old_cli.returncode, 2)

        # Passphrase baru wajib berhasil dan daftar nama entri identik
        names_after = tuple(sorted(
            secrets_bundle._load_values(new_pw, rot_dir)["values"].keys()
        ))
        manifest_names_after = tuple(
            e["name"] for e in secrets_bundle._load_manifest(rot_dir)["entries"]
        )
        self.assertEqual(names_after, names_before)
        self.assertEqual(manifest_names_after, manifest_names_before)

        new_env = bridge_secrets.bridge_environment(rot_dir, new_pw, environ={})
        self.assertEqual(new_env["GROQ_API_KEY"], entry_values["groq-api-key"])
        self.assertEqual(new_env["GEMINI_API_KEY"], entry_values["gemini-api-key"])
        self.assertEqual(new_env["GONKA_API_KEY"], entry_values["gonka-api-key"])
        self.assertEqual(new_env["GEMINI2_API_KEY"], entry_values["gemini2-api-key"])

        new_cli = subprocess.run(
            [sys.executable, str(script), "--bundle", str(rot_dir), "--", sys.executable, "-c", "pass"],
            env={**os.environ, "ACE_BUNDLE_PASSPHRASE": new_pw},
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual((new_cli.stdout, new_cli.stderr), ("", ""))

        # Nilai entri tidak pernah ditulis ke manifest maupun ke keluaran
        manifest_raw = (rot_dir / "manifest.json").read_text(encoding="utf-8")
        for secret_val in (*entry_values.values(), old_pw, new_pw):
            self.assertNotIn(secret_val, str(old_err.exception))
            self.assertNotIn(secret_val, old_cli.stdout)
            self.assertNotIn(secret_val, old_cli.stderr)
            self.assertNotIn(secret_val, new_cli.stdout)
            self.assertNotIn(secret_val, new_cli.stderr)
            self.assertNotIn(secret_val, manifest_raw)


if __name__ == "__main__":
    unittest.main()
