#!/usr/bin/env python3
"""Registry korpus beku generasi baru dengan deteksi drift (Garis B3).

Mencatat setiap berkas korpus beku (`*corpus*.jsonl` atau berkas `.jsonl`
terpilih) berupa: nama relatif POSIX, jumlah baris, `sha256`, ukuran byte,
dan sebaran `task_kind`. Mode `--check` membandingkan indeks tersimpan terhadap
kondisi terkini direktori/berkas dan melaporkan `ADDED`, `REMOVED`, maupun
`MODIFIED` (line_count / sha256 / task_kind_distribution).
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

REGISTRY_V2_SCHEMA = "ace.frozen-corpus-registry.v2"


class FrozenRegistryError(ValueError):
    """Kesalahan berkas korpus, direktori target, atau format indeks registry."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        while chunk := fp.read(65536):
            h.update(chunk)
    return h.hexdigest()


def inspect_frozen_corpus(path: Path, *, root_dir: Path | None = None) -> dict[str, Any]:
    """Hitung metadata ringkas satu berkas korpus JSONL beku."""
    if not path.is_file():
        raise FrozenRegistryError(f"Berkas korpus beku tidak ditemukan: {path}")
    try:
        raw_text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise FrozenRegistryError(f"Gagal membaca korpus '{path}': {exc}") from exc

    dist: Counter[str] = Counter()
    line_count = 0
    for line_no, raw_line in enumerate(raw_text.splitlines(), start=1):
        if not raw_line.strip():
            raise FrozenRegistryError(f"Baris kosong ditemukan pada '{path}' baris {line_no}.")
        try:
            obj = json.loads(raw_line)
        except (json.JSONDecodeError, ValueError) as exc:
            raise FrozenRegistryError(f"JSON tidak sah pada '{path}' baris {line_no}: {exc}") from exc
        if not isinstance(obj, dict):
            raise FrozenRegistryError(f"Baris '{path}' baris {line_no} wajib berupa objek JSON.")
        tk = obj.get("task_kind")
        if isinstance(tk, str) and tk.strip():
            label = tk.strip()
        else:
            k = obj.get("kind")
            label = f"kind:{k.strip()}" if isinstance(k, str) and k.strip() else "unknown"
        dist[label] += 1
        line_count += 1

    if line_count == 0:
        raise FrozenRegistryError(f"Korpus beku kosong: {path}")

    rel_name = path.resolve().relative_to(root_dir.resolve()).as_posix() if root_dir is not None else path.name
    return {
        "name": rel_name,
        "line_count": line_count,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "task_kind_distribution": dict(sorted(dist.items())),
    }


def scan_corpus_directory(target_dir: Path, *, pattern: str = "*corpus*.jsonl") -> dict[str, Any]:
    """Bangun indeks registry dari seluruh berkas korpus beku pada `target_dir`."""
    if not target_dir.is_dir():
        raise FrozenRegistryError(f"Direktori target bukan direktori yang ada: {target_dir}")
    needle = pattern.lower()
    if needle == "*corpus*.jsonl":
        files = sorted(
            p for p in target_dir.rglob("*.jsonl")
            if p.is_file() and "corpus" in p.name.lower()
        )
    else:
        files = sorted(p for p in target_dir.rglob(pattern) if p.is_file())
    if not files:
        raise FrozenRegistryError(f"Tidak ada berkas korpus yang cocok di '{target_dir}'.")

    entries = [inspect_frozen_corpus(p, root_dir=target_dir) for p in files]
    total_lines = sum(e["line_count"] for e in entries)
    overall_dist: Counter[str] = Counter()
    for e in entries:
        overall_dist.update(e["task_kind_distribution"])

    return {
        "schema": REGISTRY_V2_SCHEMA,
        "root": target_dir.resolve().as_posix(),
        "corpus_count": len(entries),
        "total_lines": total_lines,
        "task_kind_distribution": dict(sorted(overall_dist.items())),
        "entries": entries,
    }


def upsert_registry_entry(registry_path: Path, entry: dict[str, Any], *, root_dir: Path | None = None) -> dict[str, Any]:
    """Tambahkan atau perbarui satu entri pada berkas registry JSON secara atomik."""
    if registry_path.exists():
        try:
            existing = json.loads(registry_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FrozenRegistryError(f"Gagal membaca registry '{registry_path}': {exc}") from exc
        if not isinstance(existing, dict) or not isinstance(existing.get("entries"), list):
            raise FrozenRegistryError(f"Struktur registry tidak sah: {registry_path}")
        by_name = {str(item["name"]): item for item in existing["entries"] if isinstance(item, dict) and "name" in item}
        root_str = str(existing.get("root", (root_dir.resolve().as_posix() if root_dir else registry_path.parent.resolve().as_posix())))
    else:
        by_name = {}
        root_str = root_dir.resolve().as_posix() if root_dir else registry_path.parent.resolve().as_posix()

    by_name[str(entry["name"])] = entry
    entries = [by_name[name] for name in sorted(by_name)]
    total_lines = sum(int(item["line_count"]) for item in entries)
    overall_dist: Counter[str] = Counter()
    for item in entries:
        overall_dist.update(item.get("task_kind_distribution", {}))

    updated = {
        "schema": REGISTRY_V2_SCHEMA,
        "root": root_str,
        "corpus_count": len(entries),
        "total_lines": total_lines,
        "task_kind_distribution": dict(sorted(overall_dist.items())),
        "entries": entries,
    }
    atomic_write_text(registry_path, json.dumps(updated, ensure_ascii=False, indent=2) + "\n")
    return updated


def check_registry_drift(index_path: Path, target_dir: Path | None = None, *, pattern: str = "*corpus*.jsonl") -> dict[str, Any]:
    """Bandingkan indeks registry tersimpan terhadap keadaan terkini direktori korpus."""
    if not index_path.is_file():
        raise FrozenRegistryError(f"Berkas indeks registry tidak ditemukan: {index_path}")
    try:
        stored = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FrozenRegistryError(f"Gagal membaca indeks '{index_path}': {exc}") from exc
    if not isinstance(stored, dict) or not isinstance(stored.get("entries"), list):
        raise FrozenRegistryError("Format indeks registry tidak sah (harus memuat list 'entries').")

    scan_root = target_dir if target_dir is not None else Path(str(stored.get("root", "")))
    current = scan_corpus_directory(scan_root, pattern=pattern)

    expected_map = {str(e["name"]): e for e in stored["entries"] if isinstance(e, dict) and "name" in e}
    actual_map = {str(e["name"]): e for e in current["entries"]}

    drifts: list[dict[str, Any]] = []
    for name in sorted(set(expected_map) | set(actual_map)):
        if name not in expected_map:
            drifts.append({"name": name, "drift_type": "ADDED", "actual": actual_map[name]})
            continue
        if name not in actual_map:
            drifts.append({"name": name, "drift_type": "REMOVED", "expected": expected_map[name]})
            continue
        exp = expected_map[name]
        act = actual_map[name]
        changed = [k for k in ("line_count", "sha256", "bytes", "task_kind_distribution") if exp.get(k) != act.get(k)]
        if changed:
            drifts.append(
                {
                    "name": name,
                    "drift_type": "MODIFIED",
                    "changed_fields": changed,
                    "expected": {k: exp.get(k) for k in changed},
                    "actual": {k: act.get(k) for k in changed},
                }
            )

    return {
        "schema": REGISTRY_V2_SCHEMA,
        "index_path": str(index_path),
        "root": current["root"],
        "clean": len(drifts) == 0,
        "drift_count": len(drifts),
        "drifts": drifts,
    }


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Registry korpus beku dan pemeriksaan drift.")
    parser.add_argument("--dir", type=Path, required=True, help="Direktori korpus target.")
    parser.add_argument("--write", type=Path, help="Tulis indeks registry JSON secara atomik.")
    parser.add_argument("--check", type=Path, help="Bandingkan direktori saat ini terhadap berkas indeks.")
    parser.add_argument("--pattern", default="*corpus*.jsonl", help="Pola pencarian berkas korpus JSONL.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.write and args.check:
            raise FrozenRegistryError("Gunakan salah satu: --write atau --check.")
        if args.check:
            report = check_registry_drift(args.check, target_dir=args.dir, pattern=args.pattern)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["clean"] else 1
        index = scan_corpus_directory(args.dir, pattern=args.pattern)
        rendered = json.dumps(index, ensure_ascii=False, indent=2) + "\n"
        if args.write:
            atomic_write_text(args.write, rendered)
        print(rendered, end="")
        return 0
    except FrozenRegistryError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
