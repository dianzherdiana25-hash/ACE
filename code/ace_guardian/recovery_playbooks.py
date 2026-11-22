"""Jalankan pemulihan fixture bertipe tertutup dari manifest yang disetujui."""
from time import monotonic

from ._contracts import GuardianError, anchor, identity, items, schema
from .rollback_engine import restore
from ._snapshots import verify

ACTIONS = ("verify_sources", "restore_to_fresh_path", "verify_restored")

def execute(plan, expected, snapshot, failed, target, *, clock=monotonic):
    anchor(plan, expected)
    schema(plan, "ace.guardian.recovery-playbook.v1", ("fault", "steps", "rollback"))
    if plan["fault"] not in ("process_stopped", "checkpoint_corrupt", "migration_failed"):
        raise GuardianError("Jenis fault pemulihan belum terdaftar.")
    if tuple(items(plan["steps"], 3, 3)) != ACTIONS:
        raise GuardianError("Urutan playbook tidak sesuai langkah fixture yang didukung.")
    initial = clock()
    rollback = schema(plan["rollback"], "ace.guardian.rollback-plan.v1", ("verified_snapshot", "current_snapshot"))
    steps = []
    backup = verify(snapshot, rollback["verified_snapshot"])
    verify(failed, rollback["current_snapshot"])
    steps.append({"step": ACTIONS[0], "files": len(backup), "status": "ok"})
    result = restore(rollback, identity(rollback), snapshot, failed, target)
    steps.append({"step": ACTIONS[1], "receipt": result["receipt_sha256"], "status": "ok"})
    stable = verify(target, rollback["verified_snapshot"], reject_extras=True) == backup
    steps.append({"step": ACTIONS[2], "status": "ok" if stable else "held"})
    end = clock()
    if not 0 <= end - initial < 1_000_000:
        raise GuardianError("Clock latihan tidak konsisten.")
    return {"status": "fixture_recovered" if stable else "held", "fault": plan["fault"],
            "elapsed_milliseconds": int((end - initial) * 1000), "steps": steps,
            "rollback_receipt": result, "playbook_sha256": expected}

def main(argv=None):
    import argparse
    from pathlib import Path
    import sys
    from ._contracts import canonical, decode, read
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "snapshot", "failed", "target"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = execute(decode(read(args.plan)), args.expect_sha256, args.snapshot, args.failed, args.target)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Error: {error}\n")
    sys.stdout.buffer.write(canonical(result) + b"\n")
    return 0 if result["status"] == "fixture_recovered" else 1

if __name__ == "__main__":
    raise SystemExit(main())
