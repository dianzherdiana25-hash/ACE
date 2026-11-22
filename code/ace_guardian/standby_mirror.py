"""Jaga generasi mirror terisolasi dengan parent manifest dan verifikasi peran saat failover."""
from ._contracts import GuardianError, anchor, cli, digest, identity, integer, obj, schema
from ._snapshots import validate_manifest
from .snapshot_scheduler import instant

def mirror(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.guardian.standby-mirror.v1", ("active", "standby", "maximum_lag"))
    active, standby = (obj(plan[key], ("sequence", "at", "manifest", "recorded_sha256", "follows")) for key in ("active", "standby"))
    for row in (active, standby):
        integer(row["sequence"], "Generasi", 0, 100_000_000)
        instant(row["at"])
        validate_manifest(row["manifest"])
        if identity(row["manifest"]) != digest(row["recorded_sha256"]):
            raise GuardianError("Hash manifest mirror tidak cocok.")
    if active["follows"] is not None:
        digest(active["follows"])
    parent = digest(standby["follows"]) if standby["follows"] is not None else None
    delta = active["sequence"] - standby["sequence"]
    cap = integer(plan["maximum_lag"], "Batas lag mirror", 0, 100)
    mismatch = active["recorded_sha256"] != standby["recorded_sha256"]
    if delta < 0 or (delta == 0 and instant(standby["at"]) < instant(active["at"])):
        status = "invalid_order"
    elif delta > cap:
        status = "lagging"
    elif parent != active["recorded_sha256"]:
        status = "parent_unverified"
    elif delta or mismatch:
        status = "needs_sync"
    else:
        status = "byte_identical_manifest"
    return {"status": status, "sequence_lag": delta, "review_failover": status == "byte_identical_manifest",
            "active_manifest": active["recorded_sha256"], "standby_manifest": standby["recorded_sha256"]}

if __name__ == "__main__":
    raise SystemExit(cli(mirror, __doc__))
