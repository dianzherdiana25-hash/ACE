#!/usr/bin/env python3
"""Verifikator manifes kustodi: cek kehadiran dan SHA-256 setiap berkas kustodi (AG38).

Kenapa: memastikan paket kustodi yang disimpan atau dipulihkan ke rumah kedua
tidak kehilangan satu pun berkas maupun mengalami modifikasi isi diam-diam sebelum
dipakai sebagai landasan pemulihan rumah atau verifikasi identitas.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


SCHEMA = "ace.custody-manifest-check.v1"
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(65_536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def verify_custody_manifest(manifest_path: Path, root_dir: Path) -> dict[str, Any]:
    """Verifikasi daftar `{path, sha256}` di manifes terhadap berkas di `root_dir`."""
    resolved_root = Path(root_dir).resolve()
    if not resolved_root.is_dir():
        raise ValueError(f"Direktori kustodi tidak ditemukan: {root_dir}")
    if not Path(manifest_path).is_file():
        raise ValueError(f"Berkas manifes kustodi tidak ditemukan: {manifest_path}")

    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if isinstance(manifest, dict) and isinstance(manifest.get("files"), list):
        entries = manifest["files"]
    elif isinstance(manifest, dict) and isinstance(manifest.get("entries"), list):
        entries = manifest["entries"]
    else:
        raise ValueError("Manifes kustodi wajib berupa objek JSON dengan daftar 'files' atau 'entries'.")

    seen_paths: set[str] = set()
    results: list[dict[str, Any]] = []
    counts = {"ok": 0, "hilang": 0, "hash-berbeda": 0}

    for idx, entry in enumerate(entries, 1):
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or not entry["path"].strip():
            raise ValueError(f"Entri manifes ke-{idx} tidak memiliki 'path' string yang sah.")
        rel_str = entry["path"]
        rel = Path(rel_str)
        if rel.is_absolute() or ".." in rel.parts or rel_str in seen_paths:
            raise ValueError(f"Path entri manifes tidak sah atau duplikat: {rel_str}")
        seen_paths.add(rel_str)

        expected = entry.get("sha256")
        if not isinstance(expected, str) or not _SHA256_RE.fullmatch(expected):
            raise ValueError(f"SHA-256 entri '{rel_str}' tidak sah.")
        expected_norm = expected.lower()

        target = resolved_root / rel
        if target.is_symlink():
            target_resolved = target.resolve()
            if not target_resolved.is_relative_to(resolved_root):
                raise ValueError(f"Symlink keluar batas root kustodi: {rel_str}")
        if not target.is_file():
            counts["hilang"] += 1
            results.append(
                {
                    "path": rel_str,
                    "status": "hilang",
                    "expected_sha256": expected_norm,
                    "actual_sha256": None,
                }
            )
            continue

        actual = _sha256_file(target)
        if actual != expected_norm:
            counts["hash-berbeda"] += 1
            results.append(
                {
                    "path": rel_str,
                    "status": "hash-berbeda",
                    "expected_sha256": expected_norm,
                    "actual_sha256": actual,
                }
            )
        else:
            counts["ok"] += 1
            results.append(
                {
                    "path": rel_str,
                    "status": "ok",
                    "expected_sha256": expected_norm,
                    "actual_sha256": actual,
                }
            )

    all_ok = counts["hilang"] == 0 and counts["hash-berbeda"] == 0
    return {
        "schema": SCHEMA,
        "all_ok": all_ok,
        "summary": {
            "total_entries": len(results),
            **counts,
        },
        "files": results,
    }


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Verifikasi Manifes Kustodi",
        "",
        f"- Schema: `{report['schema']}` (`all_ok={report['all_ok']}`)",
        f"- Total: **{s['total_entries']}** (`ok={s['ok']}`, `hilang={s['hilang']}`, `hash-berbeda={s['hash-berbeda']}`)",
        "",
        "| Berkas | Status |",
        "| --- | --- |",
    ]
    for item in report["files"]:
        lines.append(f"| `{item['path']}` | `{item['status']}` |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path, help="Berkas JSON manifes kustodi.")
    parser.add_argument("--root", required=True, type=Path, help="Direktori akar berkas kustodi.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    try:
        report = verify_custody_manifest(args.manifest, args.root)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(render_markdown(report) if args.format == "markdown" else json.dumps(report, indent=2, ensure_ascii=False), end="\n")
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
