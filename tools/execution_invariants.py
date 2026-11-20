"""Pemeriksa tiga invarian eksekusi atas jejak receipts JSONL dan ringkasan log (AG85).

Memverifikasi jejak eksekusi secara read-only terhadap spesifikasi invarian
bernama (JSON):
1. ``inv_no_execution_without_receipt``: setiap eksekusi tercatat di log wajib
   memiliki pasangan receipt ``started`` -> ``completed``/``failed`` yang sah
   (sekaligus menolak receipt palsu ``completed`` tanpa ``started``);
2. ``inv_no_class_a_without_verified_anchor``: eksekusi Kelas A wajib memiliki
   jangkar terverifikasi;
3. ``inv_daily_cap_not_exceeded``: jumlah eksekusi per hari UTC tidak boleh
   melewati ``daily_cap``.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.execution-invariants.v1"

NAMED_INVARIANT_SPECS: list[dict[str, str]] = [
    {
        "id": "inv_no_execution_without_receipt",
        "title": "Tidak ada eksekusi tanpa pasangan receipt started/terminal yang sah",
    },
    {
        "id": "inv_no_class_a_without_verified_anchor",
        "title": "Tidak ada eksekusi Kelas A tanpa jangkar terverifikasi",
    },
    {
        "id": "inv_daily_cap_not_exceeded",
        "title": "Hitungan eksekusi harian UTC tidak melewati batas cap",
    },
]


def _load_json_or_jsonl(path: Path) -> list[dict[str, Any]]:
    raw = Path(path).read_text(encoding="utf-8").strip()
    if not raw:
        return []
    if raw.startswith("["):
        return [dict(x) for x in json.loads(raw)]
    if raw.startswith("{") and "\n" not in raw:
        obj = json.loads(raw)
        if isinstance(obj, Mapping) and isinstance(obj.get("executions"), list):
            return [dict(x) for x in obj["executions"]]
        return [dict(obj)]
    return [json.loads(ln) for ln in raw.splitlines() if ln.strip()]


def check_execution_invariants(
    receipts: Sequence[Mapping[str, Any]],
    executions: Sequence[Mapping[str, Any]],
    *,
    daily_cap: int = 5,
    verified_refs: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Audit jejak receipts + log eksekusi terhadap ketiga invarian bernama."""
    if type(daily_cap) is not int or daily_cap < 0:
        raise ValueError("daily_cap wajib integer nonnegatif")

    verified_set = set(verified_refs) if verified_refs is not None else None
    violations: list[dict[str, Any]] = []

    started_tasks: set[str] = set()
    terminal_tasks: set[str] = set()
    valid_receipt_pairs: set[str] = set()
    day_tasks: dict[str, set[str]] = defaultdict(set)

    for idx, rec in enumerate(receipts, 1):
        tid = str(rec.get("task_id") or "").strip()
        status = str(rec.get("status") or "").strip().lower()
        at = str(rec.get("at") or rec.get("ts") or "").strip()
        day = at[:10] if len(at) >= 10 else "unknown"

        if not tid:
            violations.append(
                {
                    "invariant": "inv_no_execution_without_receipt",
                    "code": "receipt_missing_task_id",
                    "line": idx,
                    "detail": "Baris receipt kehilangan task_id.",
                }
            )
            continue

        if status == "started":
            started_tasks.add(tid)
            day_tasks[day].add(tid)
        elif status in {"completed", "failed"}:
            terminal_tasks.add(tid)
            day_tasks[day].add(tid)
            if tid not in started_tasks:
                violations.append(
                    {
                        "invariant": "inv_no_execution_without_receipt",
                        "code": "terminal_without_started",
                        "task_id": tid,
                        "status": status,
                        "detail": f"Receipt palsu '{status}' muncul tanpa event 'started' untuk {tid!r}.",
                    }
                )
            else:
                valid_receipt_pairs.add(tid)

    # Cek setiap entri eksekusi pada ringkasan log.
    for idx, ex in enumerate(executions, 1):
        tid = str(ex.get("task_id") or "").strip()
        if not tid:
            violations.append(
                {
                    "invariant": "inv_no_execution_without_receipt",
                    "code": "execution_missing_task_id",
                    "index": idx,
                    "detail": "Entri eksekusi log tidak memiliki task_id.",
                }
            )
            continue

        at = str(ex.get("at") or ex.get("ts") or "").strip()
        day = at[:10] if len(at) >= 10 else "unknown"
        day_tasks[day].add(tid)

        if tid not in valid_receipt_pairs:
            violations.append(
                {
                    "invariant": "inv_no_execution_without_receipt",
                    "code": "execution_without_receipt",
                    "task_id": tid,
                    "detail": f"Eksekusi log {tid!r} tidak memiliki pasangan receipt started->terminal yang sah.",
                }
            )

        cls_val = str(ex.get("class") or ex.get("proposal_class") or "").strip().upper()
        if cls_val == "A":
            refs = ex.get("evidence_refs") or ex.get("based_on") or []
            explicit_ok = ex.get("anchor_verified")
            if explicit_ok is False:
                anchored_ok = False
            elif verified_set is not None:
                anchored_ok = bool(refs) and all(str(r) in verified_set for r in refs)
            else:
                anchored_ok = explicit_ok is True or (
                    ex.get("anchor_status") == "anchored" and bool(refs)
                )

            if not anchored_ok:
                violations.append(
                    {
                        "invariant": "inv_no_class_a_without_verified_anchor",
                        "code": "class_a_without_verified_anchor",
                        "task_id": tid,
                        "detail": f"Eksekusi Kelas A {tid!r} berjalan tanpa jangkar terverifikasi.",
                    }
                )

    # Invarian 3: batas cap harian.
    daily_counts = {day: len(tids) for day, tids in sorted(day_tasks.items()) if day != "unknown"}
    for day, count in sorted(daily_counts.items()):
        if count > daily_cap:
            violations.append(
                {
                    "invariant": "inv_daily_cap_not_exceeded",
                    "code": "daily_cap_exceeded",
                    "day": day,
                    "count": count,
                    "daily_cap": daily_cap,
                    "detail": f"Hitungan eksekusi hari {day} ({count}) melampaui cap ({daily_cap}).",
                }
            )

    violated_invariants = sorted({v["invariant"] for v in violations})
    per_invariant = [
        {
            **spec,
            "holds": spec["id"] not in violated_invariants,
        }
        for spec in NAMED_INVARIANT_SPECS
    ]

    return {
        "schema": SCHEMA,
        "daily_cap": daily_cap,
        "all_invariants_hold": len(violations) == 0,
        "invariant_specs": per_invariant,
        "summary": {
            "receipt_count": len(receipts),
            "execution_count": len(executions),
            "valid_receipt_pair_count": len(valid_receipt_pairs),
            "daily_counts": daily_counts,
            "violation_count": len(violations),
            "violated_invariants": violated_invariants,
        },
        "violations": violations,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Periksa tiga invarian eksekusi atas receipts JSONL dan ringkasan log."
    )
    parser.add_argument("--receipts", required=True, help="Path berkas receipts JSONL/JSON.")
    parser.add_argument("--executions", required=True, help="Path ringkasan log eksekusi JSON/JSONL.")
    parser.add_argument("--daily-cap", type=int, default=5, help="Batas maksimal eksekusi per hari UTC.")
    parser.add_argument("--verified-refs", help="Path opsional daftar ref terverifikasi JSON.")
    parser.add_argument("--out", help="Path output JSON opsional.")
    args = parser.parse_args(argv)

    try:
        receipts = _load_json_or_jsonl(Path(args.receipts))
        executions = _load_json_or_jsonl(Path(args.executions))
        refs = (
            json.loads(Path(args.verified_refs).read_text(encoding="utf-8"))
            if args.verified_refs
            else None
        )
        report = check_execution_invariants(
            receipts,
            executions,
            daily_cap=args.daily_cap,
            verified_refs=refs,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        op = Path(args.out)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0 if report["all_invariants_hold"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
