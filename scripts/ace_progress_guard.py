"""Fail-visible synchronous command supervisor for ACE research runs.

Runs an existing (trusted) research command without changing its algorithm or
isolation environment. Provides atomic checkpoint states and bounded runtime.
Never silently retries a failed scientific arm or declares a result validated.
"""
import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp." + str(os.getpid()))
    try:
        temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def file_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def run(args):
    cmd = args.command
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        raise ValueError("missing executable after --")
    if args.timeout <= 0 or args.heartbeat <= 0:
        raise ValueError("timeout and heartbeat must be positive")
    state_path = args.state.resolve()
    cwd = args.cwd.resolve()
    if not cwd.is_dir():
        raise ValueError("cwd does not exist")
    identity = {"cmd": cmd, "cwd": str(cwd), "source_commit": args.source_commit}
    job_sha = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    if state_path.exists():
        old = json.loads(state_path.read_text(encoding="utf-8"))
        if old.get("status") == "COMPLETE" and old.get("job_sha256") == job_sha:
            stdout = Path(old.get("stdout", ""))
            stderr = Path(old.get("stderr", ""))
            if stdout.is_file() and stderr.is_file() and old.get("stdout_sha256") == file_hash(stdout) and old.get("stderr_sha256") == file_hash(stderr):
                print("ALREADY_COMPLETE: verified existing command output; no duplicate run")
                return 0
        if not args.recover:
            print("BLOCKED_EXISTING_CHECKPOINT: inspect existing run; --recover requires explicit intent", file=sys.stderr)
            return 3
        if old.get("status") == "RUNNING":
            print("RECOVERY_REQUIRED: prior RUNNING state cannot be proven terminal; no silent rerun", file=sys.stderr)
            return 4
    out_path = state_path.with_suffix(".stdout")
    err_path = state_path.with_suffix(".stderr")
    state = dict(identity, job_sha256=job_sha, status="RUNNING", started_at=stamp(),
                 updated_at=stamp(), heartbeat_interval_s=args.heartbeat,
                 deadline_s=args.timeout, stdout=str(out_path), stderr=str(err_path))
    write_json_atomic(state_path, state)
    begin = time.monotonic()
    try:
        with out_path.open("wb") as out, err_path.open("wb") as err:
            process = subprocess.Popen(cmd, cwd=cwd, stdout=out, stderr=err,
                                       start_new_session=True, close_fds=True)
            state["pid"] = process.pid
            write_json_atomic(state_path, state)
            last_beat = begin
            while process.poll() is None:
                now = time.monotonic()
                if now - begin >= args.timeout:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                    state["status"] = "TIMEOUT"
                    state["error"] = "deadline exceeded; no automatic retry"
                    break
                if now - last_beat >= args.heartbeat:
                    state["updated_at"] = stamp()
                    state["elapsed_s"] = round(now - begin, 3)
                    write_json_atomic(state_path, state)
                    last_beat = now
                time.sleep(min(0.10, max(0.01, args.heartbeat / 2)))
            if state["status"] != "TIMEOUT":
                state["status"] = "COMPLETE" if process.returncode == 0 else "FAILED"
                if process.returncode != 0:
                    state["error"] = "nonzero command exit; no automatic retry"
            state["exit_code"] = process.returncode
    except (OSError, ValueError) as e:
        state["status"] = "INFRA_FAILURE"
        state["error"] = type(e).__name__ + ": " + str(e)
        state["exit_code"] = None
    state["elapsed_s"] = round(time.monotonic() - begin, 3)
    state["updated_at"] = stamp()
    state["stdout_sha256"] = file_hash(out_path) if out_path.exists() else None
    state["stderr_sha256"] = file_hash(err_path) if err_path.exists() else None
    write_json_atomic(state_path, state)
    print(state["status"] + ": " + str(state_path) + " (" + str(state["elapsed_s"]) + "s)")
    return 0 if state["status"] == "COMPLETE" else 124 if state["status"] == "TIMEOUT" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--heartbeat", type=float, default=5)
    parser.add_argument("--recover", action="store_true", help="accept explicit retry of terminal failures")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
