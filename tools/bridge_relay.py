#!/usr/bin/env python3
"""Jalankan relay protokol bridge dengan spool yang dipilih operator."""

import argparse
from http.server import ThreadingHTTPServer
import os
from pathlib import Path
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from ace_operational import brain_bridge_relay as protocol


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spool", type=Path, default=os.environ.get("ACE_RELAY_SPOOL"))
    parser.add_argument("--port", type=int, default=os.environ.get("ACE_RELAY_PORT", "18931"))
    parser.add_argument("--timeout", type=int, default=os.environ.get("ACE_RELAY_TIMEOUT", "240"))
    args = parser.parse_args(argv)
    if args.spool is None or not 0 <= args.port <= 65_535 or args.timeout <= 0:
        parser.error("Berikan spool, port yang sah, dan timeout positif.")
    protocol.SPOOL = args.spool
    protocol.REQ, protocol.RESP = args.spool / "req", args.spool / "resp"
    protocol.TIMEOUT_S = args.timeout
    with ThreadingHTTPServer(("127.0.0.1", args.port), protocol.Handler) as service:
        print(f"sandbox relay on 127.0.0.1:{service.server_port}", flush=True)
        threading.Thread(target=protocol._models_refresher, daemon=True).start()
        service.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
