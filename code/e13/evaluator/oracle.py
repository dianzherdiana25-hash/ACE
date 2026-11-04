"""Reference semantics for the public development rule blocks.

This module uses raw JSON values and does not depend on solver code or its DSL.
"""

from itertools import pairwise
from operator import eq, ne


def _repeat(previous, current):
    return previous == current


def _rise(previous, current):
    return previous < current


def _down(previous, current):
    return previous > current


def symbols(rule, values):
    """Emit one bit per adjacent pair, starting with a fresh monitor."""
    predicate = {
        "repeat": _repeat, "repeat_run": _repeat,
        "rise": _rise, "rise_start": _rise,
        "down": _down, "down_parity": _down,
    }[rule]
    events = [predicate(left, right) for left, right in pairwise(values)]
    previous = False
    parity = 0
    result = []
    for event in events:
        if rule == "repeat_run":
            output = event and previous
        elif rule == "rise_start":
            output = event and not previous
        elif rule == "down_parity":
            parity ^= event
            output = parity
        else:
            output = event
        result.append(int(output))
        previous = event
    return tuple(result)


def _every(_previous, _current):
    return True


# Predicate, maximum monitor value, whether the counter wraps, accepting values.
GRAPH_MONITORS = {
    "repeat_once": (eq, 2, False, frozenset({1})),
    "repeat_odd": (eq, 1, True, frozenset({1})),
    "edge_even": (_every, 1, True, frozenset({0})),
    "switch_once": (ne, 2, False, frozenset({1})),
    "switch_at_least_two": (ne, 2, False, frozenset({2})),
    "edge_min_three": (_every, 3, False, frozenset({3})),
}


def graph(rule, value):
    """Minimum cost walk accepted by the monitor, or None.

    Use synchronous relaxation over (node, previous label, monitor value).
    Nonnegative costs permit a minimum walk with no repeated expanded state.
    """
    event, cap, wrap, accepts = GRAPH_MONITORS[rule]
    distances = {(value["start"], None, 0): 0}
    for _ in range(4 * value["nodes"] * (cap + 1)):
        updated = distances.copy()
        for start, end, label, cost in value["edges"]:
            for previous in (None, 0, 1, 2, 3):
                occurs = event(previous, label) if previous is not None else event is _every
                for count in range(cap + 1):
                    known = distances.get((start, previous, count))
                    if known is None:
                        continue
                    advanced = count + int(occurs)
                    advanced = advanced % (cap + 1) if wrap else min(advanced, cap)
                    state = (end, label, advanced)
                    distance = known + cost
                    if distance < updated.get(state, float("inf")):
                        updated[state] = distance
        if distances == updated:
            break
        distances = updated
    return min((cost for (node, _, count), cost in distances.items()
                if node == value["goal"] and count in accepts), default=None)
