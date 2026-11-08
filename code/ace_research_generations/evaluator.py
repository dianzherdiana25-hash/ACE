"""AST-isolated terminal evaluator for Fase 7 (G0->G1->G2).

NEVER imported by ``tasks.py``, ``mechanisms.py``, ``lineage.py``, or ``immutable_guard.py``.
Generates held-out length 16..28 balanced terminal test banks using an independent
truth evaluator cross-checked against ``tasks.eval_spec``.
"""
from __future__ import annotations

from functools import lru_cache
import hashlib

ALPHABET = ("a", "b")
TERMINAL_PER_CLASS = 64
TERMINAL_MIN_LEN = 16
TERMINAL_MAX_LEN = 28
MAX_DRAWS = 300_000


def _indep_eval(spec: tuple, w: str) -> bool:
    k = spec[0]
    if k == "even_a_mod":
        return w[0::2].count("a") % spec[1] == spec[2]
    if k == "odd_b_mod":
        return w[1::2].count("b") % spec[1] == spec[2]
    if k == "block2_aa_mod":
        cnt = sum(1 for idx in range(0, len(w) - 1, 2) if w[idx] == "a" and w[idx + 1] == "a")
        return cnt % spec[1] == spec[2]
    if k == "flat_mod":
        return sum(1 for ch in w if ch == spec[1]) % spec[2] == spec[3]
    if k == "ends":
        suf = spec[1]
        return len(w) >= len(suf) and w[len(w) - len(suf) :] == suf
    if k == "starts":
        pre = spec[1]
        return w[: len(pre)] == pre
    if k == "contains":
        return w.find(spec[1]) != -1
    if k == "len_mod":
        return (len(w) % spec[1]) == spec[2]
    if k == "left_a_mod":
        h = len(w) // 2
        return w[:h].count("a") % spec[1] == spec[2]
    if k == "right_b_mod":
        h = len(w) // 2
        return w[h:].count("b") % spec[1] == spec[2]
    if k == "half_a_eq_mod":
        h = len(w) // 2
        return (w[:h].count("a") % spec[1]) == (w[h:].count("a") % spec[1])
    if k == "half_even_a_eq_mod":
        h = len(w) // 2
        return (w[:h][0::2].count("a") % spec[1]) == (w[h:][0::2].count("a") % spec[1])
    if k == "half_odd_b_neq_mod":
        h = len(w) // 2
        return (w[:h][1::2].count("b") % spec[1]) != (w[h:][1::2].count("b") % spec[1])
    if k == "half_block2_aa_eq_mod":
        h = len(w) // 2
        l_cnt = sum(1 for idx in range(0, len(w[:h]) - 1, 2) if w[:h][idx : idx + 2] == "aa")
        r_cnt = sum(1 for idx in range(0, len(w[h:]) - 1, 2) if w[h:][idx : idx + 2] == "aa")
        return (l_cnt % spec[1]) == (r_cnt % spec[1])
    if k == "and":
        return _indep_eval(spec[1], w) and _indep_eval(spec[2], w)
    if k == "or":
        return _indep_eval(spec[1], w) or _indep_eval(spec[2], w)
    if k == "xor":
        return _indep_eval(spec[1], w) ^ _indep_eval(spec[2], w)
    if k == "not":
        return not _indep_eval(spec[1], w)
    if k == "exact_eq_ab":
        return w.count("a") - w.count("b") == 0
    if k == "dyck":
        depth = 0
        for ch in w:
            depth += 1 if ch == "a" else -1
            if depth < 0:
                return False
        return depth == 0
    raise ValueError(f"unknown spec: {k}")


@lru_cache(maxsize=None)
def terminal_bank(task_id: str, spec: tuple, seed: int) -> list[tuple[str, bool]]:
    pos: list[tuple[str, bool]] = []
    neg: list[tuple[str, bool]] = []
    seen: set[str] = set()
    span = TERMINAL_MAX_LEN - TERMINAL_MIN_LEN + 1

    for draw in range(MAX_DRAWS):
        if len(pos) >= TERMINAL_PER_CLASS and len(neg) >= TERMINAL_PER_CLASS:
            break
        dig = hashlib.sha256(f"gen_term|{task_id}|{seed}|{draw}".encode("utf-8")).digest()
        ln = TERMINAL_MIN_LEN + (dig[0] % span)
        bits = int.from_bytes(dig[1:9], "big")
        w = "".join(ALPHABET[(bits >> j) & 1] for j in range(ln))
        if w in seen:
            continue
        lbl = _indep_eval(spec, w)
        if lbl and len(pos) < TERMINAL_PER_CLASS:
            seen.add(w)
            pos.append((w, True))
        elif (not lbl) and len(neg) < TERMINAL_PER_CLASS:
            seen.add(w)
            neg.append((w, False))

    if len(pos) < TERMINAL_PER_CLASS or len(neg) < TERMINAL_PER_CLASS:
        raise RuntimeError(f"terminal sampling cap exceeded on {task_id} seed={seed}")
    return pos + neg
