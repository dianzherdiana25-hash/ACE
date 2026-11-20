"""Perencana arsip lupa terencana (memory decay) berbasis recency & frekuensi recall (AG62).

Menilai rekaman memori aktif dari keterbaruan pemakaian (recency) serta
frekuensi pemanggilan (dari log recall fixture) secara read-only untuk menyusun
RENCANA arsip beserta jejak alasan per record tanpa pernah menghapus data.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.memory-decay-archive.v1"
DEFAULT_STALE_DAYS = 60
DEFAULT_HALF_LIFE_DAYS = 30.0
DEFAULT_MIN_RETAIN_SCORE = 0.40


def _parse_ts(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    s = raw.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _load_records(memory_path: Path) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    superseded: set[str] = set()
    for line_no, raw in enumerate(Path(memory_path).read_text(encoding="utf-8").splitlines(), 1):
        s = raw.strip()
        if not s:
            continue
        obj = json.loads(s)
        if not isinstance(obj, Mapping):
            continue
        ev = obj.get("event")
        if isinstance(ev, Mapping):
            etype = ev.get("type")
            if etype == "record" and isinstance(ev.get("record"), Mapping):
                rec = dict(ev["record"])
                if "ts" not in rec and obj.get("ts"):
                    rec["ts"] = obj.get("ts")
                rid = str(rec.get("id") or "")
                if rid:
                    records[rid] = rec
            elif etype == "supersede":
                superseded.add(str(ev.get("record_id") or ""))
            elif etype == "tombstone":
                records.pop(str(ev.get("record_id") or ""), None)
        else:
            rid = str(obj.get("id") or obj.get("record_id") or f"line-{line_no}")
            records[rid] = dict(obj)
    return [records[k] for k in sorted(records) if k not in superseded]


def _load_recall_events(recall_log_path: Path) -> list[dict[str, Any]]:
    path = Path(recall_log_path)
    if not path.is_file():
        return []
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    if raw.startswith("["):
        data = json.loads(raw)
        return [dict(x) for x in data if isinstance(x, Mapping)] if isinstance(data, list) else []
    return [json.loads(ln) for ln in raw.splitlines() if ln.strip()]


def build_archive_plan(
    memory_path: Path,
    recall_log_path: Path,
    *,
    as_of: datetime | str,
    stale_days: int = DEFAULT_STALE_DAYS,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
    min_retain_score: float = DEFAULT_MIN_RETAIN_SCORE,
) -> dict[str, Any]:
    """Hasilkan RENCANA arsip tanpa menghapus berkas memory maupun recall log."""
    as_of_dt = as_of if isinstance(as_of, datetime) else _parse_ts(as_of)
    if as_of_dt is None:
        raise ValueError(f"Timestamp as_of tidak sah: {as_of!r}")
    if as_of_dt.tzinfo is None:
        as_of_dt = as_of_dt.replace(tzinfo=timezone.utc)
    as_of_dt = as_of_dt.astimezone(timezone.utc)
    if stale_days < 0 or half_life_days <= 0:
        raise ValueError("Parameter decay stale_days/half_life_days tidak sah.")

    records = _load_records(Path(memory_path))
    recall_events = _load_recall_events(Path(recall_log_path))

    recall_counts: dict[str, int] = defaultdict(int)
    last_recalled: dict[str, datetime] = {}

    for ev in recall_events:
        ev_dt = _parse_ts(ev.get("ts") or ev.get("at") or ev.get("timestamp"))
        hit_ids: list[str] = []
        for field in ("recalled_ids", "record_ids", "ids"):
            vals = ev.get(field)
            if isinstance(vals, list):
                hit_ids.extend(str(x) for x in vals if str(x).strip())
        if isinstance(ev.get("record_id"), str) and ev["record_id"].strip():
            hit_ids.append(ev["record_id"].strip())
        if isinstance(ev.get("results"), list):
            for item in ev["results"]:
                if isinstance(item, Mapping) and item.get("id"):
                    hit_ids.append(str(item["id"]))

        for rid in dict.fromkeys(hit_ids):
            recall_counts[rid] += 1
            if ev_dt is not None and (rid not in last_recalled or ev_dt > last_recalled[rid]):
                last_recalled[rid] = ev_dt

    archive_plan: list[dict[str, Any]] = []
    retained: list[dict[str, Any]] = []

    for rec in records:
        rid = str(rec["id"])
        created_dt = _parse_ts(rec.get("created_at") or rec.get("ts"))
        freq = recall_counts.get(rid, 0)
        last_dt = last_recalled.get(rid) or created_dt
        if last_dt is not None:
            idle_days = max(0.0, round((as_of_dt - last_dt).total_seconds() / 86400.0, 2))
        else:
            idle_days = float(stale_days + 1)

        retention_score = round((freq + 1.0) / (1.0 + (idle_days / half_life_days)), 6)
        reasons: list[str] = []

        if idle_days > stale_days and retention_score < min_retain_score:
            reasons.append(f"idle_days={idle_days} > stale_days={stale_days}")
            reasons.append(f"recall_count={freq}")
            reasons.append(f"retention_score={retention_score} < min_retain_score={min_retain_score}")
            archive_plan.append(
                {
                    "record_id": rid,
                    "kind": rec.get("kind"),
                    "action": "archive_candidate",
                    "deleted": False,
                    "recall_count": freq,
                    "idle_days": idle_days,
                    "retention_score": retention_score,
                    "reason_trace": reasons,
                }
            )
        else:
            if idle_days <= stale_days:
                reasons.append(f"recent_activity:idle_days={idle_days} <= stale_days={stale_days}")
            if retention_score >= min_retain_score:
                reasons.append(f"retention_score={retention_score} >= min_retain_score={min_retain_score}")
            if freq > 0:
                reasons.append(f"recalled_{freq}_times")
            retained.append(
                {
                    "record_id": rid,
                    "kind": rec.get("kind"),
                    "action": "keep_active",
                    "recall_count": freq,
                    "idle_days": idle_days,
                    "retention_score": retention_score,
                    "reason_trace": reasons,
                }
            )

    return {
        "schema": SCHEMA,
        "as_of": as_of_dt.isoformat().replace("+00:00", "Z"),
        "policy": {
            "stale_days": stale_days,
            "half_life_days": half_life_days,
            "min_retain_score": min_retain_score,
            "delete_records": False,
        },
        "summary": {
            "total_evaluated": len(records),
            "archive_candidate_count": len(archive_plan),
            "retained_active_count": len(retained),
        },
        "archive_plan": archive_plan,
        "retained_records": retained,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Susun rencana arsip lupa terencana (tidak pernah menghapus data)."
    )
    parser.add_argument("--memory", required=True, help="Path berkas memory.jsonl sumber.")
    parser.add_argument("--recall-log", required=True, help="Path berkas log recall JSON/JSONL.")
    parser.add_argument("--as-of", required=True, help="Timestamp acuan ISO UTC.")
    parser.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS)
    parser.add_argument("--half-life-days", type=float, default=DEFAULT_HALF_LIFE_DAYS)
    parser.add_argument("--min-retain-score", type=float, default=DEFAULT_MIN_RETAIN_SCORE)
    parser.add_argument("--out", help="Path output rencana arsip JSON (default stdout).")
    args = parser.parse_args(argv)

    try:
        report = build_archive_plan(
            Path(args.memory),
            Path(args.recall_log),
            as_of=args.as_of,
            stale_days=args.stale_days,
            half_life_days=args.half_life_days,
            min_retain_score=args.min_retain_score,
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
