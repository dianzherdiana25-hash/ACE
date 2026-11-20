"""Papan skor kualitas organ dari receipts eksekusi dan laporan grounding (AG71).

Menghitung per organ secara baca-saja:
- ``grounding_mismatch_rate`` (laju klaim kuantitatif tak cocok fakta),
- ``gate_block_rate`` (laju usulan tertahan pagar keamanan/konstitusi),
- ``execution_success_rate`` (laju eksekusi berhasil vs dicoba),
- ``weekly_trend`` (deret mingguan ISO ``YYYY-Www`` dan arah perubahan).
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.organ-quality-board.v1"


def _parse_week(raw_ts: Any) -> str:
    if not isinstance(raw_ts, str) or not raw_ts.strip():
        return "unknown"
    text = raw_ts.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return "unknown"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    iso = dt.astimezone(timezone.utc).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _load_receipts(path: Path) -> list[dict[str, Any]]:
    raw = Path(path).read_text(encoding="utf-8").strip()
    if not raw:
        return []
    if raw.startswith("["):
        return [dict(x) for x in json.loads(raw)]
    return [json.loads(ln) for ln in raw.splitlines() if ln.strip()]


def _load_grounding(path: Path) -> list[dict[str, Any]]:
    raw = Path(path).read_text(encoding="utf-8").strip()
    if not raw:
        return []
    if raw.startswith("["):
        return [dict(x) for x in json.loads(raw)]
    if raw.startswith("{") and "\n" not in raw:
        obj = json.loads(raw)
        if isinstance(obj, Mapping):
            for key in ("proposals", "results", "records", "items"):
                if isinstance(obj.get(key), list):
                    return [dict(x) for x in obj[key]]
            return [dict(obj)]
    return [json.loads(ln) for ln in raw.splitlines() if ln.strip()]


def build_organ_scoreboard(
    receipts: Sequence[Mapping[str, Any]],
    grounding_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Agregasi metrik kualitas + tren mingguan per organ dari receipts & grounding."""
    task_organ: dict[str, str] = {}
    task_week: dict[str, str] = {}

    for row in list(grounding_rows) + list(receipts):
        tid = row.get("task_id") or row.get("proposal_id")
        organ = row.get("organ") or row.get("provider")
        if isinstance(tid, str) and tid.strip():
            if isinstance(organ, str) and organ.strip():
                task_organ[tid.strip()] = organ.strip()
            ts = row.get("at") or row.get("ts") or row.get("measured_at")
            wk = _parse_week(ts)
            if wk != "unknown" and tid.strip() not in task_week:
                task_week[tid.strip()] = wk

    def _new_bucket() -> dict[str, Any]:
        return {
            "completed": 0,
            "failed": 0,
            "gate_blocked": 0,
            "proposals_seen": set(),
            "grounding_checked": 0,
            "mismatch_count": 0,
            "weeks": defaultdict(
                lambda: {
                    "completed": 0,
                    "failed": 0,
                    "gate_blocked": 0,
                    "proposals_seen": set(),
                    "grounding_checked": 0,
                    "mismatch_count": 0,
                }
            ),
        }

    stats: dict[str, dict[str, Any]] = defaultdict(_new_bucket)

    for r_idx, rec in enumerate(receipts):
        tid = str(rec.get("task_id") or f"rec-{r_idx}")
        organ = str(rec.get("organ") or rec.get("provider") or task_organ.get(tid) or "unknown").strip() or "unknown"
        status = str(rec.get("status") or "").strip().lower()
        wk = _parse_week(rec.get("at") or rec.get("ts"))
        if wk == "unknown":
            wk = task_week.get(tid, "unknown")

        b = stats[organ]
        wb = b["weeks"][wk]

        if status != "started":
            b["proposals_seen"].add(tid)
            wb["proposals_seen"].add(tid)

        if status == "completed":
            b["completed"] += 1
            wb["completed"] += 1
        elif status == "failed":
            b["failed"] += 1
            wb["failed"] += 1
        elif status == "blocked" or rec.get("gate_blocked") is True or rec.get("gate_reason"):
            b["gate_blocked"] += 1
            wb["gate_blocked"] += 1

    for g_idx, g in enumerate(grounding_rows):
        tid = str(g.get("task_id") or g.get("proposal_id") or f"grd-{g_idx}")
        organ = str(g.get("organ") or g.get("provider") or task_organ.get(tid) or "unknown").strip() or "unknown"
        wk = _parse_week(g.get("at") or g.get("ts") or g.get("measured_at"))
        if wk == "unknown":
            wk = task_week.get(tid, "unknown")

        b = stats[organ]
        wb = b["weeks"][wk]
        b["proposals_seen"].add(tid)
        wb["proposals_seen"].add(tid)
        b["grounding_checked"] += 1
        wb["grounding_checked"] += 1

        is_mismatch = (
            g.get("grounded") is False
            or int(g.get("mismatch_count", 0)) > 0
            or str(g.get("status") or "").lower() in {"mismatch", "ungrounded", "failed"}
        )
        if is_mismatch:
            b["mismatch_count"] += 1
            wb["mismatch_count"] += 1

    organs_out: dict[str, dict[str, Any]] = {}
    for organ in sorted(stats):
        b = stats[organ]
        exec_total = b["completed"] + b["failed"]
        exec_rate = round(b["completed"] / exec_total, 6) if exec_total > 0 else None
        prop_total = max(len(b["proposals_seen"]), exec_total + b["gate_blocked"])
        gate_rate = round(b["gate_blocked"] / prop_total, 6) if prop_total > 0 else None
        mismatch_rate = (
            round(b["mismatch_count"] / b["grounding_checked"], 6)
            if b["grounding_checked"] > 0
            else None
        )

        weekly: list[dict[str, Any]] = []
        for wk in sorted(b["weeks"]):
            if wk == "unknown":
                continue
            wb = b["weeks"][wk]
            w_exec = wb["completed"] + wb["failed"]
            w_exec_rate = round(wb["completed"] / w_exec, 6) if w_exec > 0 else None
            w_prop = max(len(wb["proposals_seen"]), w_exec + wb["gate_blocked"])
            w_gate_rate = round(wb["gate_blocked"] / w_prop, 6) if w_prop > 0 else None
            w_mis_rate = (
                round(wb["mismatch_count"] / wb["grounding_checked"], 6)
                if wb["grounding_checked"] > 0
                else None
            )
            weekly.append(
                {
                    "week": wk,
                    "completed": wb["completed"],
                    "failed": wb["failed"],
                    "execution_success_rate": w_exec_rate,
                    "mismatch_rate": w_mis_rate,
                    "gate_block_rate": w_gate_rate,
                }
            )

        rates_series = [w["execution_success_rate"] for w in weekly if w["execution_success_rate"] is not None]
        if len(rates_series) < 2:
            trend_dir = "single_week_or_empty"
        elif rates_series[-1] - rates_series[0] > 1e-6:
            trend_dir = "improving"
        elif rates_series[-1] - rates_series[0] < -1e-6:
            trend_dir = "degrading"
        else:
            trend_dir = "stable"

        organs_out[organ] = {
            "organ": organ,
            "completed": b["completed"],
            "failed": b["failed"],
            "execution_attempts": exec_total,
            "execution_success_rate": exec_rate,
            "gate_blocked_count": b["gate_blocked"],
            "proposals_evaluated": prop_total,
            "gate_block_rate": gate_rate,
            "grounding_checked": b["grounding_checked"],
            "mismatch_count": b["mismatch_count"],
            "grounding_mismatch_rate": mismatch_rate,
            "trend_direction": trend_dir,
            "weekly_trend": weekly,
        }

    return {
        "schema": SCHEMA,
        "summary": {
            "organ_count": len(organs_out),
            "organs": sorted(organs_out.keys()),
        },
        "by_organ": organs_out,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hitung papan skor kualitas per organ dari receipts dan grounding."
    )
    parser.add_argument("--receipts", required=True, help="Path berkas receipts JSON/JSONL.")
    parser.add_argument("--grounding", required=True, help="Path berkas laporan grounding JSON/JSONL.")
    parser.add_argument("--out", help="Path output JSON opsional (default stdout).")
    args = parser.parse_args(argv)

    try:
        receipts = _load_receipts(Path(args.receipts))
        grounding = _load_grounding(Path(args.grounding))
        report = build_organ_scoreboard(receipts, grounding)
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
