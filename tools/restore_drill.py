#!/usr/bin/env python3
"""Alat uji pemulihan rumah ACE dari repo lokal + kustodi fixture dengan timer per fase (AG36).

Kenapa: memastikan kemampuan memulihkan rumah kedua (repo, berkas kustodi, serta
rantai hash cognitive memory) dapat diverifikasi end-to-end di direktori tiruan
sebelum krisis nyata. Mode live terkunci aman secara bawaan tanpa flag `--execute`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any


SCHEMA = "ace.restore-drill.v1"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(65_536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def verify_memory_jsonl_chain(memory_path: Path) -> tuple[bool, int, str]:
    """Verifikasi keutuhan rantai hash `memory.jsonl` sesuai format CognitiveMemory."""
    if not memory_path.is_file():
        return False, 0, "memory_file_missing"
    prev = "GENESIS"
    count = 0
    for idx, line in enumerate(memory_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            return False, count, f"invalid_json_line:{idx}"
        if not isinstance(entry, dict) or entry.get("prev") != prev:
            return False, count, f"prev_mismatch_line:{idx}"
        payload = json.dumps(
            {"prev": prev, "event": entry.get("event")},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        expected_hash = hashlib.sha256(payload).hexdigest()
        if entry.get("hash") != expected_hash:
            return False, count, f"hash_mismatch_line:{idx}"
        prev = expected_hash
        count += 1
    return True, count, "ok"


def run_fixture_restore_drill(
    *,
    repo_source: Path,
    custody_dir: Path,
    manifest_path: Path,
    target_dir: Path,
    memory_rel: str = "memory/memory.jsonl",
) -> dict[str, Any]:
    """Bangun rumah tiruan dari repo Git lokal + kustodi fixture dan verifikasi tiap fase."""
    if not repo_source.is_dir():
        raise ValueError(f"Sumber repo lokal tidak ditemukan: {repo_source}")
    if not custody_dir.is_dir():
        raise ValueError(f"Direktori kustodi tidak ditemukan: {custody_dir}")
    if not manifest_path.is_file():
        raise ValueError(f"Manifes kustodi tidak ditemukan: {manifest_path}")
    if target_dir.exists() and any(target_dir.iterdir()):
        raise ValueError(f"Direktori target drill wajib kosong: {target_dir}")

    target_dir.mkdir(parents=True, exist_ok=True)
    phases: list[dict[str, Any]] = []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("files") if isinstance(manifest, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError("Manifes kustodi wajib memiliki daftar 'files' tak-kosong.")

    # Fase 1: Clone repo lokal
    t0 = time.perf_counter()
    target_repo = target_dir / "repo"
    proc = subprocess.run(
        ["git", "clone", "-q", "--local", str(repo_source), str(target_repo)],
        capture_output=True,
        text=True,
        check=False,
    )
    clone_ok = proc.returncode == 0 and (target_repo / ".git").exists()
    phases.append(
        {
            "phase": "clone_repo",
            "ok": clone_ok,
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 3),
            "detail": "cloned" if clone_ok else (proc.stderr.strip() or "git_clone_failed"),
        }
    )

    # Fase 2: Pulihkan berkas kustodi ke rumah tiruan
    t1 = time.perf_counter()
    target_custody = target_dir / "custody"
    target_custody.mkdir(parents=True, exist_ok=True)
    copied = 0
    copy_errors: list[str] = []
    for item in entries:
        rel = str(item.get("path") or "")
        src_file = custody_dir / rel
        dst_file = target_custody / rel
        if not rel or ".." in Path(rel).parts or Path(rel).is_absolute():
            copy_errors.append(f"invalid_path:{rel}")
            continue
        if not src_file.is_file():
            copy_errors.append(f"source_missing:{rel}")
            continue
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)
        copied += 1
    phases.append(
        {
            "phase": "restore_custody",
            "ok": len(copy_errors) == 0,
            "elapsed_ms": round((time.perf_counter() - t1) * 1000, 3),
            "detail": {"copied_files": copied, "errors": copy_errors},
        }
    )

    # Fase 3: Verifikasi kehadiran dan hash SHA-256 kustodi
    t2 = time.perf_counter()
    file_results: list[dict[str, str]] = []
    hashes_ok = True
    for item in entries:
        rel = str(item.get("path") or "")
        expected_sha = str(item.get("sha256") or "")
        dst_file = target_custody / rel
        if not dst_file.is_file():
            file_results.append({"path": rel, "status": "hilang"})
            hashes_ok = False
        else:
            actual_sha = _sha256_file(dst_file)
            if actual_sha != expected_sha:
                file_results.append({"path": rel, "status": "hash-berbeda"})
                hashes_ok = False
            else:
                file_results.append({"path": rel, "status": "ok"})
    phases.append(
        {
            "phase": "verify_custody_hashes",
            "ok": hashes_ok,
            "elapsed_ms": round((time.perf_counter() - t2) * 1000, 3),
            "detail": {"files": file_results},
        }
    )

    # Fase 4: Verifikasi rantai hash cognitive memory
    t3 = time.perf_counter()
    mem_ok, mem_events, mem_reason = verify_memory_jsonl_chain(target_custody / memory_rel)
    phases.append(
        {
            "phase": "verify_memory_chain",
            "ok": mem_ok,
            "elapsed_ms": round((time.perf_counter() - t3) * 1000, 3),
            "detail": {"events_verified": mem_events, "reason": mem_reason},
        }
    )

    all_passed = all(p["ok"] for p in phases)
    return {
        "schema": SCHEMA,
        "mode": "fixture",
        "executed": True,
        "all_passed": all_passed,
        "total_elapsed_ms": round(sum(p["elapsed_ms"] for p in phases), 3),
        "phases": phases,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("fixture", "live"), default="live")
    parser.add_argument("--execute", action="store_true", help="Wajib disetel eksplisit untuk mode live.")
    parser.add_argument("--repo", type=Path, help="Repo git lokal sumber.")
    parser.add_argument("--custody", type=Path, help="Direktori kustodi fixture.")
    parser.add_argument("--manifest", type=Path, help="Manifes JSON daftar {path, sha256}.")
    parser.add_argument("--target", type=Path, help="Direktori target rumah tiruan.")
    parser.add_argument("--memory-rel", default="memory/memory.jsonl")
    args = parser.parse_args(argv)

    if args.mode == "live" and not args.execute:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "mode": "live",
                    "executed": False,
                    "status": "dry_run_no_execute",
                    "reason": "Mode live tidak mengeksekusi apa pun tanpa flag --execute.",
                },
                indent=2,
            )
        )
        return 0

    if args.mode == "live":
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "mode": "live",
                    "executed": False,
                    "status": "blocked_operator_required",
                    "reason": "Pemulihan live hanya boleh dijalankan oleh operator manusia.",
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    if not (args.repo and args.custody and args.manifest and args.target):
        parser.error("Mode fixture wajib menyertakan --repo, --custody, --manifest, dan --target.")
    try:
        report = run_fixture_restore_drill(
            repo_source=args.repo,
            custody_dir=args.custody,
            manifest_path=args.manifest,
            target_dir=args.target,
            memory_rel=args.memory_rel,
        )
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
