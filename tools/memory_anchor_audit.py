#!/usr/bin/env python3
"""Audit tambatan batch proposal agar referensi dangling dan based_on kosong tertangkap sebelum eksekusi.

Kenapa: proposal director tidak boleh lolos diam-diam bila referensinya tidak
terverifikasi atau bila field based_on hilang/kosong. Perkakas baca-saja ini
menjalankan memory_anchor.check_anchors pada setiap baris proposal JSONL
terhadap berkas daftar ref terverifikasi, lalu mengeluarkan vonis per proposal
(anchored, partial, dangling, atau missing_based_on) beserta ringkasan hitungan.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from ace_operational.memory_anchor import check_anchors


SCHEMA = "ace.memory-anchor-audit.v1"


class VerifiedRefSet:
    """Store baca-saja berdasar himpunan ref terverifikasi."""

    def __init__(self, refs: list[str]) -> None:
        if not isinstance(refs, list) or any(
            not isinstance(r, str) or not r.strip() for r in refs
        ):
            raise ValueError("verified_refs wajib berupa daftar string tak-kosong.")
        self._refs = frozenset(refs)

    def verify_ref(self, ref: str) -> bool:
        return ref in self._refs


def load_verified_store(path: Path) -> VerifiedRefSet:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if isinstance(data, dict):
        refs = data.get("verified_refs")
    elif isinstance(data, list):
        refs = data
    else:
        raise ValueError("Berkas ref terverifikasi wajib berupa objek {'verified_refs': [...]} atau larik JSON.")
    return VerifiedRefSet(refs)


def _extract_based_on(row: dict[str, Any]) -> tuple[bool, Any]:
    if "based_on" in row:
        return True, row["based_on"]
    cp = row.get("checkpoint")
    if isinstance(cp, dict):
        if "based_on" in cp:
            return True, cp["based_on"]
        prop = cp.get("proposal")
        if isinstance(prop, dict) and "based_on" in prop:
            return True, prop["based_on"]
    return False, None


def audit_proposals(rows: list[dict[str, Any]], store: VerifiedRefSet) -> dict[str, Any]:
    if not isinstance(rows, list):
        raise ValueError("Proposal wajib berupa daftar objek JSON.")
    counts = {
        "anchored": 0,
        "partial": 0,
        "dangling": 0,
        "missing_based_on": 0,
    }
    proposals: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for idx, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f"Proposal baris {idx} bukan objek JSON.")
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip() or task_id in seen_ids:
            raise ValueError(f"Proposal baris {idx} tidak memiliki task_id unik yang sah.")
        seen_ids.add(task_id)

        present, raw_refs = _extract_based_on(row)
        if (
            not present
            or not isinstance(raw_refs, list)
            or len(raw_refs) == 0
            or any(not isinstance(r, str) or not r.strip() for r in raw_refs)
        ):
            counts["missing_based_on"] += 1
            proposals.append(
                {
                    "task_id": task_id,
                    "verdict": "missing_based_on",
                    "anchor_status": "untethered",
                    "score": 0,
                    "refs": [],
                    "reason": "based_on_missing_or_empty",
                }
            )
            continue

        anchor = check_anchors(raw_refs, store)
        status = anchor["status"]
        if status == "anchored":
            verdict = "anchored"
        elif status == "partial":
            verdict = "partial"
        else:
            verdict = "dangling"
        counts[verdict] += 1
        proposals.append(
            {
                "task_id": task_id,
                "verdict": verdict,
                "anchor_status": status,
                "score": anchor["score"],
                "refs": anchor["refs"],
            }
        )

    return {
        "schema": SCHEMA,
        "total_proposals": len(proposals),
        "counts": counts,
        "proposals": proposals,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposals", type=Path, required=True, help="Berkas JSONL proposal.")
    parser.add_argument("--store", type=Path, required=True, help="Berkas JSON verified_refs.")
    args = parser.parse_args(argv)
    try:
        store = load_verified_store(args.store)
        with args.proposals.open(encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
        report = audit_proposals(rows, store)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
