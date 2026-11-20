#!/usr/bin/env python3
"""Pemeriksa mandiri kesehatan bridge + status engine dengan rencana perintah relight baca-saja (AG37).

Kenapa: saat bridge mati atau engine macet/stale, operator membutuhkan diagnosis
sekaligus rencana perintah relight yang siap telaah tanpa bahaya eksekusi otomatis
di luar kendali. Jam dapat diinjeksi agar pengujian batas stale deterministik.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import sys
from typing import Any

if __package__:
    from .house_check import DEFAULT_MAX_AGE_SECONDS, bridge_healthy
else:
    from house_check import DEFAULT_MAX_AGE_SECONDS, bridge_healthy


SCHEMA = "ace.bridge-self-check.v1"


def _inspect_engine_status(
    status_path: Path,
    *,
    max_age_seconds: int,
    now: datetime,
) -> tuple[str, dict[str, Any]]:
    try:
        raw = status_path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (OSError, UnicodeDecodeError, ValueError):
        return "status-rusak", {"state": "corrupt_or_unreadable", "reason": "invalid_json_or_missing"}

    if (
        not isinstance(payload, dict)
        or type(payload.get("running")) is not bool
        or type(payload.get("pid")) is not int
        or payload["pid"] <= 0
        or type(payload.get("cycle_count")) is not int
        or payload["cycle_count"] < 0
    ):
        return "status-rusak", {"state": "corrupt_or_unreadable", "reason": "invalid_schema"}

    if not payload["running"]:
        return "engine-stale", {"state": "stopped", "pid": payload["pid"], "cycle_count": payload["cycle_count"]}

    if "updated_at" not in payload:
        return "sehat", {"state": "healthy", "pid": payload["pid"], "cycle_count": payload["cycle_count"]}

    stamp = payload["updated_at"]
    if not isinstance(stamp, str):
        return "status-rusak", {"state": "corrupt_or_unreadable", "reason": "invalid_updated_at_type"}
    try:
        updated = datetime.fromisoformat(stamp)
    except ValueError:
        return "status-rusak", {"state": "corrupt_or_unreadable", "reason": "invalid_updated_at_format"}
    if updated.utcoffset() is None or now.utcoffset() is None:
        return "status-rusak", {"state": "corrupt_or_unreadable", "reason": "naive_timestamp"}

    age = (now - updated).total_seconds()
    if age < 0:
        return "status-rusak", {"state": "corrupt_or_unreadable", "reason": "future_timestamp", "age_seconds": age}

    if age > max_age_seconds:
        return "engine-stale", {
            "state": "stale",
            "pid": payload["pid"],
            "cycle_count": payload["cycle_count"],
            "age_seconds": age,
        }
    return "sehat", {
        "state": "healthy",
        "pid": payload["pid"],
        "cycle_count": payload["cycle_count"],
        "age_seconds": age,
    }


def _render_relight_plan(
    classification: str,
    bridge_url: str,
    engine_status_path: Path,
) -> str:
    quoted_status = shlex.quote(str(engine_status_path))
    quoted_url = shlex.quote(bridge_url.rstrip("/") + "/health")
    if classification == "sehat":
        return (
            "# RENCANA RELIGHT (NO-OP)\n"
            f"# Status: sehat — bridge ({bridge_url}) & engine ({engine_status_path}) segar.\n"
            "# Tidak ada perintah relight yang perlu dijalankan.\n"
        )
    if classification == "bridge-mati":
        return (
            "# RENCANA RELIGHT BRIDGE (TEKS SAJA — TIDAK DIEKSEKUSI)\n"
            f"curl --fail --silent --max-time 3 {quoted_url} || echo 'bridge unreachable'\n"
            "python3 tools/brain_bridge.py --port 8931 --state <STATE> --log <LOG> --helpers <HELPERS>\n"
            f"curl --fail --silent --max-time 3 {quoted_url}\n"
        )
    if classification == "engine-stale":
        return (
            "# RENCANA RELIGHT ENGINE STALE (TEKS SAJA — TIDAK DIEKSEKUSI)\n"
            f"cat {quoted_status}\n"
            "python3 tools/house_check.py --bridge-url "
            + shlex.quote(bridge_url)
            + f" --pump-pid-file <PUMP_PID> --engine-status {quoted_status}\n"
            "# Hentikan proses lama secara terkontrol lalu nyalakan ulang daemon engine.\n"
        )
    return (
        "# RENCANA PEMULIHAN STATUS ENGINE RUSAK (TEKS SAJA — TIDAK DIEKSEKUSI)\n"
        f"ls -la {quoted_status}\n"
        f"cat {quoted_status}\n"
        "# Periksa log daemon dan pulihkan berkas status engine sebelum menyalakan ulang proses.\n"
    )


def self_check(
    bridge_url: str,
    engine_status_path: Path,
    *,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    now: datetime | None = None,
    timeout: float = 2.0,
    health_probe: Callable[[str, float], bool] = bridge_healthy,
) -> dict[str, Any]:
    """Klasifikasikan kondisi bridge + engine dan kembalikan rencana perintah relight sebagai teks."""
    if type(max_age_seconds) is not int or max_age_seconds < 0:
        raise ValueError("--max-age-seconds wajib bilangan bulat nonnegatif.")
    current = now if now is not None else datetime.now(timezone.utc)
    bridge_ok = bool(health_probe(bridge_url, timeout))
    engine_cls, engine_detail = _inspect_engine_status(
        engine_status_path,
        max_age_seconds=max_age_seconds,
        now=current,
    )

    if not bridge_ok:
        classification = "bridge-mati"
    else:
        classification = engine_cls

    relight_plan = _render_relight_plan(classification, bridge_url, engine_status_path)
    return {
        "schema": SCHEMA,
        "executed_relight": False,
        "classification": classification,
        "bridge_ok": bridge_ok,
        "bridge_url": bridge_url,
        "engine_status_file": str(engine_status_path),
        "engine_detail": engine_detail,
        "needs_relight": classification != "sehat",
        "relight_plan": relight_plan,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge-url", required=True)
    parser.add_argument("--engine-status", required=True, type=Path)
    parser.add_argument("--max-age-seconds", type=int, default=DEFAULT_MAX_AGE_SECONDS)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--format", choices=("json", "plan"), default="json")
    args = parser.parse_args(argv)
    try:
        report = self_check(
            args.bridge_url,
            args.engine_status,
            max_age_seconds=args.max_age_seconds,
            timeout=args.timeout,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if args.format == "plan":
        sys.stdout.write(report["relight_plan"])
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    if report["classification"] == "sehat":
        return 0
    if report["classification"] == "bridge-mati":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
