"""Analisis pola ekspor gap JSONL dan deteksi gap yatim rujukan proposal (AG4).

Membaca ekspor gap JSONL (``gap_id``, ``kind``, ``occurrence``, ``status``) serta
ekspor proposal opsional secara murni baca-saja untuk merangkum kelompok per
``kind``, keluarga dominan, entri ``occurrence`` tertinggi, dan gap yatim
(dirujuk oleh proposal tetapi tidak ditemukan pada ekspor gap).
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.gap-pattern-report.v1"
_CLOSED_STATUSES = frozenset({"closed", "resolved", "done", "fixed"})


def _load_jsonl_or_json(path: Path) -> list[dict[str, Any]]:
    raw = Path(path).read_text(encoding="utf-8").strip()
    if not raw:
        return []
    if raw.startswith("["):
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError(f"Berkas JSON harus berupa list: {path}")
        return [dict(item) for item in data]
    if raw.startswith("{") and "\n" not in raw:
        obj = json.loads(raw)
        if isinstance(obj, Mapping):
            for key in ("gaps", "proposals", "records", "items"):
                if isinstance(obj.get(key), list):
                    return [dict(item) for item in obj[key]]
            return [dict(obj)]
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def _extract_proposal_gap_refs(proposal: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    sources: list[Mapping[str, Any]] = [proposal]
    cp = proposal.get("checkpoint")
    if isinstance(cp, Mapping):
        sources.append(cp)
    for src in sources:
        single = src.get("gap_id") or src.get("target_gap_id")
        if isinstance(single, str) and single.strip():
            refs.append(single.strip())
        many = src.get("gap_refs") or src.get("gap_ids")
        if isinstance(many, list):
            for item in many:
                if isinstance(item, str) and item.strip():
                    refs.append(item.strip())
    return list(dict.fromkeys(refs))


def analyze_gap_patterns(
    gaps: Sequence[Mapping[str, Any]],
    proposals: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Bangun ringkasan pola deterministik dari ekspor gap dan proposal."""
    if not gaps:
        raise ValueError("Ekspor gap tidak boleh kosong")

    by_kind: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "count": 0,
            "open_count": 0,
            "closed_count": 0,
            "total_occurrence": 0,
            "max_occurrence": 0,
            "gap_ids": [],
        }
    )
    known_gap_ids: set[str] = set()
    highest_entry: dict[str, Any] | None = None
    total_occurrence = 0

    for idx, row in enumerate(gaps, 1):
        if not isinstance(row, Mapping):
            raise ValueError(f"Entri gap ke-{idx} wajib berupa objek JSON")
        gap_id = row.get("gap_id") or row.get("id")
        if not isinstance(gap_id, str) or not gap_id.strip():
            raise ValueError(f"Entri gap ke-{idx} wajib memiliki gap_id tak-kosong")
        gap_id = gap_id.strip()
        kind = str(row.get("kind") or row.get("error_type") or "UNKNOWN").strip() or "UNKNOWN"
        status = str(row.get("status") or "OPEN").strip().upper()
        occ = row.get("occurrence", 1)
        if isinstance(occ, bool) or not isinstance(occ, (int, float)) or occ < 0:
            raise ValueError(f"occurrence gap '{gap_id}' tidak sah: {occ!r}")
        occ_int = int(occ)

        known_gap_ids.add(gap_id)
        total_occurrence += occ_int

        bucket = by_kind[kind]
        bucket["count"] += 1
        if status.lower() in _CLOSED_STATUSES:
            bucket["closed_count"] += 1
        else:
            bucket["open_count"] += 1
        bucket["total_occurrence"] += occ_int
        if occ_int > bucket["max_occurrence"]:
            bucket["max_occurrence"] = occ_int
        bucket["gap_ids"].append(gap_id)

        candidate = {
            "gap_id": gap_id,
            "kind": kind,
            "occurrence": occ_int,
            "status": status,
        }
        if highest_entry is None or (
            candidate["occurrence"],
            candidate["gap_id"],
        ) > (highest_entry["occurrence"], highest_entry["gap_id"]):
            highest_entry = candidate

    groups_sorted: dict[str, dict[str, Any]] = {}
    for kind in sorted(by_kind):
        info = by_kind[kind]
        info["gap_ids"] = sorted(info["gap_ids"])
        groups_sorted[kind] = info

    dom_kind = min(
        groups_sorted.keys(),
        key=lambda k: (-groups_sorted[k]["count"], -groups_sorted[k]["total_occurrence"], k),
    )
    dominant_family = {
        "kind": dom_kind,
        "count": groups_sorted[dom_kind]["count"],
        "share": round(groups_sorted[dom_kind]["count"] / len(gaps), 6),
        "total_occurrence": groups_sorted[dom_kind]["total_occurrence"],
    }

    orphan_map: dict[str, list[str]] = defaultdict(list)
    for idx, prop in enumerate(proposals, 1):
        if not isinstance(prop, Mapping):
            continue
        pid = str(prop.get("proposal_id") or prop.get("task_id") or prop.get("id") or f"prop-{idx}")
        for ref_gap in _extract_proposal_gap_refs(prop):
            if ref_gap not in known_gap_ids:
                orphan_map[ref_gap].append(pid)

    orphan_gaps = [
        {"gap_id": gid, "referenced_by": sorted(set(orphan_map[gid]))}
        for gid in sorted(orphan_map)
    ]

    return {
        "schema": SCHEMA,
        "summary": {
            "total_gaps": len(gaps),
            "unique_gap_ids": len(known_gap_ids),
            "kind_count": len(groups_sorted),
            "total_occurrence": total_occurrence,
            "orphan_gap_count": len(orphan_gaps),
        },
        "dominant_family": dominant_family,
        "highest_occurrence": highest_entry,
        "by_kind": groups_sorted,
        "orphan_gaps": orphan_gaps,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analisis pola ekspor gap JSONL dan deteksi gap yatim dari proposal."
    )
    parser.add_argument("--gaps", required=True, help="Path berkas ekspor gap JSONL/JSON.")
    parser.add_argument("--proposals", help="Path opsional ekspor proposal JSONL/JSON.")
    parser.add_argument("--out", help="Path output JSON opsional (default stdout).")
    args = parser.parse_args(argv)

    try:
        gaps = _load_jsonl_or_json(Path(args.gaps))
        proposals = _load_jsonl_or_json(Path(args.proposals)) if args.proposals else []
        report = analyze_gap_patterns(gaps, proposals)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
