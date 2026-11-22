"""Hentikan proses fixture yang dibuat sendiri, pulihkan snapshot, lalu ukur waktu lokal."""
import argparse
from pathlib import Path
import selectors
import subprocess
import sys
from time import monotonic

from ._contracts import GuardianError, anchor, canonical, decode, identity, integer, read, schema
from ._snapshots import validate_manifest
from .recovery_playbooks import execute

FIXTURE = "import time; print('fixture-ready', flush=True); time.sleep(30)"

VERIFY_RESTART = """\
from hashlib import sha256
import json
import os
import stat
import sys

entries = json.load(sys.stdin)
def verify(record):
    directory = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY
    parts = record["path"].split("/")
    parent = os.open(".", directory)
    try:
        for piece in parts[:-1]:
            following = os.open(piece, directory, dir_fd=parent)
            os.close(parent)
            parent = following
        leaf = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(leaf, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or metadata.st_size != record["bytes"]:
                return False
            data = stream.read(record["bytes"] + 1)
        return len(data) == record["bytes"] and sha256(data).hexdigest() == record["sha256"]
    finally:
        os.close(parent)

try:
    if not all(verify(record) for record in entries):
        sys.exit(3)
except OSError:
    sys.exit(3)
print("verified-ready")
"""


def restart_fixture(target, manifest, *, deadline=3.0):
    records = validate_manifest(manifest)
    if target.is_symlink() or not target.is_dir():
        raise GuardianError("Restart perlu direktori fixture yang nyata.")
    completed = subprocess.run(
        [sys.executable, "-I", "-S", "-c", VERIFY_RESTART], cwd=target,
        input=canonical(records), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        timeout=deadline, check=False,
    )
    return {"exit_code": completed.returncode,
            "ready_verified": completed.returncode == 0 and completed.stdout == b"verified-ready\n",
            "manifest_sha256": identity(manifest)}


def terminate_fixture(*, deadline=3.0):
    with subprocess.Popen([sys.executable, "-I", "-S", "-c", FIXTURE], stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL) as process:
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                if not selector.select(deadline) or process.stdout.readline() != b"fixture-ready\n":
                    raise GuardianError("Proses fixture tidak siap.")
            start = monotonic()
            process.terminate()
            code = process.wait(timeout=deadline)
            if code >= 0:
                raise GuardianError("Proses fixture tidak mengalami penghentian yang direncanakan.")
            return start, code
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=deadline)

def drill(plan, expected, snapshot, failed, target):
    anchor(plan, expected)
    schema(plan, "ace.guardian.recovery-drill.v1", ("playbook", "limit_ms"))
    maximum = integer(plan["limit_ms"], "Batas drill", 1, 300_000)
    if plan["playbook"].get("fault") != "process_stopped":
        raise GuardianError("Drill proses memerlukan playbook process_stopped.")
    started, exit_code = terminate_fixture()
    result = execute(plan["playbook"], identity(plan["playbook"]), snapshot, failed, target)
    manifest = plan["playbook"]["rollback"]["verified_snapshot"]
    restart = restart_fixture(target, manifest) if result["status"] == "fixture_recovered" else None
    elapsed = int((monotonic() - started) * 1000)
    recovered = restart is not None and restart["ready_verified"]
    met = recovered and elapsed < maximum
    return {"status": "fixture_recovered" if recovered else "held",
            "process_exit": exit_code, "elapsed_ms": elapsed, "restart": restart,
            "under_limit": met, "limit_ms": maximum, "playbook": result, "scope": "local_fixture_subprocess"}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("plan", "snapshot", "failed", "target"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = drill(decode(read(args.plan)), args.expect_sha256, args.snapshot, args.failed, args.target)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        parser.exit(2, f"Error: {error}\n")
    sys.stdout.buffer.write(canonical(report) + b"\n")
    return 0 if report["under_limit"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
