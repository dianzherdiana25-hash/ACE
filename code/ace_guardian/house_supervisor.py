"""Diagnosa timestamp heartbeat dari berkas fixture dengan prioritas dependensi yang eksplisit."""
from ._contracts import GuardianError, anchor, cli, decode, integer, obj, schema
from ._snapshots import fingerprint, open_file
from .snapshot_scheduler import instant

COMPONENTS = ("bridge", "pump", "engine")

def supervise(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.guardian.heartbeats.v1", ("at", "components"))
    now = instant(plan["at"])
    definition = obj(plan["components"], COMPONENTS)
    states = {}
    for name in COMPONENTS:
        spec = obj(definition[name], ("path", "max_age"))
        cap = integer(spec["max_age"], "Usia lease detik", 1, 86_400)
        try:
            with open_file(root, spec["path"]) as stream:
                raw = stream.read(32_769)
            if len(raw) > 32768:
                raise GuardianError("Berkas heartbeat terlalu besar.")
            record = schema(decode(raw), "ace.guardian.heartbeat.v1", ("component", "at", "running", "sequence"))
            if record["component"] != name or type(record["running"]) is not bool:
                raise GuardianError("Heartbeat salah komponen/status.")
            seq = integer(record["sequence"], "Urutan", 0, 100_000_000)
            age = int((now - instant(record["at"])).total_seconds())
            status = "invalid_time" if age < 0 else "stopped" if not record["running"] else "stale" if age > cap else "healthy"
            states[name] = {"status": status, "age_seconds": age, "sequence": seq, **fingerprint(raw)}
        except FileNotFoundError:
            states[name] = {"status": "missing"}
        except (OSError, ValueError, TypeError, KeyError, RecursionError):
            states[name] = {"status": "invalid"}
    primary = next((name for name, data in states.items() if data["status"] != "healthy"), None)
    return {"as_of": plan["at"], "states": states, "status": "healthy" if primary is None else "attention",
            "first_unhealthy": primary}

if __name__ == "__main__":
    raise SystemExit(cli(supervise, __doc__, rooted=True))
