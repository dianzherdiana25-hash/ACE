"""Penangkap & pembanding sidik jari perilaku lintas snapshot (AG93).

Menjalankan paket prompt sidik jari (JSONL kategori ``keputusan``, ``gaya``,
``pengetahuan_diri``) lewat callable ``answerer(item) -> str``, lalu membandingkan
dua snapshot per kategori dengan status ``berubah`` vs ``bertahan`` serta laju
divergensi per kategori.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable, Mapping, Sequence


SNAPSHOT_SCHEMA = "ace.behavior-fingerprint-snapshot.v1"
DIFF_SCHEMA = "ace.behavior-fingerprint-diff.v1"
VALID_CATEGORIES = ("keputusan", "gaya", "pengetahuan_diri")


def _normalize_response(raw: Any) -> str:
    text = "" if raw is None else str(raw)
    return re.sub(r"\s+", " ", text.strip())


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_prompt_pack(path: str | Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        row = json.loads(line)
        pid = str(row.get("prompt_id") or "").strip()
        cat = str(row.get("category") or "").strip()
        prompt = str(row.get("prompt") or "").strip()
        if not pid:
            raise ValueError(f"Prompt item wajib memiliki prompt_id: {row!r}")
        if cat not in VALID_CATEGORIES:
            raise ValueError(
                f"Kategori sidik jari tidak dikenal {cat!r}; pilih dari {VALID_CATEGORIES}."
            )
        if not prompt:
            raise ValueError(f"Prompt item {pid!r} memiliki prompt kosong.")
        items.append({"prompt_id": pid, "category": cat, "prompt": prompt})
    return items


def run_fingerprint_snapshot(
    prompt_pack: Sequence[Mapping[str, Any]],
    answerer: Callable[[Mapping[str, Any]], Any],
    *,
    snapshot_id: str = "snap-0",
) -> dict[str, Any]:
    """Jalankan paket prompt lewat ``answerer`` dan hasilkan snapshot terstruktur."""
    responses: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in prompt_pack:
        pid = str(row["prompt_id"])
        cat = str(row["category"])
        if cat not in VALID_CATEGORIES:
            raise ValueError(f"Kategori tidak sah: {cat!r}")
        if pid in seen_ids:
            raise ValueError(f"prompt_id duplikat: {pid!r}")
        seen_ids.add(pid)
        norm = _normalize_response(answerer(row))
        responses.append(
            {
                "prompt_id": pid,
                "category": cat,
                "response": norm,
                "response_sha256": _hash_text(norm),
            }
        )

    return {
        "schema": SNAPSHOT_SCHEMA,
        "snapshot_id": snapshot_id,
        "item_count": len(responses),
        "responses": responses,
    }


def diff_fingerprint_snapshots(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> dict[str, Any]:
    """Bandingkan dua snapshot sidik jari per kategori (``berubah`` vs ``bertahan``)."""
    base_by_id = {str(r["prompt_id"]): r for r in baseline.get("responses", [])}
    cand_by_id = {str(r["prompt_id"]): r for r in candidate.get("responses", [])}
    if set(base_by_id.keys()) != set(cand_by_id.keys()):
        raise ValueError("Kedua snapshot wajib memiliki himpunan prompt_id yang identik.")

    by_category: dict[str, dict[str, Any]] = {
        cat: {
            "total": 0,
            "berubah": 0,
            "bertahan": 0,
            "divergence_rate": 0.0,
            "retention_rate": 0.0,
        }
        for cat in VALID_CATEGORIES
    }
    items: list[dict[str, Any]] = []
    total_changed = 0
    total_kept = 0

    for row_base in baseline.get("responses", []):
        pid = str(row_base["prompt_id"])
        row_cand = cand_by_id[pid]
        cat = str(row_base["category"])
        if str(row_cand["category"]) != cat:
            raise ValueError(f"Kategori mismatch untuk {pid!r}: {cat!r} vs {row_cand['category']!r}.")
        if cat not in by_category:
            raise ValueError(f"Kategori tidak didukung: {cat!r}")

        changed = row_base["response_sha256"] != row_cand["response_sha256"]
        status = "berubah" if changed else "bertahan"
        bucket = by_category[cat]
        bucket["total"] += 1
        bucket[status] += 1
        if changed:
            total_changed += 1
        else:
            total_kept += 1
        items.append(
            {
                "prompt_id": pid,
                "category": cat,
                "status": status,
                "baseline_response": row_base["response"],
                "candidate_response": row_cand["response"],
            }
        )

    for cat, bucket in by_category.items():
        n = bucket["total"]
        if n > 0:
            bucket["divergence_rate"] = round(bucket["berubah"] / n, 6)
            bucket["retention_rate"] = round(bucket["bertahan"] / n, 6)

    total = len(items)
    return {
        "schema": DIFF_SCHEMA,
        "baseline_id": str(baseline.get("snapshot_id", "baseline")),
        "candidate_id": str(candidate.get("snapshot_id", "candidate")),
        "total_items": total,
        "berubah": total_changed,
        "bertahan": total_kept,
        "overall_divergence_rate": round(total_changed / total, 6) if total else 0.0,
        "overall_retention_rate": round(total_kept / total, 6) if total else 0.0,
        "by_category": by_category,
        "items": items,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pembanding snapshot sidik jari perilaku (AG93)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_diff = sub.add_parser("diff", help="Bandingkan dua berkas snapshot JSON")
    p_diff.add_argument("--baseline", required=True)
    p_diff.add_argument("--candidate", required=True)
    args = parser.parse_args(argv)

    if args.cmd == "diff":
        base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        cand = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
        report = diff_fingerprint_snapshots(base, cand)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
