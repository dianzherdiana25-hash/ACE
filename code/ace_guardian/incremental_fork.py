"""Bangun fork baru dari delta terverifikasi dan gunakan kembali hanya byte lama yang cocok."""
import argparse
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from ._contracts import GuardianError, anchor, canonical, decode, identity, read, schema
from ._snapshots import fingerprint, read_fixture, validate_manifest, verify, write_new
from .state_forker import fork

def increment(plan, expected, previous, changes, target):
    anchor(plan, expected)
    schema(plan, "ace.guardian.incremental.v1", ("before", "after"))
    old = verify(previous, plan["before"], reject_extras=True)
    delta = {}
    retained = []
    for entry in validate_manifest(plan["after"]):
        path = entry["path"]
        expected_bytes = {key: entry[key] for key in ("sha256", "bytes")}
        if path in old and fingerprint(old[path]) == expected_bytes:
            retained.append(path)
        else:
            data = read_fixture(changes, path)
            if fingerprint(data) != expected_bytes:
                raise GuardianError(f"Delta berbeda: {path}")
            delta[path] = data
    target_parent = target.parent.resolve(strict=True)
    canonical_target = target_parent / target.name
    for path in (previous.resolve(strict=True), changes.resolve(strict=True)):
        if path == canonical_target or path in canonical_target.parents or canonical_target in path.parents:
            raise GuardianError("Target inkremental harus berada di luar sumber.")
    with TemporaryDirectory(prefix="ace-guardian-incremental-") as directory:
        stage = Path(directory)
        for name, raw in sorted({**{name: old[name] for name in retained}, **delta}.items()):
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            write_new(path, raw)
        stats = fork(stage, canonical_target, plan["after"], identity(plan["after"]))
    return {**stats, "reused": sorted(retained), "changed": sorted(delta), "removed": sorted(old.keys() - set(retained) - delta.keys())}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("plan", "previous", "changes", "target"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = increment(decode(read(args.plan)), args.expect_sha256, args.previous, args.changes, args.target)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(2, f"Error: {error}\n")
    sys.stdout.buffer.write(canonical(result) + b"\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
