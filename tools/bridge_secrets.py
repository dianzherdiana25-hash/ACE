#!/usr/bin/env python3
"""Siapkan env anak bridge agar credential tidak perlu masuk berkas plaintext.

Bundel memetakan groq-api-key → GROQ_API_KEY, gemini-api-key → GEMINI_API_KEY
dan gonka-api-key → GONKA_API_KEY. Bucket gemini2-api-key dan gemini3-api-key
opsional memakai GEMINI2_API_KEY serta GEMINI3_API_KEY. Passphrase masuk lewat
ACE_BUNDLE_PASSPHRASE dan dikeluarkan dari env anak. Jalur CLI menyembunyikan
stdout/stderr anak. Program anak harus dipercaya memakai env secara privat.
"""
import argparse
import json
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


class _DuplicateEntryError(ValueError):
    pass


class BridgeSecretsError(ValueError):
    """Galat tetap tanpa isi credential, dengan kode taksonomi terstruktur."""

    def __init__(self, message: str, *, code: str = "bridge_secrets_error") -> None:
        super().__init__(message)
        self.code = code


def _no_duplicate_object_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise _DuplicateEntryError(key)
        obj[key] = value
    return obj


def _check_manifest_if_present(bundle_dir: Path) -> None:
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.is_file():
        return
    try:
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8"),
            object_pairs_hook=_no_duplicate_object_pairs,
        )
    except _DuplicateEntryError:
        raise BridgeSecretsError(
            "Bundel bridge memuat nama entri duplikat.",
            code="duplicate_entry",
        ) from None
    except (OSError, ValueError):
        raise BridgeSecretsError(
            "Skema bundel bridge tidak sah.",
            code="invalid_schema",
        ) from None
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != secrets_bundle.SCHEMA_MANIFEST
        or not isinstance(manifest.get("entries"), list)
    ):
        raise BridgeSecretsError(
            "Skema bundel bridge tidak sah.",
            code="invalid_schema",
        )
    seen_names: set[str] = set()
    for entry in manifest["entries"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise BridgeSecretsError(
                "Skema bundel bridge tidak sah.",
                code="invalid_schema",
            )
        name = entry["name"]
        if name in seen_names:
            raise BridgeSecretsError(
                "Bundel bridge memuat nama entri duplikat.",
                code="duplicate_entry",
            )
        seen_names.add(name)


def bridge_environment(bundle_dir: Path, passphrase: str, *, environ=None) -> dict:
    bundle_path = bundle_dir / "bundle.gpg"
    if not bundle_path.is_file():
        raise BridgeSecretsError("Bundel bridge tidak ditemukan.", code="bundle_missing")
    if (not isinstance(passphrase, str) or not passphrase or "\n" in passphrase
            or len(passphrase.encode("utf-8")) > 1024):
        raise BridgeSecretsError("Passphrase bundel absen atau tidak sah.", code="invalid_passphrase")
    try:
        if bundle_path.stat().st_size == 0:
            raise BridgeSecretsError("Bundel bridge kosong.", code="bundle_empty")
    except OSError:
        raise BridgeSecretsError("Bundel bridge tidak ditemukan.", code="bundle_missing") from None

    _check_manifest_if_present(bundle_dir)

    try:
        raw = secrets_bundle._decrypt(passphrase, bundle_path)
    except (OSError, secrets_bundle.BundleError):
        raise BridgeSecretsError(
            "Bundel bridge gagal didekripsi: passphrase salah atau ciphertext rusak.",
            code="wrong_passphrase",
        ) from None

    if not raw or not raw.strip():
        raise BridgeSecretsError("Bundel bridge kosong.", code="bundle_empty")

    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_object_pairs)
    except _DuplicateEntryError:
        raise BridgeSecretsError(
            "Bundel bridge memuat nama entri duplikat.",
            code="duplicate_entry",
        ) from None
    except (ValueError, UnicodeDecodeError):
        raise BridgeSecretsError("Skema bundel bridge tidak sah.", code="invalid_schema") from None

    if (
        not isinstance(data, dict)
        or data.get("schema") != secrets_bundle.SCHEMA_BUNDLE
        or not isinstance(data.get("values"), dict)
    ):
        raise BridgeSecretsError("Skema bundel bridge tidak sah.", code="invalid_schema")

    values = data["values"]
    if len(values) == 0:
        raise BridgeSecretsError("Bundel bridge kosong.", code="bundle_empty")

    for key in _REQUIRED:
        if key not in values:
            raise BridgeSecretsError(
                "Bundel belum memuat semua entri wajib bridge.",
                code="missing_required_entry",
            )
    child_env = dict(os.environ if environ is None else environ)
    child_env.pop("ACE_BUNDLE_PASSPHRASE", None)
    for key, target in _BINDINGS.items():
        child_env.pop(target, None)
        if key in values:
            value = values[key]
            if not isinstance(value, str) or not value.strip() or "\0" in value:
                raise BridgeSecretsError(
                    "Bundel memuat entri bridge yang tidak sah.",
                    code="invalid_entry_value",
                )
            child_env[target] = value
    return child_env


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
        parser.exit(2, f"Error [{exc.code}]: {exc}\n")
    except (OSError, ValueError):
        parser.exit(2, "Error [child_spawn_failed]: proses anak bridge tidak dapat dimulai.\n")
    if result.returncode:
        parser.exit(1, "Error [child_failed]: proses anak bridge gagal.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
