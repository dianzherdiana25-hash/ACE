#!/usr/bin/env python3
"""Baca tiga sinyal watchdog dalam satu proses agar kegagalan terlokalisasi.

Bridge yang gagal memberi exit 2. Jika bridge sehat, pump tidak ada atau
status engine nonaktif, stale, atau tidak sah memberi exit 1. Ketiganya sehat
memberi 0. PID pump diperiksa dengan sinyal 0.

Engine yang berhenti tetap stopped berapa pun usianya. Engine yang running
menjadi stale bila usia updated_at melampaui ambang (default 300 detik).
Tepat pada ambang masih sehat. Status lama tanpa updated_at mengikuti running.
"""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

if __package__:
    from .engine_status import (
        DEFAULT_MAX_AGE_SECONDS,
        format_for_house_check,
        parse_engine_status,
    )
else:
    from engine_status import (
        DEFAULT_MAX_AGE_SECONDS,
        format_for_house_check,
        parse_engine_status,
    )


def pid_present(pid):
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def bridge_healthy(url, timeout):
    try:
        parts = urlsplit(url)
        if (parts.scheme not in {"http", "https"} or not parts.hostname
                or parts.username or parts.query or parts.fragment):
            return False
        with urlopen(url.rstrip("/") + "/health", timeout=timeout) as response:
            data = json.loads(response.read(65_537))
        return isinstance(data, dict) and data.get("ok") is True
    except (ValueError, OSError):
        return False


def inspect_house(bridge_url, pump_pid_file, engine_status, *, timeout=2,
                  health_probe=bridge_healthy, pid_probe=pid_present,
                  max_age_seconds=DEFAULT_MAX_AGE_SECONDS, now=None):
    if type(max_age_seconds) is not int or max_age_seconds < 0:
        raise ValueError("Ambang usia wajib bilangan bulat nonnegatif.")
    bridge = health_probe(bridge_url, timeout)
    try:
        pump_pid = int(pump_pid_file.read_text(encoding="utf-8").strip())
        if not 0 < pump_pid <= 2**31 - 1:
            raise ValueError
        pump = {"state": "healthy" if pid_probe(pump_pid) else "missing", "pid": pump_pid}
    except (OSError, ValueError):
        pump = {"state": "unavailable"}

    engine = format_for_house_check(
        parse_engine_status(engine_status, max_age_seconds=max_age_seconds, now=now)
    )
    code = 2 if not bridge else int(any(unit["state"] != "healthy" for unit in (pump, engine)))
    return {"schema": "ace.house-check.v1", "exit_code": code,
            "summary": ("healthy", "degraded", "dead")[code],
            "components": {"bridge": {"state": "healthy" if bridge else "unavailable"},
                           "pump": pump, "engine": engine}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge-url", required=True)
    parser.add_argument("--pump-pid-file", type=Path, required=True)
    parser.add_argument("--engine-status", type=Path, required=True)
    parser.add_argument("--max-age-seconds", type=int, default=DEFAULT_MAX_AGE_SECONDS)
    args = parser.parse_args(argv)
    try:
        result = inspect_house(args.bridge_url, args.pump_pid_file, args.engine_status,
                               max_age_seconds=args.max_age_seconds)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
