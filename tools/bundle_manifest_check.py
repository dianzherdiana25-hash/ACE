#!/usr/bin/env python3
"""Periksa kelengkapan nama entri manifest bundle terhadap kebutuhan bridge_home tanpa membaca nilai.

Kenapa: operator perlu memverifikasi sebelum cutover apakah manifest publik bundle
memuat seluruh nama entri wajib (dan mana opsional atau nama asing/tak dikenal)
tanpa pernah membuka bundle terenkripsi ataupun menyertakan nilai apa pun di laporan.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

if __package__:
    from .bridge_home import BUNDLE_MANIFEST_SCHEMA, REQUIRED_ENTRY_NAMES
    from .bridge_secrets import _BINDINGS
else:
    from bridge_home import BUNDLE_MANIFEST_SCHEMA, REQUIRED_ENTRY_NAMES
    from bridge_secrets import _BINDINGS


SCHEMA = "ace.bundle-manifest-check.v1"
OPTIONAL_ENTRY_NAMES = tuple(
    name for name in _BINDINGS if name not in REQUIRED_ENTRY_NAMES
)


class BundleManifestCheckError(ValueError):
    """Kesalahan pembacaan atau skema manifest bundle."""


def check_bundle_manifest(
    manifest_path: Path,
    *,
    required_names: tuple[str, ...] = REQUIRED_ENTRY_NAMES,
    optional_names: tuple[str, ...] = OPTIONAL_ENTRY_NAMES,
) -> dict[str, Any]:
    """Bandingkan nama entri manifest dengan himpunan wajib dan opsional bridge_home.

    Hanya field `name` yang diperiksa dan dilaporkan; seluruh nilai atau metadata
    tambahan diabaikan dan tidak pernah muncul di laporan.
    """
    try:
        raw = manifest_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise BundleManifestCheckError(f"Manifest tidak terbaca atau bukan JSON sah: {type(exc).__name__}") from None

    if (
        not isinstance(data, dict)
        or data.get("schema") != BUNDLE_MANIFEST_SCHEMA
        or not isinstance(data.get("entries"), list)
    ):
        raise BundleManifestCheckError(f"Skema manifest wajib {BUNDLE_MANIFEST_SCHEMA} dengan daftar entries.")

    seen_names: list[str] = []
    duplicate_names: set[str] = set()
    seen_set: set[str] = set()
    for idx, entry in enumerate(data["entries"], 1):
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not entry["name"].strip():
            raise BundleManifestCheckError(f"Entri manifest ke-{idx} tidak memiliki field 'name' yang sah.")
        name = entry["name"]
        if name in seen_set:
            duplicate_names.add(name)
        else:
            seen_set.add(name)
            seen_names.append(name)

    required_set = frozenset(required_names)
    optional_set = frozenset(optional_names)
    known_set = required_set | optional_set

    present_required = [name for name in required_names if name in seen_set]
    missing_required = [name for name in required_names if name not in seen_set]
    present_optional = [name for name in optional_names if name in seen_set]
    missing_optional = [name for name in optional_names if name not in seen_set]
    unexpected_names = sorted(name for name in seen_set if name not in known_set)
    duplicates_sorted = sorted(duplicate_names)

    has_all_required = len(missing_required) == 0
    is_clean = has_all_required and not unexpected_names and not duplicates_sorted
    if not has_all_required:
        status = "missing_required"
    elif unexpected_names or duplicates_sorted:
        status = "unexpected_or_duplicate_entries"
    else:
        status = "complete"

    return {
        "schema": SCHEMA,
        "status": status,
        "has_all_required": has_all_required,
        "clean": is_clean,
        "required_expected": list(required_names),
        "optional_expected": list(optional_names),
        "present_required": present_required,
        "missing_required": missing_required,
        "present_optional": present_optional,
        "missing_optional": missing_optional,
        "unexpected_names": unexpected_names,
        "duplicate_names": duplicates_sorted,
        "entry_count": len(seen_names),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Pemeriksaan Kelengkapan Nama Entri Manifest Bundle",
        "",
        f"- Schema: `{report['schema']}`",
        f"- Status: **{report['status']}** (`has_all_required={report['has_all_required']}`, `clean={report['clean']}`)",
        f"- Entri wajib ada ({len(report['present_required'])}/{len(report['required_expected'])}): "
        + (", ".join(f"`{n}`" for n in report["present_required"]) or "-"),
        f"- Entri wajib hilang ({len(report['missing_required'])}): "
        + (", ".join(f"`{n}`" for n in report["missing_required"]) or "-"),
        f"- Entri opsional ada ({len(report['present_optional'])}/{len(report['optional_expected'])}): "
        + (", ".join(f"`{n}`" for n in report["present_optional"]) or "-"),
        f"- Nama asing / tidak dikenal ({len(report['unexpected_names'])}): "
        + (", ".join(f"`{n}`" for n in report["unexpected_names"]) or "-"),
        f"- Nama duplikat ({len(report['duplicate_names'])}): "
        + (", ".join(f"`{n}`" for n in report["duplicate_names"]) or "-"),
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path, help="Path berkas manifest.json publik bundle.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--strict", action="store_true", help="Keluar 1 bila ada wajib hilang, nama asing, atau duplikat.")
    args = parser.parse_args(argv)
    try:
        report = check_bundle_manifest(args.manifest)
    except BundleManifestCheckError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(render_markdown(report) if args.format == "markdown" else json.dumps(report, indent=2), end="\n")
    if args.strict and not report["clean"]:
        return 1
    return 0 if report["has_all_required"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
