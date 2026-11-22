"""Temukan irisan ketersediaan peserta dari permintaan bertambat dan bentuk draf janji temu."""
from datetime import timedelta

from ._contracts import PresenceError, anchor, cli, identifier, integer, items, obj, schema, text
from ._journal import format_time, instant
from ._timeline import minute_slots

def propose(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.appointments.v1", ("request_ref", "title", "duration", "earliest", "people"))
    text(plan["request_ref"], "Bukti permintaan")
    text(plan["title"], "Judul")
    earliest = instant(plan["earliest"])
    length = timedelta(minutes=integer(plan["duration"], "Durasi", 1, 1440))
    intersection = None
    seen = set()
    for row in items(plan["people"], 25, 1):
        obj(row, ("id", "windows"))
        key = identifier(row["id"], "Peserta")
        if key in seen:
            raise PresenceError("Peserta janji temu ganda.")
        seen.add(key)
        windows = minute_slots(row["windows"])
        if intersection is None:
            intersection = windows
        else:
            merged = []
            left = right = 0
            while left < len(intersection) and right < len(windows):
                a, b = intersection[left]
                c, d = windows[right]
                start, end = max(a, c), min(b, d)
                if start < end:
                    merged.append((start, end))
                if b <= d:
                    left += 1
                else:
                    right += 1
            intersection = merged
    if earliest.second:
        earliest += timedelta(seconds=60 - earliest.second)
    for start, end in intersection:
        start = max(start, earliest)
        if start + length <= end:
            return {"status": "draft", "start": format_time(start), "end": format_time(start + length),
                    "people": sorted(seen), "title": plan["title"], "source": plan["request_ref"]}
    return {"status": "no_common_slot", "source": plan["request_ref"]}

if __name__ == "__main__":
    raise SystemExit(cli(propose, __doc__))
