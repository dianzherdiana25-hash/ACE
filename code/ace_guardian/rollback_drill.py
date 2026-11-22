"""Uji ulang rollback fixture terhadap koleksi kegagalan dan cocokkan delta dengan ekspektasi terpisah."""
from pathlib import Path
from tempfile import TemporaryDirectory

from ._contracts import GuardianError, anchor, cli, identifier, identity, items, obj, schema
from ._snapshots import relative
from .rollback_engine import restore

def drill(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.guardian.rollback-drill.v1", ("cases",))
    results = []
    seen = set()
    for row in items(plan["cases"], 30, 1):
        obj(row, ("id", "snapshot", "current", "rollback", "expected_changes"))
        key = identifier(row["id"], "Kasus rollback")
        approved, damaged = [root.joinpath(*relative(row[name])) for name in ("snapshot", "current")]
        if key in seen or approved.is_symlink() or damaged.is_symlink():
            raise GuardianError("Kasus rollback ganda atau root mengarah ke symlink.")
        seen.add(key)
        for node in (approved, damaged):
            if root.resolve() not in node.resolve().parents:
                raise GuardianError("Root rollback berada di luar root fixture.")
        shape = obj(row["expected_changes"], ("added", "removed", "replaced"))
        with TemporaryDirectory(prefix="ace-guardian-rollback-") as directory:
            outcome = restore(row["rollback"], identity(row["rollback"]), approved, damaged, Path(directory) / "recovered")
        checked = {column: outcome[column] == sorted(items(shape[column], 900)) for column in shape}
        results.append({"id": key, "success": all(checked.values()), "expected_checks": checked, "receipt": outcome})
    return {"cases": results, "passed": sum(row["success"] for row in results), "evaluated": len(results)}

if __name__ == "__main__":
    raise SystemExit(cli(drill, __doc__, rooted=True))
