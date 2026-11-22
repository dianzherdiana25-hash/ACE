"""Pulihkan snapshot terverifikasi ke jalur fixture baru dan periksa kedua lengan lama tetap utuh."""
import argparse
from pathlib import Path
import shutil
import sys

from ._contracts import GuardianError, anchor, canonical, decode, identity, read, schema
from ._snapshots import verify
from .state_forker import fork

def restore(plan, expected, snapshot_root, current_root, destination):
    anchor(plan, expected)
    schema(plan, "ace.guardian.rollback-plan.v1", ("verified_snapshot", "current_snapshot"))
    if current_root.is_symlink():
        raise GuardianError("State yang ditinjau harus berupa direktori fixture nyata.")
    current_root = current_root.resolve(strict=True)
    output = destination.parent.resolve(strict=True) / destination.name
    if output == current_root or output in current_root.parents or current_root in output.parents:
        raise GuardianError("Pemulihan harus berakhir di luar state yang sedang ditinjau.")
    current = plan["current_snapshot"]
    approved = plan["verified_snapshot"]
    before = verify(current_root, current)
    approved_bytes = verify(snapshot_root, approved)
    stats = fork(snapshot_root, destination, approved, identity(approved))
    original_output = output.lstat()
    try:
        actual = verify(output, approved, reject_extras=True)
        unchanged = verify(current_root, current) == before and verify(snapshot_root, approved) == approved_bytes
        if not unchanged or actual != approved_bytes:
            raise GuardianError("Sumber atau byte hasil berubah selama pemulihan.")
    except (OSError, ValueError):
        try:
            found = output.lstat()
        except FileNotFoundError:
            pass
        else:
            if (found.st_dev, found.st_ino) == (original_output.st_dev, original_output.st_ino):
                shutil.rmtree(output)
        raise
    changes = {"added": sorted(actual.keys() - before), "removed": sorted(before.keys() - actual),
               "replaced": sorted(name for name in actual.keys() & before if actual[name] != before[name])}
    payload = {"status": "restored_isolated_fixture", "plan_sha256": expected,
               "sources_reverified": unchanged, "files": stats["files"], **changes}
    return {**payload, "receipt_sha256": identity(payload)}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "snapshot", "current", "destination"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = restore(decode(read(args.plan)), args.expect_sha256, args.snapshot, args.current, args.destination)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(2, f"Error: {error}\n")
    sys.stdout.buffer.write(canonical(result) + b"\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
