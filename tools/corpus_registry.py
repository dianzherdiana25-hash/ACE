#!/usr/bin/env python3
"""Registri corpus beku di `handover/` beserta deteksi drift (`--check`).

Memindai direktori `handover/` (atau direktori target lain) untuk seluruh
berkas corpus beku (`*corpus*.jsonl`, tidak peka huruf besar/kecil), mencatat
nama relatif POSIX, jumlah baris, ukuran byte, sha256, dan sebaran `task_kind`
ke dalam satu berkas indeks JSON. Mode `--check` membandingkan indeks tersimpan
terhadap keadaan direktori saat ini dan melaporkan setiap drift.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

REGISTRY_SCHEMA = "ace.frozen-corpus-registry.v1"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HANDOVER_DIR = REPO_ROOT / "handover"


class RegistryError(ValueError):
    """Kesalahan masukan, path, atau format indeks registri corpus tidak sah."""


def _sha256_file(path: Path, chunk_size: int = 65536) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        while chunk := fp.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def _is_frozen_corpus_file(path: Path) -> bool:
    return path.suffix.lower() == ".jsonl" and "corpus" in path.name.lower()


def _inspect_corpus(path: Path, root: Path) -> dict[str, Any]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RegistryError(f"Gagal membaca corpus '{path}': {exc}") from exc

    counts: Counter[str] = Counter()
    line_count = 0
    for line_no, raw_line in enumerate(raw_text.splitlines(), start=1):
        if not raw_line.strip():
            raise RegistryError(f"Baris kosong ditemukan pada '{path}' baris {line_no}.")
        try:
            obj = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise RegistryError(f"JSON tidak sah pada '{path}' baris {line_no}: {exc.msg}") from exc
        if not isinstance(obj, dict):
            raise RegistryError(f"Baris '{path}' baris {line_no} wajib berupa objek JSON.")
        tk = obj.get("task_kind")
        tk_label = tk.strip() if isinstance(tk, str) and tk.strip() else "unknown"
        counts[tk_label] += 1
        line_count += 1

    return {
        "name": path.relative_to(root).as_posix(),
        "line_count": line_count,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
        "task_kind_counts": {k: counts[k] for k in sorted(counts)},
    }


def scan_corpora(handover_dir: Path) -> dict[str, Any]:
    """Pindai `handover_dir` dan bangun indeks corpus beku secara deterministik."""
    if not handover_dir.is_dir():
        raise RegistryError(f"Direktori handover tidak ditemukan: {handover_dir}")

    root = handover_dir.resolve()
    candidates: list[Path] = []
    for current_dir, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        filenames.sort()
        cur = Path(current_dir)
        for name in filenames:
            p = cur / name
            if p.is_symlink():
                continue
            if _is_frozen_corpus_file(p):
                candidates.append(p)

    candidates.sort(key=lambda p: p.relative_to(root).as_posix())
    entries = [_inspect_corpus(path, root) for path in candidates]
    return {
        "schema": REGISTRY_SCHEMA,
        "source_dir": root.name,
        "corpus_count": len(entries),
        "corpora": entries,
    }


def check_drift(handover_dir: Path, index_path: Path) -> dict[str, Any]:
    """Bandingkan indeks registri tersimpan terhadap keadaan `handover_dir` kini."""
    if not index_path.is_file():
        raise RegistryError(f"Berkas indeks tidak ditemukan: {index_path}")
    try:
        saved = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RegistryError(f"Gagal membaca indeks '{index_path}': {exc}") from exc

    if not isinstance(saved, dict) or saved.get("schema") != REGISTRY_SCHEMA:
        raise RegistryError("Schema indeks registri tidak sah.")
    saved_list = saved.get("corpora")
    if not isinstance(saved_list, list):
        raise RegistryError("Field 'corpora' pada indeks harus berupa daftar.")

    current = scan_corpora(handover_dir)
    saved_map: dict[str, dict[str, Any]] = {}
    for entry in saved_list:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise RegistryError("Entri indeks corpus tidak sah.")
        saved_map[entry["name"]] = entry

    curr_map = {entry["name"]: entry for entry in current["corpora"]}

    added = sorted(name for name in curr_map if name not in saved_map)
    removed = sorted(name for name in saved_map if name not in curr_map)
    changed: list[dict[str, Any]] = []

    for name in sorted(set(curr_map) & set(saved_map)):
        s_item = saved_map[name]
        c_item = curr_map[name]
        diffs: dict[str, Any] = {}
        for field in ("sha256", "line_count", "size_bytes", "task_kind_counts"):
            if s_item.get(field) != c_item.get(field):
                diffs[field] = {"expected": s_item.get(field), "actual": c_item.get(field)}
        if diffs:
            changed.append({"name": name, "diffs": diffs})

    drift_detected = bool(added or removed or changed)
    return {
        "schema": REGISTRY_SCHEMA,
        "index": str(index_path),
        "drift_detected": drift_detected,
        "added": added,
        "removed": removed,
        "changed": changed,
        "current_count": current["corpus_count"],
        "saved_count": len(saved_map),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Registri corpus beku ACE di handover/ dan pendeteksi drift."
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=DEFAULT_HANDOVER_DIR,
        help="Direktori sumber corpus beku (default: handover/)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Tulis indeks JSON ke berkas target (default: cetak ke stdout)",
    )
    parser.add_argument(
        "--check",
        type=Path,
        default=None,
        metavar="INDEX_JSON",
        help="Bandingkan indeks tersimpan terhadap keadaan direktori saat ini",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Titik masuk CLI registri corpus beku."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        if args.check is not None:
            report = check_drift(args.dir, args.check)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 1 if report["drift_detected"] else 0

        registry = scan_corpora(args.dir)
        rendered = json.dumps(registry, ensure_ascii=False, indent=2) + "\n"
        if args.output is not None:
            tmp_path = args.output.with_name(f".{args.output.name}.tmp.{os.getpid()}")
            tmp_path.write_text(rendered, encoding="utf-8")
            os.replace(tmp_path, args.output)
        print(rendered, end="")
        return 0
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    except (OSError, RegistryError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
