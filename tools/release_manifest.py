#!/usr/bin/env python3
"""Perakit manifest rilis JSON luring untuk cabang/PR terhadap `main`.

Kenapa modul ini ada:
Sebelum sebuah cabang diajukan sebagai PR atau rilis draf, peninjau perlu
daftar lengkap dan deterministik seluruh berkas berubah beserta `sha256`,
ukuran byte, klasifikasi jalur (`handover` / `evidence` / `lainnya`), serta
peringatan eksplisit bila ada berkas yang berada di luar allowlist program atau
menyentuh jalur sensitif/terlarang. Seluruh data dibaca dari objek Git lokal
(tanpa jaringan dan tanpa mengubah working tree).

Exit code:
- 0: manifest berhasil dibangun (dan tanpa peringatan bila `--fail-on-warnings`)
- 1: `--fail-on-warnings` aktif dan ditemukan peringatan jalur
- 2: argumen CLI atau pemeriksaan Git lokal gagal
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any, Sequence

RELEASE_MANIFEST_SCHEMA = "ace.release-manifest.v1"

# Selaras dengan kebijakan allowlist rilis/self-send program (`self_send.py` & `draft_release_preflight.py`).
DEFAULT_ALLOWLIST_PREFIXES: tuple[str, ...] = ("handover/", "evidence/")

# Pola jalur sensitif/terlarang yang selalu memicu peringatan walaupun berada di bawah prefix allowlist.
FORBIDDEN_PATH_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("secrets_or_credentials", re.compile(r"(^|/)(secrets/|.*secret.*|.*credential.*|\.env($|\.)|id_rsa|.*\.pem$|.*\.key$)", re.IGNORECASE)),
    ("private_income_ledger", re.compile(r"(^|/)handover/ledger_penghasilan\.md$|utang_awal", re.IGNORECASE)),
    ("frozen_corpus", re.compile(r"(^|/)handover/.*(?:_corpus_|_beku).*\.jsonl$", re.IGNORECASE)),
    ("evo0007_instrument", re.compile(r"(^|/)evidence/evo0007/|(^|/)evo0007_run\.py$", re.IGNORECASE)),
    ("measurement_instrument", re.compile(r"(^|/)code/ace_evaluator/|(^|/)ratification_loop\.py$|(?:abc_v3_scorer|round2_instrument|g\d+_instrument)\.py$", re.IGNORECASE)),
)


class ReleaseManifestError(ValueError):
    """Kesalahan pembacaan Git lokal atau parameter perakit manifest rilis."""


def _run_git(repo_root: Path, *args: str) -> bytes:
    proc = subprocess.run(
        ["git", "--no-replace-objects", "-C", str(repo_root), *args],
        capture_output=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        raise ReleaseManifestError(f"Perintah git gagal ({' '.join(args[:3])}): {stderr or proc.returncode}")
    return proc.stdout


def classify_path(rel_posix: str) -> str:
    """Klasifikasikan jalur berkas ke dalam `handover`, `evidence`, atau `lainnya`."""
    norm = rel_posix.replace("\\", "/").lstrip("./")
    if norm.startswith("handover/"):
        return "handover"
    if norm.startswith("evidence/"):
        return "evidence"
    return "lainnya"


def check_path_policy(
    rel_posix: str,
    *,
    allowlist_prefixes: Sequence[str] = DEFAULT_ALLOWLIST_PREFIXES,
) -> tuple[bool, str | None, list[str]]:
    """Evaluasi apakah jalur mematuhi allowlist program dan bebas pola terlarang."""
    norm = rel_posix.replace("\\", "/").lstrip("./")
    reasons: list[str] = []

    in_allowlist = any(norm.startswith(prefix) for prefix in allowlist_prefixes)
    if not in_allowlist:
        reasons.append(f"di luar allowlist program ({', '.join(allowlist_prefixes)})")

    if any(part.startswith(".") for part in PurePosixPath(norm).parts):
        reasons.append("mengandung segmen tersembunyi (dotfile/dotdir)")

    forbidden_rule: str | None = None
    for rule_name, pattern in FORBIDDEN_PATH_RULES:
        if pattern.search(norm):
            forbidden_rule = rule_name
            reasons.append(f"menyentuh pola sensitif/terlarang ({rule_name})")
            break

    outside_policy = (not in_allowlist) or (forbidden_rule is not None) or any(
        part.startswith(".") for part in PurePosixPath(norm).parts
    )
    return outside_policy, forbidden_rule, reasons


def build_release_manifest(
    repo_root: Path,
    *,
    base_ref: str = "main",
    head_ref: str = "HEAD",
    allowlist_prefixes: Sequence[str] = DEFAULT_ALLOWLIST_PREFIXES,
) -> dict[str, Any]:
    """Bangun JSON manifest rilis deterministik untuk selisih `base_ref...head_ref`."""
    root = repo_root.resolve()
    if not root.is_dir():
        raise ReleaseManifestError(f"Direktori repositori tidak ditemukan: {repo_root}")

    base_sha = _run_git(root, "rev-parse", "--verify", f"{base_ref}^{{commit}}").decode("ascii").strip()
    head_sha = _run_git(root, "rev-parse", "--verify", f"{head_ref}^{{commit}}").decode("ascii").strip()
    merge_base = _run_git(root, "merge-base", base_sha, head_sha).decode("ascii").strip()

    branch_proc = subprocess.run(
        ["git", "-C", str(root), "symbolic-ref", "--short", head_ref],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    branch_name = branch_proc.stdout.strip() if branch_proc.returncode == 0 else head_ref

    raw_diff = _run_git(root, "diff", "--no-renames", "--name-status", "-z", merge_base, head_sha)
    tokens = raw_diff.split(b"\0")
    if tokens and tokens[-1] == b"":
        tokens.pop()
    if len(tokens) % 2 != 0:
        raise ReleaseManifestError("Format keluaran `git diff --name-status -z` tidak terduga.")

    entries: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    class_counts: Counter[str] = Counter()
    total_bytes = 0

    for idx in range(0, len(tokens), 2):
        status = tokens[idx].decode("ascii", errors="replace")
        path = tokens[idx + 1].decode("utf-8", errors="replace")
        classification = classify_path(path)
        class_counts[classification] += 1

        outside_policy, forbidden_rule, policy_reasons = check_path_policy(
            path,
            allowlist_prefixes=allowlist_prefixes,
        )

        if status == "D":
            size_bytes = 0
            sha256_hex: str | None = None
            policy_reasons.append("menghapus berkas dari riwayat cabang")
        else:
            tree_info = _run_git(root, "ls-tree", "-z", head_sha, "--", path)
            if tree_info.startswith(b"120000 "):
                policy_reasons.append("berkas berupa symlink (120000)")
                outside_policy = True
            blob = _run_git(root, "cat-file", "blob", f"{head_sha}:{path}")
            size_bytes = len(blob)
            sha256_hex = hashlib.sha256(blob).hexdigest()
            total_bytes += size_bytes

        if policy_reasons:
            warnings.append(
                {
                    "path": path,
                    "status": status,
                    "classification": classification,
                    "forbidden_rule": forbidden_rule,
                    "reasons": policy_reasons,
                }
            )

        entries.append(
            {
                "path": path,
                "status": status,
                "classification": classification,
                "size_bytes": size_bytes,
                "sha256": sha256_hex,
                "in_allowlist": not outside_policy,
                "forbidden_rule": forbidden_rule,
                "warnings": policy_reasons,
            }
        )

    entries.sort(key=lambda item: item["path"])
    warnings.sort(key=lambda item: item["path"])

    canonical_files = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest_sha256 = hashlib.sha256(canonical_files).hexdigest()

    return {
        "schema": RELEASE_MANIFEST_SCHEMA,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "branch": branch_name,
        "base_sha": base_sha,
        "merge_base_sha": merge_base,
        "head_sha": head_sha,
        "allowlist_prefixes": list(allowlist_prefixes),
        "summary": {
            "changed_file_count": len(entries),
            "total_size_bytes": total_bytes,
            "classification_counts": {
                "handover": class_counts.get("handover", 0),
                "evidence": class_counts.get("evidence", 0),
                "lainnya": class_counts.get("lainnya", 0),
            },
            "warning_count": len(warnings),
            "outside_allowlist_count": sum(1 for e in entries if not e["in_allowlist"]),
        },
        "manifest_sha256": manifest_sha256,
        "warnings": warnings,
        "files": entries,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rakit JSON manifest rilis untuk berkas berubah satu cabang terhadap main."
    )
    parser.add_argument("--repo", type=Path, default=Path("."), help="Direktori repositori Git lokal.")
    parser.add_argument("--base", default="main", help="Ref basis perbandingan (default: main).")
    parser.add_argument("--head", default="HEAD", help="Ref cabang target (default: HEAD).")
    parser.add_argument(
        "--allow-prefix",
        action="append",
        default=None,
        help="Override prefix allowlist (dapat diulang; default: handover/, evidence/).",
    )
    parser.add_argument("--out", type=Path, default=None, help="Simpan manifest JSON ke path ini.")
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Keluar dengan kode 1 bila terdapat peringatan jalur di luar allowlist/terlarang.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    allow_prefixes = tuple(args.allow_prefix) if args.allow_prefix else DEFAULT_ALLOWLIST_PREFIXES
    try:
        manifest = build_release_manifest(
            args.repo,
            base_ref=args.base,
            head_ref=args.head,
            allowlist_prefixes=allow_prefixes,
        )
    except ReleaseManifestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)

    if args.fail_on_warnings and manifest["summary"]["warning_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
