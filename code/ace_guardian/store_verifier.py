"""Laporkan checksum berbeda, file hilang, dan inventory ekstra pada snapshot luring."""
import os
from pathlib import Path, PurePosixPath

from ._contracts import GuardianError, anchor, cli, schema
from ._snapshots import fingerprint, read_fixture, validate_manifest

def inspect(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.guardian.store-verification.v1", ("manifest", "reject_extras"))
    if type(plan["reject_extras"]) is not bool:
        raise GuardianError("Pilihan inventory harus boolean.")
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise GuardianError("Root verifikasi harus direktori fixture nyata.")
    manifest = validate_manifest(plan["manifest"])
    known = {row["path"] for row in manifest}
    directories = {str(parent) for name in known for parent in PurePosixPath(name).parents if str(parent) != "."}
    checks = []
    for row in sorted(manifest, key=lambda row: row["path"]):
        try:
            actual = fingerprint(read_fixture(root, row["path"]))
            status = "verified" if all(row[key] == actual[key] for key in actual) else "different"
        except FileNotFoundError:
            actual, status = None, "missing"
        except (OSError, GuardianError):
            actual, status = None, "unreadable"
        checks.append({"path": row["path"], "status": status, "actual": actual})
    extras = []
    if plan["reject_extras"]:
        def onerror(error):
            raise error
        for base, folders, files in os.walk(root, followlinks=False, onerror=onerror):
            for name in folders + files:
                current = Path(base) / name
                rel = str(current.relative_to(root))
                if (rel not in known and rel not in directories) or current.is_symlink():
                    extras.append(rel)
                if len(extras) > 4000:
                    raise GuardianError("Inventory tambahan terlalu besar.")
    return {"ok": all(row["status"] == "verified" for row in checks) and not extras,
            "files": checks, "extra_paths": sorted(extras), "plan_sha256": expected}

if __name__ == "__main__":
    raise SystemExit(cli(inspect, __doc__, rooted=True))
