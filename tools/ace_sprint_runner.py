"""Normalize bounded ACE execution and emit a terminal status on launch failures."""

import argparse
import json
import sys
import time

from ace_bounded_runner import run


def execute(command, *, timeout, heartbeat, log, cwd=None):
    start = time.monotonic()
    try:
        result = run(command, timeout=timeout, heartbeat=heartbeat, log_file=log, cwd=cwd)
    except (FileNotFoundError, PermissionError) as error:
        return {"status": "BLOCKED_ENV", "exit_code": 125, "elapsed_s": round(time.monotonic()-start, 3),
                "log_file": log, "reason": type(error).__name__}
    except (OSError, ValueError, KeyboardInterrupt) as error:
        return {"status": "FAILED", "exit_code": 130 if isinstance(error, KeyboardInterrupt) else 1,
                "elapsed_s": round(time.monotonic()-start, 3), "log_file": log, "reason": type(error).__name__}
    if result["status"] == "OK":
        result["status"] = "COMPLETE"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", required=True, type=float)
    parser.add_argument("--heartbeat", required=True, type=float)
    parser.add_argument("--log", required=True)
    parser.add_argument("--cwd")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    result = execute(command, timeout=args.timeout, heartbeat=args.heartbeat, log=args.log, cwd=args.cwd)
    print(json.dumps(result, sort_keys=True), flush=True)
    return 124 if result["status"] == "TIMEOUT" else result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
