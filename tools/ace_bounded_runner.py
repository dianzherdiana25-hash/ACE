"""One-shot ACE command runner: explicit deadline, visible progress, fail closed.

Does not schedule work, resume a model session or modify GitHub.
Suitable for a verified local/Colab development environment. No dependencies.
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def run(command, *, timeout, heartbeat, log_file=None, cwd=None):
    if not command or timeout <= 0 or heartbeat <= 0:
        raise ValueError("command and positive timeout/heartbeat required")
    if log_file is not None:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    # Send stdout/stderr directly to log to avoid PIPE blocking and unbounded memory.
    with (open(log_file, "wb") if log_file else open(os.devnull, "wb")) as log:
        proc = subprocess.Popen(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)
        last_notice = started
        deadline = started + timeout
        try:
            while True:
                code = proc.poll()
                now = time.monotonic()
                if code is not None:
                    return {"status": "OK" if code == 0 else "FAILED",
                            "exit_code": code, "elapsed_s": round(now - started, 3),
                            "log_file": str(log_file) if log_file else None}
                if now >= deadline:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait(timeout=2)
                    return {"status": "TIMEOUT", "exit_code": proc.returncode,
                            "elapsed_s": round(time.monotonic() - started, 3),
                            "log_file": str(log_file) if log_file else None}
                if now - last_notice >= heartbeat:
                    print(f"ACE HEARTBEAT elapsed={now-started:.1f}s pid={proc.pid}",
                          file=sys.stderr, flush=True)
                    last_notice = now
                time.sleep(min(0.1, max(0.01, deadline-now)))
        except BaseException:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=2)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--heartbeat", type=float, default=10.0)
    parser.add_argument("--log", required=True)
    parser.add_argument("--cwd")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    result = run(command, timeout=args.timeout, heartbeat=args.heartbeat,
                 log_file=args.log, cwd=args.cwd)
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0 if result["status"] == "OK" else (124 if result["status"] == "TIMEOUT" else 1)


if __name__ == "__main__":
    sys.exit(main())
