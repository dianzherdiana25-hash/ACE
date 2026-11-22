"""Usulkan jendela tugas berat yang bebas konflik dan beri bobot dari bukti fokus."""
from datetime import timedelta
from fractions import Fraction

from ._contracts import PresenceError, anchor, cli, identifier, integer, items, obj, schema, text
from ._journal import format_time, instant
from ._timeline import minute_slots

def advise(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.best-time.v1", ("duration", "busy", "candidates", "focus_history"))
    length = timedelta(minutes=integer(plan["duration"], "Durasi tugas", 1, 720))
    busy = minute_slots(plan["busy"])
    history = {}
    for row in items(plan["focus_history"], 168):
        obj(row, ("weekday", "hour", "completed", "tried", "source"))
        key = integer(row["weekday"], "Hari", 0, 6), integer(row["hour"], "Jam UTC", 0, 23)
        attempts = integer(row["tried"], "Percobaan", 1, 10000)
        success = integer(row["completed"], "Tuntas", 0, attempts)
        if key in history:
            raise PresenceError("Data fokus jam yang sama berulang.")
        history[key] = Fraction(success, attempts), text(row["source"], "Bukti fokus")
    candidates = []
    seen = set()
    for row in items(plan["candidates"], 400):
        obj(row, ("id", "starts"))
        key = identifier(row["id"], "Jendela")
        if key in seen:
            raise PresenceError("Jendela kandidat ganda.")
        seen.add(key)
        start = instant(row["starts"])
        end = start + length
        if any(start < last and first < end for first, last in busy):
            continue
        observed = history.get((start.weekday(), start.hour))
        ratio, source = observed if observed else (Fraction(0), None)
        candidates.append((not bool(observed), -ratio, start, key, source))
    return {"candidates": [{"id": key, "start": format_time(start), "end": format_time(start + length),
                            "focus_fraction": str(-negative) if source else None, "source": source}
                           for _, negative, start, key, source in sorted(candidates)]}

if __name__ == "__main__":
    raise SystemExit(cli(advise, __doc__))
