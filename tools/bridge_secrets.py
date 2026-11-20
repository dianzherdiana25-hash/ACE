#!/usr/bin/env python3
"""Siapkan env anak bridge agar credential tidak perlu masuk berkas plaintext.

Bundel memetakan groq-api-key → GROQ_API_KEY, gemini-api-key → GEMINI_API_KEY
dan gonka-api-key → GONKA_API_KEY. Bucket gemini2-api-key dan gemini3-api-key
opsional memakai GEMINI2_API_KEY serta GEMINI3_API_KEY. Passphrase masuk lewat
ACE_BUNDLE_PASSPHRASE dan dikeluarkan dari env anak. Jalur CLI menyembunyikan
stdout/stderr anak. Program anak harus dipercaya memakai env secara privat.
"""
import argparse
import os
from pathlib import Path
import subprocess

if __package__:
    from . import secrets_bundle
else:
    import secrets_bundle


_BINDINGS = {"groq-api-key": "GROQ_API_KEY", "gemini-api-key": "GEMINI_API_KEY",
             "gonka-api-key": "GONKA_API_KEY", "gemini2-api-key": "GEMINI2_API_KEY",
             "gemini3-api-key": "GEMINI3_API_KEY"}
_REQUIRED = ("groq-api-key", "gemini-api-key", "gonka-api-key")


class BridgeSecretsError(ValueError):
    """Galat tetap tanpa isi credential."""


def bridge_environment(bundle_dir: Path, passphrase: str, *, environ=None) -> dict:
    if not (bundle_dir / "bundle.gpg").is_file():
        raise BridgeSecretsError("Bundel bridge tidak ditemukan.")
    if (not isinstance(passphrase, str) or not passphrase or "\n" in passphrase
            or len(passphrase.encode("utf-8")) > 1024):
        raise BridgeSecretsError("Passphrase bundel absen atau tidak sah.")
    try:
        values = secrets_bundle._load_values(passphrase, bundle_dir)["values"]
    except (OSError, ValueError, TypeError, KeyError, AttributeError, secrets_bundle.BundleError):
        raise BridgeSecretsError("Bundel bridge gagal didekripsi atau tidak sah.") from None

    for key in _REQUIRED:
        if key not in values:
            raise BridgeSecretsError("Bundel belum memuat semua entri wajib bridge.")
    child_env = dict(os.environ if environ is None else environ)
    child_env.pop("ACE_BUNDLE_PASSPHRASE", None)
    for key, target in _BINDINGS.items():
        child_env.pop(target, None)
        if key in values:
            value = values[key]
            if not isinstance(value, str) or not value.strip() or "\0" in value:
                raise BridgeSecretsError("Bundel memuat entri bridge yang tidak sah.")
            child_env[target] = value
    return child_env


def rotate_bundle_passphrase(bundle_dir: Path, old_passphrase: str, new_passphrase: str) -> tuple[str, ...]:
    """Enkripsi ulang bundel bridge dengan passphrase baru tanpa pernah mencetak nilai entri."""
    for label, pw in (("lama", old_passphrase), ("baru", new_passphrase)):
        if (not isinstance(pw, str) or not pw or "\n" in pw
                or len(pw.encode("utf-8")) > 1024):
            raise BridgeSecretsError(f"Passphrase {label} bundel absen atau tidak sah.")
    if old_passphrase == new_passphrase:
        raise BridgeSecretsError("Passphrase baru bundel wajib berbeda dari passphrase lama.")
    # Pastikan bundel sah untuk bridge dengan passphrase lama terlebih dahulu
    bridge_environment(bundle_dir, old_passphrase, environ={})
    try:
        data = secrets_bundle._load_values(old_passphrase, bundle_dir)
        names_before = tuple(sorted(data["values"].keys()))
        secrets_bundle._store_values(new_passphrase, bundle_dir, data)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, secrets_bundle.BundleError):
        raise BridgeSecretsError("Rotasi passphrase bundel bridge gagal.") from None
    return names_before


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Perintah anak setelah --.")
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("Perintah anak wajib diberikan.")
    try:
        env = bridge_environment(args.bundle, os.environ.get("ACE_BUNDLE_PASSPHRASE"))
        result = subprocess.run(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except BridgeSecretsError as exc:
        parser.exit(2, f"Error: {exc}\n")
    except (OSError, ValueError):
        parser.exit(2, "Error: proses anak bridge tidak dapat dimulai.\n")
    if result.returncode:
        parser.exit(1, "Error: proses anak bridge gagal.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
