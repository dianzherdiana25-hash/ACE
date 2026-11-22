"""Gladi migrasi tanpa promosi dan ukur perubahan byte, format, dan batas kapasitas tujuan."""
import argparse
from pathlib import Path
import sys

from ._contracts import GuardianError, anchor, canonical, decode, identity, integer, items, obj, read, schema
from ._snapshots import verify
from .state_forker import fork

def rehearse(plan, expected, source, sandbox):
    anchor(plan, expected)
    schema(plan, "ace.guardian.migration.v1", ("manifest", "max_bytes", "json_checks"))
    manifest = plan["manifest"]
    allowance = integer(plan["max_bytes"], "Ruang tujuan", 1, 30_000_000)
    content = verify(source, manifest)
    total = sum(map(len, content.values()))
    results = []
    for row in items(plan["json_checks"], 500):
        obj(row, ("path", "fields"))
        fields = items(row["fields"], 100, 1)
        if any(not isinstance(name, str) or not name for name in fields):
            raise GuardianError("Field JSON migrasi tidak sah.")
        if row["path"] not in content:
            raise GuardianError("Validasi format menunjuk di luar manifest.")
        try:
            value = decode(content[row["path"]])
        except (ValueError, RecursionError):
            value = None
        missing = set(fields) - value.keys() if isinstance(value, dict) else set(fields)
        results.append({"path": row["path"], "missing_fields": sorted(missing), "passed": not missing})
    if total > allowance or not all(row["passed"] for row in results):
        return {"status": "held", "bytes": total, "budget": allowance, "format_checks": results}
    stats = fork(source, sandbox, manifest, identity(manifest))
    if verify(sandbox, manifest, reject_extras=True) != content:
        raise GuardianError("Byte tujuan berubah selama gladi.")
    return {"status": "fixture_rehearsed", "bytes": total, "budget": allowance, "format_checks": results,
            "manifest": stats["manifest_sha256"]}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "source", "sandbox"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = rehearse(decode(read(args.plan)), args.expect_sha256, args.source, args.sandbox)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(2, f"Error: {error}\n")
    sys.stdout.buffer.write(canonical(result) + b"\n")
    return 0 if result["status"] == "fixture_rehearsed" else 1

if __name__ == "__main__":
    raise SystemExit(main())
