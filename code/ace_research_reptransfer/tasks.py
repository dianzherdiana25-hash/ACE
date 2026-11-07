"""R9 task specifications (pure data) and the *primary* truth implementation.

A rule is a nested tuple so that two independent implementations can interpret it:
this module (Python string methods) and ``evaluator`` (regex / explicit stepping).
This module is imported by fit-side code; it contains no terminal data.
"""
from __future__ import annotations

ALPHABET = ("a", "b")

# Source banks (admitted only if the learned DFA is exact on all strings of length 6-12).
SOURCE_REL = (
    ("ca%4==0", ("mod", "a", 4, 0)),
    ("cb%4==0", ("mod", "b", 4, 0)),
    ("ca%3==0", ("mod", "a", 3, 0)),
    ("ends:ba", ("ends", "ba")),
    ("starts:bb", ("starts", "bb")),
    ("contains:aab", ("contains", "aab")),
    ("len%4==0", ("lenmod", 4, 0)),
)
SOURCE_IRR = (
    ("starts:ab", ("starts", "ab")),
    ("starts:ba", ("starts", "ba")),
    ("ends:aa", ("ends", "aa")),
    ("ends:bb", ("ends", "bb")),
    ("contains:bab", ("contains", "bab")),
    ("contains:aba", ("contains", "aba")),
    ("ca%2==0", ("mod", "a", 2, 0)),
    ("len%3==0", ("lenmod", 3, 0)),
)
# Tried in the pre-registration preflight and excluded because R1 does not identify them
# from exhaustive length<=5 strings; kept here only so a test can assert they still fail.
SOURCE_PREFLIGHT_EXCLUDED = (
    ("ca%5==0", ("mod", "a", 5, 0)),
    ("ends:abb", ("ends", "abb")),
)

TARGETS = (
    ("U1", "U", ("and", ("mod", "a", 4, 2), ("ends", "ba"))),
    ("U2", "U", ("and", ("mod", "b", 4, 1), ("starts", "bb"))),
    ("U3", "U", ("xor", ("mod", "a", 4, 1), ("ends", "ba"))),
    ("U4", "U", ("or", ("mod", "b", 4, 3), ("contains", "aab"))),
    ("U5", "U", ("and", ("mod", "a", 4, 3), ("mod", "b", 4, 2))),
    ("U6", "U", ("xor", ("mod", "b", 4, 2), ("starts", "bb"))),
    ("L1", "L", ("and", ("mod", "a", 3, 1), ("ends", "ba"))),
    ("L2", "L", ("or", ("mod", "a", 3, 2), ("starts", "bb"))),
    ("L3", "L", ("xor", ("mod", "a", 3, 1), ("contains", "aab"))),
    ("N1", "N", ("equal_counts",)),
    ("N2", "N", ("dyck",)),
)
TARGET_BY_ID = {task_id: (stratum, spec) for task_id, stratum, spec in TARGETS}
# Drift controls: identical train/validation labels, complemented terminal truth.
DRIFT = (("D1", "U1"), ("D2", "L1"))


def truth(spec, s: str) -> bool:
    kind = spec[0]
    if kind in ("and", "or", "xor"):
        x, y = truth(spec[1], s), truth(spec[2], s)
        return (x and y) if kind == "and" else (x or y) if kind == "or" else (x != y)
    if kind == "mod":
        return s.count(spec[1]) % spec[2] == spec[3]
    if kind == "lenmod":
        return len(s) % spec[1] == spec[2]
    if kind == "starts":
        return s.startswith(spec[1])
    if kind == "ends":
        return s.endswith(spec[1])
    if kind == "contains":
        return spec[1] in s
    if kind == "equal_counts":
        return s.count("a") == s.count("b")
    if kind == "dyck":
        level = 0
        for c in s:
            level += 1 if c == "a" else -1
            if level < 0:
                return False
        return level == 0
    raise ValueError(f"unknown rule: {spec!r}")
