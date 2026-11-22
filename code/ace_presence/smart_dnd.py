"""Jaga gangguan pada interval tenang, dengan pengecualian interupsi yang terikat permintaannya."""
from ._contracts import PresenceError, anchor, cli, digest, identifier, identity, items, obj, schema
from ._journal import format_time, instant
from ._timeline import minute_slots

def decide(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.dnd-plan.v1", ("now", "quiet", "requests", "interrupt_grants"))
    now = instant(plan["now"])
    interrupt_grants = {digest(value) for value in items(plan["interrupt_grants"], 500)}
    quiet_until = next((last for first, last in minute_slots(plan["quiet"]) if first <= now < last), None)
    report = []
    seen = set()
    for row in items(plan["requests"], 500):
        obj(row, ("id", "urgency", "channel", "deadline"))
        key = identifier(row["id"], "Permintaan")
        channel = identifier(row["channel"], "Kanal")
        deadline = instant(row["deadline"])
        if key in seen or row["urgency"] not in ("normal", "critical"):
            raise PresenceError("Permintaan ganda atau urgensi tidak dikenal.")
        seen.add(key)
        if deadline <= now:
            state, after = "expired", None
        elif quiet_until is None:
            state, after = "allow", None
        elif row["urgency"] == "critical" and identity(row) in interrupt_grants:
            state, after = "allow_verified_interrupt", None
        elif quiet_until >= deadline:
            state, after = "operator_review", None
        else:
            state, after = "defer", format_time(quiet_until)
        report.append({"id": key, "channel": channel, "decision": state, "after": after})
    return {"quiet": quiet_until is not None, "requests": report}

if __name__ == "__main__":
    raise SystemExit(cli(decide, __doc__))
