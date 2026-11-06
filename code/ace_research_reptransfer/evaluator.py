"""Terminal evaluator: independent truth implementation and terminal bank generation.

Fit-side modules (``features``, ``head``, ``sampling``, ``arms``) must never import this module;
a test enforces that. Truth here uses ``re`` and explicit stepping, not the string methods used in
``tasks.truth``; the two are cross-checked in tests and by the verifier.
"""
from __future__ import annotations

import hashlib
import re

from .tasks import ALPHABET, TARGET_BY_ID

TERMINAL_PER_CLASS = 64
TERMINAL_MIN, TERMINAL_MAX = 16, 30
DRAW_CAP = 400_000


def independent_truth(spec, s: str) -> bool:
    kind = spec[0]
    if kind in ("and", "or", "xor"):
        x, y = independent_truth(spec[1], s), independent_truth(spec[2], s)
        return (x and y) if kind == "and" else (x or y) if kind == "or" else (x ^ y)
    if kind == "mod":
        total = 0
        for c in s:
            if c == spec[1]:
                total += 1
        return total % spec[2] == spec[3]
    if kind == "lenmod":
        return sum(1 for _ in s) % spec[1] == spec[2]
    if kind == "starts":
        return re.match(re.escape(spec[1]), s) is not None
    if kind == "ends":
        return re.search(re.escape(spec[1]) + r"\Z", s) is not None
    if kind == "contains":
        return re.search("(?=" + re.escape(spec[1]) + ")", s) is not None
    if kind == "equal_counts":
        diff = 0
        for c in s:
            diff += 1 if c == "a" else -1
        return diff == 0
    if kind == "dyck":
        t = s
        while "ab" in t:  # reduction: delete matched pairs until none remain
            t = t.replace("ab", "", 1)
        return t == ""
    raise ValueError(f"unknown rule: {spec!r}")


def _draw(role: str, task_id: str, seed: int, cls: bool, i: int) -> str:
    digest = hashlib.sha256(f"term|{role}|{task_id}|{seed}|{int(cls)}|{i}".encode("utf-8")).digest()
    length = TERMINAL_MIN + digest[0] % (TERMINAL_MAX - TERMINAL_MIN + 1)
    bits = int.from_bytes(digest[1:5], "big")
    return "".join(ALPHABET[(bits >> j) & 1] for j in range(length))


def terminal_bank(task_id: str, seed: int):
    """64 positives + 64 negatives (distinct), lengths 16-30; draw cap per class is a hard failure."""
    _, spec = TARGET_BY_ID[task_id]
    bank = []
    for cls in (True, False):
        found = {}
        for i in range(DRAW_CAP):
            w = _draw("bank", task_id, seed, cls, i)
            if w not in found and independent_truth(spec, w) == cls:
                found[w] = cls
                if len(found) == TERMINAL_PER_CLASS:
                    break
        if len(found) != TERMINAL_PER_CLASS:
            raise RuntimeError(f"terminal draw cap exhausted: {task_id} seed={seed} class={cls}")
        bank.extend(found.items())
    return sorted(bank, key=lambda item: (len(item[0]), item[0]))
