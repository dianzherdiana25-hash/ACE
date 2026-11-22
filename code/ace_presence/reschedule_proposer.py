"""Bentuk pilihan pindah yang menghormati jam kerja, benturan, dan lead time."""
from datetime import timedelta

from ._contracts import PresenceError, anchor, cli, integer, obj, schema, text
from ._journal import format_time, instant
from ._timeline import minute_slots

def propose(plan, expected):
    anchor(plan, expected)
    schema(plan, "ace.presence.reschedule.v1", ("appointment", "work", "busy", "not_before", "max_results"))
    old = obj(plan["appointment"], ("start", "end", "source"))
    former, until = instant(old["start"]), instant(old["end"])
    after = instant(plan["not_before"])
    length = until - former
    text(old["source"], "Sumber jadwal lama")
    if not timedelta(minutes=1) <= length <= timedelta(days=1):
        raise PresenceError("Durasi jadwal di luar batas.")
    busy = minute_slots(plan["busy"])
    cap = integer(plan["max_results"], "Maksimal opsi", 1, 12)
    candidates = set()
    for start, finish in minute_slots(plan["work"]):
        # Closest free location per segment: include original to both sides and all busy edges.
        boundaries = {max(start, after), max(start, after, former), finish - length}
        boundaries.update(end for _, end in busy if start <= end <= finish)
        boundaries.update(begin - length for begin, _ in busy if start <= begin <= finish)
        boundaries.update((former - timedelta(minutes=1), former + timedelta(minutes=1)))
        for point in boundaries:
            end = point + length
            if (max(start, after) <= point < end <= finish and point != former
                    and not any(first < end and point < last for first, last in busy)):
                candidates.add(point)
    ranked = sorted(candidates, key=lambda start: (abs(start - former), start))
    return {"source": old["source"], "proposals": [
        {"start": format_time(start), "end": format_time(start + length),
         "shift_seconds": int((start - former).total_seconds())} for start in ranked[:cap]]}

if __name__ == "__main__":
    raise SystemExit(cli(propose, __doc__))
