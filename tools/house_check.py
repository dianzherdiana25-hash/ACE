#!/usr/bin/env python3
"""Baca tiga sinyal watchdog dalam satu proses agar kegagalan terlokalisasi.

Bridge yang gagal memberi exit 2. Jika bridge sehat, pump tidak ada atau
status engine nonaktif/tidak sah memberi exit 1. Ketiganya sehat memberi 0.
PID pump diperiksa dengan sinyal 0. Status engine dinilai dari berkas.
"""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen


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
                  health_probe=bridge_healthy, pid_probe=pid_present):
    bridge = health_probe(bridge_url, timeout)
    try:
        pump_pid = int(pump_pid_file.read_text(encoding="utf-8").strip())
        if not 0 < pump_pid <= 2**31 - 1:
            raise ValueError
        pump = {"state": "healthy" if pid_probe(pump_pid) else "missing", "pid": pump_pid}
    except (OSError, ValueError):
        pump = {"state": "unavailable"}

    try:
        payload = json.loads(engine_status.read_text(encoding="utf-8"))
        if (not isinstance(payload, dict) or type(payload.get("running")) is not bool
                or type(payload.get("pid")) is not int or payload["pid"] <= 0
                or type(payload.get("cycle_count")) is not int or payload["cycle_count"] < 0):
            raise ValueError
        engine = {"state": "healthy" if payload["running"] else "stopped",
                  **{key: payload[key] for key in ("pid", "cycle_count", "running")}}
    except (OSError, ValueError):
        engine = {"state": "unavailable"}
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
    args = parser.parse_args(argv)
    result = inspect_house(args.bridge_url, args.pump_pid_file, args.engine_status)
    print(json.dumps(result, indent=2))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
