#!/usr/bin/env python3
"""Jalankan relay protokol bridge dengan spool yang dipilih operator."""

import argparse
from collections.abc import Callable
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import time

_CODE_DIR = str(Path(__file__).resolve().parents[1] / "code")
if _CODE_DIR not in sys.path:
    sys.path.insert(0, _CODE_DIR)
from ace_operational import brain_bridge_relay as protocol


def enqueue_spool(spool: Path, call_id: str, payload: dict, *, now: Callable[[], float] = time.time) -> Path:
    """Tulis satu entri permintaan ke spool/req secara deterministik."""
    req_dir = spool / "req"
    req_dir.mkdir(parents=True, exist_ok=True)
    record = {**payload, "call_id": call_id, "ts": payload.get("ts", now())}
    target = req_dir / f"{call_id}.json"
    tmp = req_dir / f".{call_id}.json.tmp"
    tmp.write_text(json.dumps(record, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, target)
    return target


def drain_spool_with_backoff(
    spool: Path,
    upstream: Callable[[dict], dict],
    *,
    base_delay: float = 0.5,
    factor: float = 2.0,
    max_delay: float = 30.0,
    max_attempts: int = 8,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> dict:
    """Kirim entri spool/req berurutan ke upstream dengan backoff menaik saat upstream gagal.

    Entri spool tetap utuh di disk selama upstream belum pulih, jeda antar-percobaan
    menaik (bukan busy-loop), dan setelah upstream pulih seluruh entri terkirim
    berurutan menurut (ts, nama_berkas).
    """
    if base_delay <= 0 or factor <= 1.0 or max_delay < base_delay or max_attempts <= 0:
        raise ValueError("Parameter backoff tidak sah.")
    req_dir = spool / "req"
    resp_dir = spool / "resp"
    corrupt_dir = spool / "corrupt"
    req_dir.mkdir(parents=True, exist_ok=True)
    resp_dir.mkdir(parents=True, exist_ok=True)

    entries = []
    skipped_corrupt: list[dict] = []
    for path in sorted(req_dir.glob("*.json")):
        if path.name.startswith(".") or path.is_symlink() or not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("entri spool wajib berupa objek JSON")
            ts_val = float(data.get("ts", 0.0))
        except (OSError, UnicodeDecodeError, ValueError, TypeError) as exc:
            corrupt_dir.mkdir(parents=True, exist_ok=True)
            os.replace(path, corrupt_dir / path.name)
            skipped_corrupt.append({"file": path.name, "reason": str(exc)})
            continue
        entries.append((ts_val, path.name, path, data))
    entries.sort(key=lambda item: (item[0], item[1]))

    backoff_delays: list[float] = []
    delivered_ids: list[str] = []
    attempt_timestamps: list[float] = []

    for _, _, req_path, payload in entries:
        call_id = str(payload.get("call_id") or req_path.stem)
        attempt = 0
        while True:
            attempt += 1
            attempt_timestamps.append(now())
            try:
                response = upstream(payload)
                if not isinstance(response, dict) or int(response.get("status", 502)) >= 500:
                    raise ConnectionError("upstream unavailable")
                break
            except Exception:
                if attempt >= max_attempts:
                    return {
                        "status": "exhausted",
                        "delivered_ids": delivered_ids,
                        "pending_count": len(list(req_dir.glob("*.json"))),
                        "backoff_delays": backoff_delays,
                        "attempt_timestamps": attempt_timestamps,
                        "skipped_corrupt": skipped_corrupt,
                    }
                delay = min(max_delay, base_delay * (factor ** (attempt - 1)))
                backoff_delays.append(delay)
                sleep(delay)

        resp_tmp = resp_dir / f".{call_id}.json.tmp"
        resp_target = resp_dir / f"{call_id}.json"
        resp_tmp.write_text(json.dumps(response, sort_keys=True, ensure_ascii=False), encoding="utf-8")
        os.replace(resp_tmp, resp_target)
        req_path.unlink()
        delivered_ids.append(call_id)

    return {
        "status": "drained",
        "delivered_ids": delivered_ids,
        "pending_count": len(list(req_dir.glob("*.json"))),
        "backoff_delays": backoff_delays,
        "attempt_timestamps": attempt_timestamps,
        "skipped_corrupt": skipped_corrupt,
    }


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
