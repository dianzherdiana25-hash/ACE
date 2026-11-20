#!/usr/bin/env python3
"""Buat penanda preflight cutover agar laporan hanya memuat nama entri bundel.

CLI membaca passphrase lewat ACE_BUNDLE_PASSPHRASE. Keluaran JSON dapat
diberikan ke bridge_home --bundle-manifest. Penanda memeriksa kehadiran
entri dan tidak mengukur kelayakan credential untuk panggilan organ.
--diff MANIFEST_LAMA mencetak nama added, removed, dan unchanged. Tanpa
perubahan, added dan removed kosong. Preflight tetap memakai mode biasa.
"""
import argparse
import json
import os
from pathlib import Path

if __package__:
    from . import secrets_bundle
else:
    import secrets_bundle


def build_manifest(bundle_dir: Path, passphrase: str) -> dict:
    if (not isinstance(passphrase, str) or not passphrase or "\n" in passphrase
            or "\r" in passphrase or len(passphrase.encode("utf-8", errors="replace")) > 1024):
        raise ValueError("Passphrase bundel absen atau tidak sah.")
    try:
        names = sorted(secrets_bundle._load_values(passphrase, bundle_dir)["values"])
    except (OSError, ValueError, TypeError, KeyError, AttributeError, secrets_bundle.BundleError):
        raise ValueError("Bundel gagal didekripsi atau tidak sah.") from None
    if any(not secrets_bundle.NAME_RE.fullmatch(name) for name in names):
        raise ValueError("Bundel memuat nama entri yang tidak sah.")
    return {"schema": secrets_bundle.SCHEMA_MANIFEST,
            "entries": [{"name": name} for name in names]}


def _entry_names(manifest):
    if (not isinstance(manifest, dict) or manifest.get("schema") != secrets_bundle.SCHEMA_MANIFEST
            or not isinstance(manifest.get("entries"), list)):
        raise ValueError("Format manifest penanda tidak sah.")
    names = set()
    for entry in manifest["entries"]:
        name = entry.get("name") if isinstance(entry, dict) else None
        if not isinstance(name, str) or not secrets_bundle.NAME_RE.fullmatch(name) or name in names:
            raise ValueError("Nama entri manifest penanda tidak sah atau ganda.")
        names.add(name)
    return names


def diff_manifests(old, new):
    before, after = _entry_names(old), _entry_names(new)
    return {"added": sorted(after - before), "removed": sorted(before - after),
            "unchanged": sorted(before & after)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--diff", type=Path, metavar="MANIFEST_LAMA")
    args = parser.parse_args(argv)
    try:
        manifest = build_manifest(args.bundle, os.environ.get("ACE_BUNDLE_PASSPHRASE"))
    except ValueError as exc:
        parser.exit(2, f"Error: {exc}\n")
    if args.diff is not None:
        try:
            old = json.loads(args.diff.read_text(encoding="utf-8"))
            manifest = diff_manifests(old, manifest)
        except (OSError, ValueError):
            parser.exit(2, "Error: manifest penanda lama tidak dapat dibaca atau tidak sah.\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
