"""Manifes registry perkakas tempaan dan evaluasi calon pensiun berkala (AG82).

Mengelola dan memvalidasi manifes registry perkakas (``name``, ``version``,
``origin_gap``, ``status``) serta mengevaluasi log pemakaian fixture secara
read-only untuk menandai perkakas tak terpakai atau gagal berulang sebagai
calon pensiun (``retire_candidate``).
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.tool-registry.v1"
ALLOWED_STATUSES = frozenset({"candidate", "adopted", "retired"})
DEFAULT_UNUSED_DAYS = 30
DEFAULT_MAX_FAILURE_RATE = 0.50
DEFAULT_MIN_FAIL_CALLS = 3


def _parse_utc(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        dt = raw
    elif isinstance(raw, str) and raw.strip():
        text = raw.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def validate_registry(registry: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validasi skema manifes registry perkakas dan kembalikan entri terkanonisasi."""
    raw_items = (
        registry.get("tools")
        if isinstance(registry, Mapping)
        else registry
    )
    if not isinstance(raw_items, Sequence) or isinstance(raw_items, (str, bytes)) or not raw_items:
        raise ValueError("Manifes registry wajib memuat daftar 'tools' tak-kosong.")

    seen_names: set[str] = set()
    validated: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_items, 1):
        if not isinstance(item, Mapping):
            raise ValueError(f"Entri registry[{idx}] wajib berupa objek.")
        name = str(item.get("name") or "").strip()
        version = str(item.get("version") or "").strip()
        origin_gap = str(item.get("origin_gap") or "").strip()
        status = str(item.get("status") or "").strip().lower()
        if not name or not version or not origin_gap:
            raise ValueError(f"Entri registry[{idx}] kekurangan name/version/origin_gap.")
        if status not in ALLOWED_STATUSES:
            raise ValueError(f"Status perkakas {name!r} tidak sah: {status!r}.")
        if name in seen_names:
            raise ValueError(f"Nama perkakas duplikat di registry: {name!r}.")
        seen_names.add(name)
        validated.append(
            {
                "name": name,
                "version": version,
                "origin_gap": origin_gap,
                "status": status,
                "registered_at": item.get("registered_at"),
            }
        )
    return validated


def evaluate_registry(
    registry: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    usage_events: Sequence[Mapping[str, Any]],
    *,
    as_of: datetime | str,
    unused_days: int = DEFAULT_UNUSED_DAYS,
    max_failure_rate: float = DEFAULT_MAX_FAILURE_RATE,
    min_calls_for_failure: int = DEFAULT_MIN_FAIL_CALLS,
) -> dict[str, Any]:
    """Evaluasi berkala pemakaian tiap perkakas dan tandai calon pensiun."""
    as_of_dt = _parse_utc(as_of)
    if as_of_dt is None:
        raise ValueError(f"Tanggal acuan as_of tidak sah: {as_of!r}")
    if unused_days < 0 or not 0.0 <= max_failure_rate <= 1.0 or min_calls_for_failure < 1:
        raise ValueError("Parameter ambang evaluasi registry tidak sah.")

    tools = validate_registry(registry)
    usage_map: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"calls": 0, "successes": 0, "failures": 0, "last_used": None}
    )

    for ev in usage_events:
        if not isinstance(ev, Mapping):
            continue
        tname = str(ev.get("tool") or ev.get("name") or "").strip()
        if not tname:
            continue
        bucket = usage_map[tname]
        bucket["calls"] += 1
        ok = ev.get("success")
        if ok is None:
            ok = str(ev.get("status") or "").strip().lower() in {"ok", "success", "passed"}
        if ok:
            bucket["successes"] += 1
        else:
            bucket["failures"] += 1
        ev_dt = _parse_utc(ev.get("ts") or ev.get("at"))
        if ev_dt is not None and (bucket["last_used"] is None or ev_dt > bucket["last_used"]):
            bucket["last_used"] = ev_dt

    reports: list[dict[str, Any]] = []
    retire_candidates: list[str] = []
    keep_active: list[str] = []

    for tool in sorted(tools, key=lambda t: t["name"]):
        tname = tool["name"]
        st = usage_map.get(tname, {"calls": 0, "successes": 0, "failures": 0, "last_used": None})
        calls = st["calls"]
        failures = st["failures"]
        fail_rate = round(failures / calls, 6) if calls > 0 else 0.0

        last_dt = st["last_used"] or _parse_utc(tool.get("registered_at"))
        idle_days: float | None = (
            max(0.0, round((as_of_dt - last_dt).total_seconds() / 86400.0, 2))
            if last_dt is not None
            else None
        )

        reasons: list[str] = []
        if tool["status"] == "retired":
            recommendation = "already_retired"
            reasons.append("already_retired_in_manifest")
        else:
            if calls == 0:
                reasons.append("unused_zero_calls")
            elif idle_days is not None and idle_days > unused_days:
                reasons.append(f"unused_past_threshold:{idle_days}>{unused_days}d")
            if calls >= min_calls_for_failure and fail_rate >= max_failure_rate:
                reasons.append(f"repeated_failures:rate={fail_rate}>={max_failure_rate}")

            if reasons:
                recommendation = "retire_candidate"
                retire_candidates.append(tname)
            else:
                recommendation = "keep_active"
                reasons.append("healthy_active_usage")
                keep_active.append(tname)

        reports.append(
            {
                **tool,
                "calls": calls,
                "successes": st["successes"],
                "failures": failures,
                "failure_rate": fail_rate,
                "idle_days": idle_days,
                "recommendation": recommendation,
                "reasons": reasons,
            }
        )

    return {
        "schema": SCHEMA,
        "as_of": as_of_dt.isoformat().replace("+00:00", "Z"),
        "summary": {
            "total_tools": len(reports),
            "keep_active_count": len(keep_active),
            "retire_candidate_count": len(retire_candidates),
            "keep_active": keep_active,
            "retire_candidates": retire_candidates,
        },
        "tools": reports,
    }


def _load_usage(path: Path) -> list[dict[str, Any]]:
    raw = Path(path).read_text(encoding="utf-8").strip()
    if not raw:
        return []
    if raw.startswith("["):
        return [dict(x) for x in json.loads(raw)]
    return [json.loads(ln) for ln in raw.splitlines() if ln.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluasi manifes registry perkakas tempaan terhadap log pemakaian fixture."
    )
    parser.add_argument("--registry", required=True, help="Path manifes registry JSON.")
    parser.add_argument("--usage-log", required=True, help="Path log pemakaian JSON/JSONL.")
    parser.add_argument("--as-of", required=True, help="Timestamp acuan ISO UTC.")
    parser.add_argument("--unused-days", type=int, default=DEFAULT_UNUSED_DAYS)
    parser.add_argument("--max-failure-rate", type=float, default=DEFAULT_MAX_FAILURE_RATE)
    parser.add_argument("--min-fail-calls", type=int, default=DEFAULT_MIN_FAIL_CALLS)
    parser.add_argument("--out", help="Path output JSON opsional.")
    args = parser.parse_args(argv)

    try:
        registry = json.loads(Path(args.registry).read_text(encoding="utf-8"))
        usage = _load_usage(Path(args.usage_log))
        report = evaluate_registry(
            registry,
            usage,
            as_of=args.as_of,
            unused_days=args.unused_days,
            max_failure_rate=args.max_failure_rate,
            min_calls_for_failure=args.min_fail_calls,
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
