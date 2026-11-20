"""Indeks embedding sidecar persisten (JSONL) untuk rekaman memory ACE (AG60).

Membangun dan memperbarui secara inkremental berkas indeks vektor sidecar
(``.jsonl``) tanpa memodifikasi berkas log ``memory.jsonl`` sumber, serta
menyediakan perintah ``verify`` untuk melaporkan rekaman tanpa vektor, vektor
kedaluwarsa, dan vektor yatim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable, Mapping, Sequence


SCHEMA = "ace.embedding-index.v1"
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def deterministic_bow_embedder(text: str, dim: int = 16) -> list[float]:
    """Embedder hash deterministik offline bawaan untuk pengujian dan CLI luring."""
    vec = [0.0] * dim
    for tok in _TOKEN_RE.findall(text.lower()):
        h = int.from_bytes(hashlib.sha256(tok.encode("utf-8")).digest()[:4], "big")
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0.0:
        vec = [round(v / norm, 6) for v in vec]
    return vec


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _record_text(rec: Mapping[str, Any]) -> str:
    content = rec.get("content", "")
    body = content if isinstance(content, str) else json.dumps(content, sort_keys=True, ensure_ascii=False)
    kind = str(rec.get("kind") or "")
    return f"{kind} {body}".strip()


def load_memory_records(memory_path: Path) -> list[dict[str, Any]]:
    """Baca rekaman aktif dari berkas CognitiveMemory JSONL atau JSONL datar (read-only)."""
    records: dict[str, dict[str, Any]] = {}
    for line_no, raw in enumerate(Path(memory_path).read_text(encoding="utf-8").splitlines(), 1):
        stripped = raw.strip()
        if not stripped:
            continue
        obj = json.loads(stripped)
        if not isinstance(obj, Mapping):
            continue
        ev = obj.get("event")
        if isinstance(ev, Mapping):
            etype = ev.get("type")
            if etype == "record" and isinstance(ev.get("record"), Mapping):
                rec = dict(ev["record"])
                rid = str(rec.get("id") or "")
                if rid:
                    records[rid] = rec
            elif etype == "tombstone":
                rid = str(ev.get("record_id") or "")
                records.pop(rid, None)
        else:
            rid = str(obj.get("id") or obj.get("record_id") or f"line-{line_no}")
            records[rid] = dict(obj)
    return [records[k] for k in sorted(records)]


def load_index_entries(index_path: Path) -> dict[str, dict[str, Any]]:
    """Muat sidecar indeks embedding JSONL bila sudah ada."""
    path = Path(index_path)
    if not path.is_file():
        return {}
    entries: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        obj = json.loads(s)
        if isinstance(obj, Mapping) and isinstance(obj.get("record_id"), str):
            entries[obj["record_id"]] = dict(obj)
    return entries


def build_or_update_index(
    memory_path: Path,
    index_path: Path,
    embedder: Callable[[str], Sequence[float]] = deterministic_bow_embedder,
    *,
    model_id: str = "deterministic-bow-16",
    prune_orphans: bool = True,
) -> dict[str, Any]:
    """Bangun atau perbarui inkremental sidecar embedding JSONL dari memory."""
    records = load_memory_records(Path(memory_path))
    existing = load_index_entries(Path(index_path))

    updated: dict[str, dict[str, Any]] = {} if prune_orphans else dict(existing)
    reused_ids: list[str] = []
    embedded_ids: list[str] = []

    for rec in records:
        rid = str(rec["id"])
        text = _record_text(rec)
        c_sha = _canonical_sha256(text)
        prev = existing.get(rid)
        if (
            prev is not None
            and prev.get("content_sha256") == c_sha
            and prev.get("model") == model_id
            and isinstance(prev.get("vector"), list)
            and len(prev["vector"]) > 0
        ):
            updated[rid] = dict(prev)
            reused_ids.append(rid)
            continue

        vec = [float(x) for x in embedder(text)]
        if not vec:
            raise ValueError(f"Embedder menghasilkan vektor kosong untuk record {rid!r}")
        updated[rid] = {
            "schema": SCHEMA,
            "record_id": rid,
            "content_sha256": c_sha,
            "model": model_id,
            "dim": len(vec),
            "vector": vec,
        }
        embedded_ids.append(rid)

    target = Path(index_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.parent / f".{target.name}.tmp"
    lines = [
        json.dumps(updated[rid], sort_keys=True, ensure_ascii=False)
        for rid in sorted(updated)
    ]
    tmp.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    os.replace(tmp, target)

    return {
        "schema": SCHEMA,
        "memory_path": str(memory_path),
        "index_path": str(index_path),
        "model": model_id,
        "total_records": len(records),
        "reused_count": len(reused_ids),
        "embedded_count": len(embedded_ids),
        "total_indexed": len(updated),
        "embedded_ids": embedded_ids,
        "reused_ids": reused_ids,
    }


def verify_index(memory_path: Path, index_path: Path) -> dict[str, Any]:
    """Verifikasi sidecar embedding terhadap log memory secara read-only."""
    records = load_memory_records(Path(memory_path))
    index_entries = load_index_entries(Path(index_path))

    rec_map = {str(rec["id"]): rec for rec in records}
    rec_ids = set(rec_map.keys())
    idx_ids = set(index_entries.keys())

    missing_vectors = sorted(rec_ids - idx_ids)
    orphan_vectors = sorted(idx_ids - rec_ids)
    stale_vectors: list[str] = []

    for rid in sorted(rec_ids & idx_ids):
        c_sha = _canonical_sha256(_record_text(rec_map[rid]))
        entry = index_entries[rid]
        vec = entry.get("vector")
        if entry.get("content_sha256") != c_sha or not isinstance(vec, list) or not vec:
            stale_vectors.append(rid)

    valid = not missing_vectors and not orphan_vectors and not stale_vectors
    return {
        "schema": SCHEMA,
        "memory_path": str(memory_path),
        "index_path": str(index_path),
        "valid": valid,
        "summary": {
            "total_records": len(rec_ids),
            "total_vectors": len(idx_ids),
            "missing_vector_count": len(missing_vectors),
            "orphan_vector_count": len(orphan_vectors),
            "stale_vector_count": len(stale_vectors),
        },
        "missing_vectors": missing_vectors,
        "orphan_vectors": orphan_vectors,
        "stale_vectors": stale_vectors,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bangun, perbarui inkremental, dan verifikasi indeks embedding sidecar JSONL."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sync = sub.add_parser("build", help="Bangun/perbarui indeks embedding sidecar.")
    p_sync.add_argument("--memory", required=True, help="Path berkas memory.jsonl sumber (read-only).")
    p_sync.add_argument("--index", required=True, help="Path sidecar JSONL indeks embedding.")
    p_sync.add_argument("--no-prune", action="store_true", help="Pertahankan vektor lama walau record dihapus.")
    p_sync.add_argument("--out", help="Path output ringkasan JSON opsional.")

    p_ver = sub.add_parser("verify", help="Laporkan record tanpa vektor & vektor yatim.")
    p_ver.add_argument("--memory", required=True, help="Path berkas memory.jsonl sumber (read-only).")
    p_ver.add_argument("--index", required=True, help="Path sidecar JSONL indeks embedding.")
    p_ver.add_argument("--out", help="Path output laporan JSON opsional.")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "build":
            result = build_or_update_index(
                Path(args.memory),
                Path(args.index),
                prune_orphans=not args.no_prune,
            )
            exit_code = 0
        else:
            result = verify_index(Path(args.memory), Path(args.index))
            exit_code = 0 if result["valid"] else 1
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        op = Path(args.out)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
