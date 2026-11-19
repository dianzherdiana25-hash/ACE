"""Tests for tools/secrets_bundle.py — the encrypted secrets bundle.

Every test runs the real CLI against a throwaway directory with the
real gpg binary; the passphrase comes from the test environment and
the S2K count is lowered to the enforced floor for speed. No real
secret ever appears here: the canary value is a fixed fake string,
and one test asserts it appears in NEITHER the manifest nor the
ciphertext bytes.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "secrets_bundle.py"
PASSPHRASE = "test-passphrase-bundel-ace"
WRONG = "passphrase-yang-salah"
CANARY = "FAKE-SECRET-CANARY-0123456789"


def _env(passphrase: str = PASSPHRASE) -> dict:
    env = dict(os.environ)
    env["ACE_BUNDLE_PASSPHRASE"] = passphrase
    env["ACE_BUNDLE_S2K_COUNT"] = "65536"
    return env


def _run(base: Path, *args: str, passphrase: str = PASSPHRASE,
         stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(TOOL), "--dir", str(base), *args],
        input=stdin, capture_output=True, text=True, env=_env(passphrase),
    )


class TestSecretsBundle(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name) / "secrets"
        proc = _run(self.base, "init")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _add_canary(self, name: str = "contoh-api") -> None:
        proc = _run(self.base, "add", name, "--service", "contoh",
                    "--value-stdin", stdin=CANARY + "\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_init_creates_bundle_and_manifest(self) -> None:
        self.assertTrue((self.base / "bundle.gpg").is_file())
        manifest = json.loads((self.base / "manifest.json").read_text("utf-8"))
        self.assertEqual(manifest["schema"], "ace.secrets-bundle-manifest.v1")
        self.assertEqual(manifest["entries"], [])
        proc = _run(self.base, "verify")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("0 entri", proc.stdout)

    def test_init_refuses_overwrite(self) -> None:
        proc = _run(self.base, "init")
        self.assertNotEqual(proc.returncode, 0)

    def test_add_get_roundtrip(self) -> None:
        self._add_canary()
        proc = _run(self.base, "get", "contoh-api")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, CANARY)
        proc = _run(self.base, "verify")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("1 entri", proc.stdout)

    def test_value_appears_nowhere_in_plaintext(self) -> None:
        self._add_canary()
        manifest_bytes = (self.base / "manifest.json").read_bytes()
        bundle_bytes = (self.base / "bundle.gpg").read_bytes()
        self.assertNotIn(CANARY.encode(), manifest_bytes)
        self.assertNotIn(CANARY.encode(), bundle_bytes)
        self.assertNotIn(PASSPHRASE.encode(), manifest_bytes)
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        self.assertEqual(manifest["entries"][0]["name"], "contoh-api")
        self.assertEqual(manifest["entries"][0]["service"], "contoh")

    def test_list_shows_names_not_values(self) -> None:
        self._add_canary()
        proc = _run(self.base, "list")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("contoh-api", proc.stdout)
        self.assertNotIn(CANARY, proc.stdout)

    def test_wrong_passphrase_fails_closed(self) -> None:
        self._add_canary()
        for args in (("verify",), ("get", "contoh-api")):
            proc = _run(self.base, *args, passphrase=WRONG)
            self.assertNotEqual(proc.returncode, 0, args)
            self.assertNotIn(CANARY, proc.stdout)

    def test_tampered_bundle_fails_closed(self) -> None:
        self._add_canary()
        bundle = self.base / "bundle.gpg"
        raw = bytearray(bundle.read_bytes())
        raw[len(raw) // 2] ^= 0xFF
        bundle.write_bytes(bytes(raw))
        proc = _run(self.base, "verify")
        self.assertNotEqual(proc.returncode, 0)
        proc = _run(self.base, "get", "contoh-api")
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn(CANARY, proc.stdout)

    def test_get_missing_name_fails(self) -> None:
        proc = _run(self.base, "get", "tidak-ada")
        self.assertNotEqual(proc.returncode, 0)

    def test_add_duplicate_refused_then_force_replaces(self) -> None:
        self._add_canary()
        proc = _run(self.base, "add", "contoh-api", "--value-stdin",
                    stdin="nilai-lain\n")
        self.assertNotEqual(proc.returncode, 0)
        proc = _run(self.base, "add", "contoh-api", "--force",
                    "--value-stdin", stdin="nilai-baru\n")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        proc = _run(self.base, "get", "contoh-api")
        self.assertEqual(proc.stdout, "nilai-baru")

    def test_remove(self) -> None:
        self._add_canary()
        proc = _run(self.base, "remove", "contoh-api")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        proc = _run(self.base, "get", "contoh-api")
        self.assertNotEqual(proc.returncode, 0)
        proc = _run(self.base, "verify")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_bad_name_rejected(self) -> None:
        for bad in ("../lari", "Spasi Nama", "-awal", "UPPER"):
            proc = _run(self.base, "add", bad, "--value-stdin", stdin="x\n")
            self.assertNotEqual(proc.returncode, 0, bad)

    def test_rotate_refused_in_env_mode(self) -> None:
        # rotate-passphrase is interactive by design: the new passphrase
        # must never travel through the environment.
        proc = _run(self.base, "rotate-passphrase")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("prompt", proc.stderr)

    def test_passphrase_never_in_gpg_argv(self) -> None:
        sys.path.insert(0, str(REPO_ROOT))
        from tools import secrets_bundle as sb

        captured: list[list[str]] = []

        class _Done:
            returncode = 0
            stdout = b""
            stderr = b""

        real_run = sb.subprocess.run

        def fake_run(cmd, **kwargs):
            captured.append(list(cmd))
            return _Done()

        sb.subprocess.run = fake_run
        try:
            sb._gpg(PASSPHRASE, ["--symmetric", "--output", "x"], b"data")
        finally:
            sb.subprocess.run = real_run
        self.assertTrue(captured)
        for cmd in captured:
            for part in cmd:
                self.assertNotIn(PASSPHRASE, part)


if __name__ == "__main__":
    unittest.main()
