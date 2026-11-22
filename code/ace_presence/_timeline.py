"""Validasi interval setengah terbuka dan pembulatan yang dipakai kelas perkakas waktu."""
from bisect import bisect_right
from collections import defaultdict
from datetime import timedelta
from fractions import Fraction

from ._contracts import PresenceError, identifier, integer, items, obj
from ._journal import instant


def nonoverlap(slots):
    ordered = sorted(slots)
    if any(previous[1] > following[0] for previous, following in zip(ordered, ordered[1:])):
        raise PresenceError("Interval bertabrakan.")
    return ordered


def minute_slots(raw):
    result = []
    for row in items(raw, 600):
        obj(row, ("start", "end"))
        start, end = instant(row["start"]), instant(row["end"])
        if end <= start or any((start.second, end.second)):
            raise PresenceError("Interval perlu batas menit yang maju.")
        result.append((start, end))
    return nonoverlap(result)


def minutes(start, end):
    return (end - start) // timedelta(minutes=1)


def histogram(raw, *, group, key):
    results = defaultdict(list)
    for row in items(raw, 10_000):
        obj(row, (group, key))
        results[identifier(row[group], group)].append(integer(row[key], key, 1, 1_000_000))
    return results


def quantile(values, percent):
    ordered = sorted(values)
    return ordered[(len(ordered) * percent + 99) // 100 - 1]


def posterior(risks, threshold):
    # Laplace smoothing leaves explicit uncertainty when observations are sparse.
    ordered = sorted(risks)
    late = len(ordered) - bisect_right(ordered, threshold)
    return Fraction(late + 1, len(ordered) + 2), late
