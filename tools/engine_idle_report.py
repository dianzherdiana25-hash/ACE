"""Laporan waktu idle mesin dan jam habis anggaran per peran per hari (AG48).

Membaca log engine serta snapshot status secara read-only untuk menghitung:
- Total menit idle per hari (dari durasi eksplisit maupun interval antar-event idle),
- Timestamp pertama kali setiap peran mengalami kehabisan anggaran per hari,
- Tren pemanjangan siklus (``cycles_lengthening``) sebagai indikator pelambatan/exhaustion.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.engine-idle-report.v1"
_IDLE_STATES = frozenset({"idle", "waiting", "sleeping", "budget_exhausted", "quota_exhausted"})


def _parse_ts(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_records(path: Path) -> list[dict[str, Any]]:
    target = Path(path)
    if target.is_dir():
        rows: list[dict[str, Any]] = []
        for child in sorted(target.iterdir()):
            if child.is_file() and child.suffix in {".json", ".jsonl"}:
                rows.extend(_load_records(child))
        return rows

    raw = target.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    if raw.startswith("["):
        data = json.loads(raw)
        if isinstance(data, list):
            return [dict(item) for item in data if isinstance(item, Mapping)]
        return []
    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
            if isinstance(obj, Mapping):
                if isinstance(obj.get("snapshots"), list):
                    return [dict(item) for item in obj["snapshots"] if isinstance(item, Mapping)]
                return [dict(obj)]
        except json.JSONDecodeError:
            pass
    out: list[dict[str, Any]] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        obj = json.loads(s)
        if isinstance(obj, Mapping):
            out.append(dict(obj))
    return out


def _is_idle_record(rec: Mapping[str, Any]) -> bool:
    if rec.get("idle") is True:
        return True
    state = str(rec.get("state") or rec.get("status") or rec.get("mode") or "").strip().lower()
    return state in _IDLE_STATES


def _extract_exhausted_roles(rec: Mapping[str, Any]) -> list[str]:
    found: list[str] = []
    ev = str(rec.get("event") or rec.get("event_type") or "").strip().lower()
    if ev in {"budget_exhausted", "quota_exhausted"} or rec.get("budget_exhausted") is True:
        role = rec.get("role")
        if isinstance(role, str) and role.strip():
            found.append(role.strip())

    budgets = rec.get("budgets") or rec.get("roles")
    if isinstance(budgets, Mapping):
        for role_name, info in budgets.items():
            if not isinstance(info, Mapping):
                continue
            exhausted_flag = info.get("exhausted") is True
            remaining = info.get("remaining")
            used = info.get("used")
            limit = info.get("limit")
            rem_exhausted = (
                isinstance(remaining, (int, float))
                and not isinstance(remaining, bool)
                and remaining <= 0
            )
            quota_used_up = (
                isinstance(used, (int, float))
                and isinstance(limit, (int, float))
                and not isinstance(used, bool)
                and not isinstance(limit, bool)
                and limit > 0
                and used >= limit
            )
            if exhausted_flag or rem_exhausted or quota_used_up:
                found.append(str(role_name))
    return list(dict.fromkeys(found))


def build_idle_report(
    log_records: Sequence[Mapping[str, Any]],
    snapshot_records: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Hitung menit idle harian, siklus, dan waktu habis anggaran per peran."""
    timeline: list[tuple[datetime, int, Mapping[str, Any]]] = []
    for idx, rec in enumerate(list(log_records) + list(snapshot_records)):
        raw_ts = rec.get("ts") or rec.get("at") or rec.get("timestamp") or rec.get("updated_at")
        dt = _parse_ts(raw_ts)
        if dt is not None:
            timeline.append((dt, idx, rec))

    if not timeline:
        raise ValueError("Tidak ada catatan bertimestamp valid di log maupun snapshot.")

    timeline.sort(key=lambda item: (item[0], item[1]))

    daily_idle_seconds: dict[str, float] = defaultdict(float)
    daily_cycles: dict[str, list[float]] = defaultdict(list)
    daily_exhaustions: dict[str, dict[str, str]] = defaultdict(dict)
    first_exhaustion_overall: dict[str, str] = {}
    daily_event_count: dict[str, int] = defaultdict(int)
    daily_idle_events: dict[str, int] = defaultdict(int)

    for pos, (dt, _idx, rec) in enumerate(timeline):
        day = dt.strftime("%Y-%m-%d")
        ts_str = _format_ts(dt)
        daily_event_count[day] += 1

        cycle_sec = rec.get("cycle_seconds")
        if isinstance(cycle_sec, (int, float)) and not isinstance(cycle_sec, bool):
            daily_cycles[day].append(float(cycle_sec))

        for role in _extract_exhausted_roles(rec):
            if role not in daily_exhaustions[day]:
                daily_exhaustions[day][role] = ts_str
            if role not in first_exhaustion_overall:
                first_exhaustion_overall[role] = ts_str

        if _is_idle_record(rec):
            daily_idle_events[day] += 1
            explicit_sec = rec.get("idle_seconds")
            if explicit_sec is None and isinstance(rec.get("idle_minutes"), (int, float)):
                explicit_sec = float(rec["idle_minutes"]) * 60.0
            if isinstance(explicit_sec, (int, float)) and not isinstance(explicit_sec, bool):
                daily_idle_seconds[day] += max(0.0, float(explicit_sec))
            elif pos + 1 < len(timeline):
                next_dt = timeline[pos + 1][0]
                if next_dt > dt and next_dt.strftime("%Y-%m-%d") == day:
                    daily_idle_seconds[day] += (next_dt - dt).total_seconds()

    all_days = sorted(daily_event_count.keys())
    by_day: dict[str, dict[str, Any]] = {}
    for day in all_days:
        cycles = daily_cycles.get(day, [])
        first_c = cycles[0] if cycles else None
        last_c = cycles[-1] if cycles else None
        avg_c = round(sum(cycles) / len(cycles), 2) if cycles else None
        lengthening = bool(len(cycles) >= 2 and last_c is not None and first_c is not None and last_c > first_c)
        idle_min = round(daily_idle_seconds.get(day, 0.0) / 60.0, 4)
        exhaustions = dict(sorted(daily_exhaustions.get(day, {}).items()))
        healthy = idle_min == 0.0 and len(exhaustions) == 0 and not lengthening

        by_day[day] = {
            "day": day,
            "event_count": daily_event_count[day],
            "idle_event_count": daily_idle_events.get(day, 0),
            "idle_minutes": idle_min,
            "cycle_count": len(cycles),
            "first_cycle_seconds": first_c,
            "last_cycle_seconds": last_c,
            "avg_cycle_seconds": avg_c,
            "cycles_lengthening": lengthening,
            "budget_exhaustions": exhaustions,
            "healthy": healthy,
        }

    total_idle_min = round(sum(row["idle_minutes"] for row in by_day.values()), 4)
    exhausted_days = [day for day in all_days if by_day[day]["budget_exhaustions"]]
    healthy_days = [day for day in all_days if by_day[day]["healthy"]]

    return {
        "schema": SCHEMA,
        "summary": {
            "days_analyzed": len(all_days),
            "total_idle_minutes": total_idle_min,
            "exhausted_days": exhausted_days,
            "healthy_days": healthy_days,
            "first_exhaustion_per_role": dict(sorted(first_exhaustion_overall.items())),
        },
        "by_day": by_day,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analisis waktu idle harian dan timestamp habis anggaran per peran dari log engine."
    )
    parser.add_argument("--log", help="Path log JSON/JSONL engine.")
    parser.add_argument("--snapshots", help="Path berkas atau direktori snapshot status JSON/JSONL.")
    parser.add_argument("--out", help="Path output JSON opsional (default stdout).")
    args = parser.parse_args(argv)

    if not args.log and not args.snapshots:
        print("error: minimal --log atau --snapshots harus diberikan", file=sys.stderr)
        return 2

    try:
        logs = _load_records(Path(args.log)) if args.log else []
        snaps = _load_records(Path(args.snapshots)) if args.snapshots else []
        report = build_idle_report(logs, snaps)
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
