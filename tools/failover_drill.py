"""Perencana drill failover deterministik & pengisi formulir laporan waktu (AG86).

Menyusun rencana drill failover berdasar ``seed`` (jam acak deterministik dari
``random.Random(seed)``, urutan matikan komponen, daftar periksa ambil-alih,
serta templat formulir laporan waktu) tanpa mengeksekusi penghentian apa pun.
Menyediakan subperintah ``plan`` dan ``fill-report``.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import random
import sys
from typing import Any, Mapping, Sequence


SCHEMA = "ace.failover-drill-plan.v1"
TIME_REPORT_SCHEMA = "ace.failover-drill-time-report.v1"
DEFAULT_COMPONENTS: tuple[str, ...] = (
    "bridge_relay_pump",
    "brain_bridge_primary",
    "engine_cycle_worker",
)


def _parse_utc(raw: str) -> datetime:
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError(f"Timestamp wajib berzona waktu ISO: {raw!r}")
    return dt.astimezone(timezone.utc)


def build_failover_drill_plan(
    *,
    seed: int,
    window_date: str = "2026-11-25",
    components: Sequence[str] = DEFAULT_COMPONENTS,
) -> dict[str, Any]:
    """Susun rencana drill failover deterministik dari ``seed`` tanpa menyentuh proses live."""
    if type(seed) is not int:
        raise ValueError("seed wajib berupa integer.")
    if not components:
        raise ValueError("Daftar komponen drill tidak boleh kosong.")
    day_obj = date.fromisoformat(window_date)

    rng = random.Random(seed)
    planned_hour = rng.randint(1, 22)
    planned_minute = rng.randint(0, 59)
    planned_dt = datetime(
        day_obj.year, day_obj.month, day_obj.day, planned_hour, planned_minute, 0, tzinfo=timezone.utc
    )
    planned_utc = planned_dt.isoformat().replace("+00:00", "Z")

    # Urutan matikan acak terdeterministik dari seed atas salinan daftar komponen.
    shuffled = list(components)
    rng.shuffle(shuffled)
    shutdown_sequence = [
        {
            "step": idx,
            "component": comp,
            "planned_action": f"quiesce_and_stop:{comp} (PLAN ONLY — TIDAK DIEKSEKUSI)",
            "executed": False,
        }
        for idx, comp in enumerate(shuffled, 1)
    ]

    takeover_checklist = [
        {
            "check_id": "chk-01-precheck",
            "phase": "before",
            "item": "Pastikan cadangan checkpoint terbaru terverifikasi hash.",
            "checked": False,
        },
        {
            "check_id": "chk-02-health",
            "phase": "during",
            "item": "Konfirmasi failover endpoint cadangan menanggapi /health ok=true.",
            "checked": False,
        },
        {
            "check_id": "chk-03-rollback",
            "phase": "after",
            "item": "Verifikasi tidak ada tugas rusak/terulang setelah ambil-alih.",
            "checked": False,
        },
    ]

    drill_id = f"drill-{day_obj.strftime('%Y%m%d')}-s{seed}"
    blank_report = {
        "schema": TIME_REPORT_SCHEMA,
        "drill_id": drill_id,
        "seed": seed,
        "planned_utc": planned_utc,
        "status": "BLANK",
        "operator_id": None,
        "timestamps": {
            "t_trigger": None,
            "t_detected": None,
            "t_takeover_complete": None,
            "t_health_verified": None,
        },
        "metrics_seconds": {
            "detection_latency": None,
            "takeover_duration": None,
            "recovery_verify_duration": None,
            "total_rto": None,
        },
        "notes": "",
    }

    return {
        "schema": SCHEMA,
        "plan_only": True,
        "executes_shutdown": False,
        "drill_id": drill_id,
        "seed": seed,
        "window_date": window_date,
        "planned_utc": planned_utc,
        "planned_hour_utc": planned_hour,
        "planned_minute_utc": planned_minute,
        "shutdown_sequence": shutdown_sequence,
        "takeover_checklist": takeover_checklist,
        "time_report_template": blank_report,
    }


def fill_time_report(
    plan_or_template: Mapping[str, Any],
    *,
    t_trigger: str,
    t_detected: str,
    t_takeover_complete: str,
    t_health_verified: str,
    operator_id: str = "operator-fixture",
    notes: str = "",
) -> dict[str, Any]:
    """Isi formulir laporan waktu kosong dari rencana drill dan hitung metrik RTO."""
    template = (
        plan_or_template["time_report_template"]
        if isinstance(plan_or_template.get("time_report_template"), Mapping)
        else plan_or_template
    )
    if not isinstance(template, Mapping) or "drill_id" not in template:
        raise ValueError("Templat laporan waktu drill tidak sah.")

    dt_trig = _parse_utc(t_trigger)
    dt_det = _parse_utc(t_detected)
    dt_take = _parse_utc(t_takeover_complete)
    dt_ver = _parse_utc(t_health_verified)

    if not (dt_trig <= dt_det <= dt_take <= dt_ver):
        raise ValueError(
            "Urutan stempel waktu wajib monoton: t_trigger <= t_detected <= t_takeover_complete <= t_health_verified"
        )

    return {
        "schema": TIME_REPORT_SCHEMA,
        "drill_id": template["drill_id"],
        "seed": template["seed"],
        "planned_utc": template["planned_utc"],
        "status": "FILLED",
        "operator_id": str(operator_id or "operator-fixture").strip(),
        "timestamps": {
            "t_trigger": dt_trig.isoformat().replace("+00:00", "Z"),
            "t_detected": dt_det.isoformat().replace("+00:00", "Z"),
            "t_takeover_complete": dt_take.isoformat().replace("+00:00", "Z"),
            "t_health_verified": dt_ver.isoformat().replace("+00:00", "Z"),
        },
        "metrics_seconds": {
            "detection_latency": round((dt_det - dt_trig).total_seconds(), 3),
            "takeover_duration": round((dt_take - dt_det).total_seconds(), 3),
            "recovery_verify_duration": round((dt_ver - dt_take).total_seconds(), 3),
            "total_rto": round((dt_ver - dt_trig).total_seconds(), 3),
        },
        "notes": notes.strip(),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Susun rencana drill failover dari seed dan isi laporan waktu."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan", help="Susun rencana drill failover deterministik.")
    p_plan.add_argument("--seed", type=int, required=True)
    p_plan.add_argument("--date", default="2026-11-25")
    p_plan.add_argument("--out")

    p_fill = sub.add_parser("fill-report", help="Isi formulir laporan waktu kosong dari rencana.")
    p_fill.add_argument("--plan", required=True, help="Path JSON rencana drill atau templat kosong.")
    p_fill.add_argument("--t-trigger", required=True)
    p_fill.add_argument("--t-detected", required=True)
    p_fill.add_argument("--t-takeover-complete", required=True)
    p_fill.add_argument("--t-health-verified", required=True)
    p_fill.add_argument("--operator", default="operator-fixture")
    p_fill.add_argument("--notes", default="")
    p_fill.add_argument("--out")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "plan":
            result = build_failover_drill_plan(seed=args.seed, window_date=args.date)
        else:
            plan_doc = json.loads(Path(args.plan).read_text(encoding="utf-8"))
            result = fill_time_report(
                plan_doc,
                t_trigger=args.t_trigger,
                t_detected=args.t_detected,
                t_takeover_complete=args.t_takeover_complete,
                t_health_verified=args.t_health_verified,
                operator_id=args.operator,
                notes=args.notes,
            )
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
