#!/usr/bin/env python3
"""Jalankan protokol bridge yang sudah ada dengan jalur rumah yang eksplisit."""

import argparse
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from ace_operational import brain_bridge as protocol


def _safe_organ_call(callback):
    def call(*args):
        try:
            return callback(*args)
        except Exception:
            # Keluaran helper luar dapat membawa informasi konfigurasi privat.
            raise RuntimeError("organ helper unavailable") from None
    return call


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=os.environ.get("ACE_BRIDGE_PORT", "8931"))
    parser.add_argument("--state", type=Path, default=os.environ.get("ACE_BRIDGE_STATE"))
    parser.add_argument("--log", type=Path, default=os.environ.get("ACE_BRIDGE_LOG"))
    parser.add_argument("--helpers", type=Path, default=os.environ.get("ACE_BRIDGE_HELPERS"))
    parser.add_argument("--budgets", type=Path, default=os.environ.get("ACE_BRIDGE_BUDGETS"))
    args = parser.parse_args(argv)
    if args.state is None or args.log is None or args.helpers is None:
        parser.error("--state, --log, dan --helpers wajib diberikan lewat argumen atau env.")
    if not 0 <= args.port <= 65_535 or args.state.resolve() == args.log.resolve():
        parser.error("Port atau jalur state/log tidak sah.")
    budgets = protocol.BUDGETS
    if args.budgets:
        try:
            budgets = json.loads(args.budgets.read_text(encoding="utf-8"))
            if (not isinstance(budgets, dict) or budgets.keys() != protocol.ROLE_MAP.keys()
                    or any(type(cap) is not int or cap < 0 for cap in budgets.values())):
                raise ValueError
        except (OSError, ValueError):
            parser.error("Berkas budget wajib memuat integer nonnegatif untuk semua role bridge.")
    protocol.STATE = args.state
    protocol.LOG = args.log
    protocol.HELPERS = args.helpers
    protocol.BUDGETS = budgets
    protocol.call_helper = _safe_organ_call(protocol.call_helper)
    protocol.embed_helper = _safe_organ_call(protocol.embed_helper)
    with ThreadingHTTPServer(("127.0.0.1", args.port), protocol.Handler) as service:
        print(f"brain bridge on 127.0.0.1:{service.server_port}", flush=True)
        service.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
