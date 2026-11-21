"""Jalankan resep numerik dalam proses lokal dengan batas address space.

Worker khusus memanggil optimizer yang sudah terdaftar. Parent
memeriksa ulang checkpoint terhadap rencana dan mempertahankan prefix
yang selesai ketika batas waktu atau memori tercapai. Output worker
yang tidak cocok tidak dipakai sebagai receipt.
"""
import argparse
from pathlib import Path
import resource
import subprocess
import sys

from . import train_runner
from ._forge_io import InputError, canonical, decode, digest, integer, read_bytes
from .dataset_forge import MAX_BYTES


MEMORY_EXIT = 73
INPUT_EXIT = 74
MIB = 1024**2


def _context(plan_path, bundle_path, expected_plan, checkpoint_path, expected_head):
    if (checkpoint_path is None) != (expected_head is None):
        raise InputError("Resume memerlukan checkpoint dan anchor head.")
    plan = decode(read_bytes(plan_path, MAX_BYTES))
    bundles = decode(read_bytes(bundle_path, MAX_BYTES))
    history = train_runner._load(checkpoint_path) if checkpoint_path is not None else []
    anchor = digest(expected_head) if expected_head is not None else train_runner.genesis(expected_plan)
    jobs, _ = train_runner._prepare(plan, bundles, expected_plan)
    train_runner._replay(history, jobs, expected_plan, anchor)
    return plan, bundles, history, anchor, jobs


def _set_memory(mib):
    requested = mib * MIB
    current, hard = resource.getrlimit(resource.RLIMIT_AS)
    inherited = [cap for cap in (current, hard) if cap != resource.RLIM_INFINITY]
    limit = min([requested, *inherited])
    resource.setrlimit(resource.RLIMIT_AS, (limit, hard))


def _worker(args):
    try:
        _set_memory(args.memory_mib)
        plan, bundles, history, anchor, _ = _context(
            args.plan, args.bundles, args.expect_plan_sha256, args.checkpoint_from, args.expect_head,
        )
        for record in train_runner.run(plan, bundles, args.expect_plan_sha256, checkpoints=history, expected_head=anchor):
            sys.stdout.buffer.write(canonical(record) + b"\n")
            sys.stdout.buffer.flush()
    except MemoryError:
        return MEMORY_EXIT
    except (OSError, ValueError, RecursionError, OverflowError):
        return INPUT_EXIT
    return 0


def _receipt_prefix(output, status):
    data = output or b""
    if not isinstance(data, bytes) or len(data) > train_runner.MAX_LOG_BYTES:
        raise InputError("Output worker tidak berupa checkpoint yang didukung.")
    if data and not data.endswith(b"\n"):
        if status == "complete":
            raise InputError("Worker selesai dengan checkpoint terpotong.")
        data = data[:data.rfind(b"\n") + 1]
    rows = []
    for blob in data.splitlines():
        item = decode(blob)
        if not isinstance(item, dict) or blob != canonical(item) or len(rows) >= train_runner.MAX_JOBS:
            raise InputError("Baris checkpoint worker tidak sah.")
        rows.append(item)
    return rows


def run(plan, bundles, expected_plan, *, memory_mib, timeout_seconds, checkpoint=None, expected_head=None):
    memory_mib = integer(memory_mib, 16, 65_536)
    timeout_seconds = integer(timeout_seconds, 1, 3600)
    _, _, history, start_head, jobs = _context(plan, bundles, expected_plan, checkpoint, expected_head)
    command = [sys.executable, "-m", "ace_forge.lean_forge_runner", str(plan), str(bundles),
               "--expect-plan-sha256", expected_plan, "--memory-mib", str(memory_mib),
               "--timeout-seconds", str(timeout_seconds), "--worker"]
    if checkpoint is not None:
        command.extend(("--checkpoint-from", str(checkpoint), "--expect-head", expected_head))
    environment = {"PYTHONPATH": str(Path(__file__).resolve().parents[1]), "PYTHONDONTWRITEBYTECODE": "1",
                   "PYTHONUTF8": "1"}
    status, exit_code = "complete", None
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL, env=environment, timeout=timeout_seconds, check=False)
        exit_code = result.returncode
        output = result.stdout
        if exit_code:
            status = {MEMORY_EXIT: "memory_limit", INPUT_EXIT: "worker_rejected"}.get(exit_code, "worker_stopped")
    except subprocess.TimeoutExpired as exc:
        status, output = "deadline", exc.stdout
    new = _receipt_prefix(output, status)
    head = new[-1].get("sha256") if new else start_head
    verified = train_runner._replay([*history, *new], jobs, expected_plan, head)
    if status == "complete" and len(history) + len(new) != len(jobs):
        raise InputError("Worker mengaku selesai dengan checkpoint kurang.")
    return {
        "schema": "ace.forge-lean-run.v1", "status": status, "plan_sha256": expected_plan,
        "requested_memory_mib": memory_mib, "timeout_seconds": timeout_seconds, "worker_exit": exit_code,
        "start_head_sha256": start_head, "head_sha256": verified, "checkpoint_count": len(history) + len(new),
        "job_count": len(jobs), "new_checkpoints": new,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("bundles", type=Path)
    parser.add_argument("--expect-plan-sha256", required=True)
    parser.add_argument("--memory-mib", type=int, required=True)
    parser.add_argument("--timeout-seconds", type=int, required=True)
    parser.add_argument("--checkpoint-from", type=Path)
    parser.add_argument("--expect-head")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.worker:
            integer(args.memory_mib, 16, 65_536)
            return _worker(args)
        result = run(args.plan, args.bundles, args.expect_plan_sha256, memory_mib=args.memory_mib,
                     timeout_seconds=args.timeout_seconds, checkpoint=args.checkpoint_from, expected_head=args.expect_head)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError, OverflowError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] != "complete")


if __name__ == "__main__":
    raise SystemExit(main())
