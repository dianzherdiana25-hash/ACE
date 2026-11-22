"""Satukan janji, tenggat, dan acara hari ini menjadi agenda lokal yang berurutan."""
from ._contracts import PresenceError, anchor, cli, day, identifier, identity, integer, items, obj, schema, text
from .calendar_engine import calendar

def agenda(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.daily-agenda.v1", ("calendar_plan", "commitments", "limit"))
    view = calendar(plan["calendar_plan"], identity(plan["calendar_plan"]))
    today = day(view["day"])
    rows = []
    seen = set()
    for case in items(plan["commitments"], 3000):
        obj(case, ("id", "due_on", "title", "status", "priority", "source"))
        key = identifier(case["id"], "Komitmen")
        if key in seen or case["status"] not in ("open", "fulfilled", "cancelled"):
            raise PresenceError("Komitmen ganda atau status tidak sah.")
        seen.add(key)
        due = day(case["due_on"])
        text(case["title"], "Judul")
        text(case["source"], "Bukti agenda")
        importance = integer(case["priority"], "Prioritas", 0, 100)
        if due <= today and case["status"] == "open":
            rows.append((due, -importance, key, case))
    cap = integer(plan["limit"], "Batas komitmen", 1, 100)
    return {"day": view["day"], "zone": view["zone"], "meetings": view["events"], "priority": [
        {**row, "overdue": due < today} for due, _, _, row in sorted(rows)[:cap]],
        "omitted_commitments": max(0, len(rows) - cap)}

if __name__ == "__main__":
    raise SystemExit(cli(agenda, __doc__))
