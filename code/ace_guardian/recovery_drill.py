"""Hentikan proses fixture yang dibuat sendiri, pulihkan snapshot, lalu ukur waktu lokal."""
import argparse
from pathlib import Path
import selectors
import subprocess
import sys
from time import monotonic

from ._contracts import GuardianError, anchor, canonical, decode, identity, integer, read, schema
from .recovery_playbooks import execute

FIXTURE = "import time; print('fixture-ready', flush=True); time.sleep(30)"

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
    elapsed = int((monotonic() - started) * 1000)
    met = result["status"] == "fixture_recovered" and elapsed < maximum
    return {"status": result["status"], "process_exit": exit_code, "elapsed_ms": elapsed,
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
