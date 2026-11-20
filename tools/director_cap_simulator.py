"""Simulator kapasitas harian adaptif director dari log receipt JSONL (AG45).

Memutar ulang log receipt ``director_executor`` (field ``status`` dan ``at``)
per hari UTC (``at[:10]``) untuk menghitung cap harian berikutnya secara AIMD
(Additive Increase, Multiplicative Decrease) dengan aturan eksplisit:

1. Hitung peristiwa terminal per hari: ``completed`` dan ``failed``.
2. Jika ``terminal_total == 0``: tahan cap (``next_cap = cap``, ``no_terminal_events``).
3. Jika ``success_rate < shrink_threshold`` (default ``0.50``): turunkan cap
   secara multiplikatif ``next_cap = max(min_cap, cap // 2)`` (``low_success_rate_shrink``).
4. Jika ``success_rate >= promote_threshold`` (default ``0.85``) dan
   ``terminal_total >= min_samples`` (default ``1`` agar tidak terjebak di ``cap=1``):
   naikkan cap secara aditif ``next_cap = min(max_cap, cap + 1)`` (``high_success_rate_promote``).
5. Di antara kedua ambang: tahan cap (``hold_band``).
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.director-cap-simulator.v1"
DEFAULT_INITIAL_CAP = 2
DEFAULT_MIN_CAP = 1
DEFAULT_MAX_CAP = 10
DEFAULT_PROMOTE_THRESHOLD = 0.85
DEFAULT_SHRINK_THRESHOLD = 0.50
DEFAULT_MIN_SAMPLES = 1


def _extract_day(entry: Mapping[str, Any]) -> str | None:
    raw = entry.get("at") or entry.get("day") or entry.get("ts")
    if not isinstance(raw, str):
        return None
    stripped = raw.strip()
    if len(stripped) >= 10 and stripped[4:5] == "-" and stripped[7:8] == "-":
        return stripped[:10]
    return None


def load_receipt_events(receipts_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Baca baris JSONL receipt secara aman; baris cacat dilaporkan tanpa crash."""
    events: list[dict[str, Any]] = []
    malformed: list[dict[str, Any]] = []
    for line_no, raw in enumerate(
        Path(receipts_path).read_text(encoding="utf-8", errors="replace").splitlines(), 1
    ):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError as exc:
            malformed.append({"line": line_no, "reason": "invalid_json", "detail": str(exc)})
            continue
        if not isinstance(obj, dict):
            malformed.append({"line": line_no, "reason": "not_object"})
            continue
        events.append(obj)
    return events, malformed


def simulate_daily_caps(
    events: Sequence[Mapping[str, Any]],
    *,
    initial_cap: int = DEFAULT_INITIAL_CAP,
    min_cap: int = DEFAULT_MIN_CAP,
    max_cap: int = DEFAULT_MAX_CAP,
    promote_threshold: float = DEFAULT_PROMOTE_THRESHOLD,
    shrink_threshold: float = DEFAULT_SHRINK_THRESHOLD,
    min_samples: int = DEFAULT_MIN_SAMPLES,
) -> dict[str, Any]:
    """Simulasikan evolusi cap harian dari urutan peristiwa receipt."""
    if min_cap < 1 or max_cap < min_cap:
        raise ValueError("Rentang min_cap/max_cap tidak sah (wajib 1 <= min_cap <= max_cap).")
    if not (min_cap <= initial_cap <= max_cap):
        raise ValueError("initial_cap harus berada di antara min_cap dan max_cap.")
    if not (0.0 <= shrink_threshold <= promote_threshold <= 1.0):
        raise ValueError("Ambang wajib memenuhi 0 <= shrink_threshold <= promote_threshold <= 1.")

    buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"started": 0, "completed": 0, "failed": 0, "other": 0}
    )
    skipped_without_day = 0
    for ev in events:
        day = _extract_day(ev)
        if day is None:
            skipped_without_day += 1
            continue
        status = str(ev.get("status") or "").strip().lower()
        if status == "started":
            buckets[day]["started"] += 1
        elif status == "completed":
            buckets[day]["completed"] += 1
        elif status == "failed":
            buckets[day]["failed"] += 1
        else:
            buckets[day]["other"] += 1

    cap = initial_cap
    daily_trace: list[dict[str, Any]] = []
    promotions = 0
    shrinks = 0
    holds = 0
    cap_history = [cap]

    for day in sorted(buckets):
        counts = buckets[day]
        completed = counts["completed"]
        failed = counts["failed"]
        terminal_total = completed + failed
        cap_start = cap

        if terminal_total == 0:
            success_rate: float | None = None
            rule_applied = "no_terminal_events"
            cap_next = cap_start
            holds += 1
        else:
            success_rate = round(completed / terminal_total, 6)
            if success_rate < shrink_threshold:
                cap_next = max(min_cap, cap_start // 2)
                rule_applied = (
                    "low_success_rate_at_floor"
                    if cap_next == cap_start
                    else "low_success_rate_shrink"
                )
                shrinks += 1
            elif success_rate >= promote_threshold and terminal_total >= min_samples:
                cap_next = min(max_cap, cap_start + 1)
                rule_applied = (
                    "high_success_rate_at_ceiling"
                    if cap_next == cap_start
                    else "high_success_rate_promote"
                )
                promotions += 1
            else:
                cap_next = cap_start
                rule_applied = "hold_band"
                holds += 1

        cap = cap_next
        cap_history.append(cap_next)
        daily_trace.append(
            {
                "day": day,
                "cap_start": cap_start,
                "started": counts["started"],
                "completed": completed,
                "failed": failed,
                "terminal_total": terminal_total,
                "success_rate": success_rate,
                "cap_next": cap_next,
                "rule_applied": rule_applied,
            }
        )

    return {
        "schema": SCHEMA,
        "policy": {
            "initial_cap": initial_cap,
            "min_cap": min_cap,
            "max_cap": max_cap,
            "promote_threshold": promote_threshold,
            "shrink_threshold": shrink_threshold,
            "min_samples": min_samples,
        },
        "summary": {
            "days_replayed": len(daily_trace),
            "initial_cap": initial_cap,
            "final_cap": cap,
            "min_cap_observed": min(cap_history),
            "max_cap_observed": max(cap_history),
            "promotions": promotions,
            "shrinks": shrinks,
            "holds": holds,
            "skipped_without_day": skipped_without_day,
        },
        "daily_trace": daily_trace,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Simulasikan cap harian adaptif director dari berkas receipt JSONL."
    )
    parser.add_argument("--receipts", required=True, help="Path berkas receipt JSONL.")
    parser.add_argument("--initial-cap", type=int, default=DEFAULT_INITIAL_CAP)
    parser.add_argument("--min-cap", type=int, default=DEFAULT_MIN_CAP)
    parser.add_argument("--max-cap", type=int, default=DEFAULT_MAX_CAP)
    parser.add_argument("--promote-threshold", type=float, default=DEFAULT_PROMOTE_THRESHOLD)
    parser.add_argument("--shrink-threshold", type=float, default=DEFAULT_SHRINK_THRESHOLD)
    parser.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES)
    parser.add_argument("--out", help="Path output JSON opsional (default stdout).")
    args = parser.parse_args(argv)

    try:
        events, malformed = load_receipt_events(Path(args.receipts))
        report = simulate_daily_caps(
            events,
            initial_cap=args.initial_cap,
            min_cap=args.min_cap,
            max_cap=args.max_cap,
            promote_threshold=args.promote_threshold,
            shrink_threshold=args.shrink_threshold,
            min_samples=args.min_samples,
        )
        report["malformed_lines"] = malformed
    except (OSError, ValueError) as exc:
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
