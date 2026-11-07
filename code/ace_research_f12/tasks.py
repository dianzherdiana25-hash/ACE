"""Task suite for ACE F12 Causal Autonomous Research.

Defines 3 mathematically disjoint structural families over Sigma = {'a', 'b'}:
- Family A: Strided Modular Parity (alternating positional invariants)
- Family B: Dyck Nested Balance & Depth Bounds (context-free bracket dynamics)
- Family C: Relational Split-Frame Equivalence (prefix/suffix relational symmetry)
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Callable, Dict, List, Tuple

ALPHABET = ("a", "b")


@dataclass(frozen=True)
class F12Task:
    task_id: str
    family: str  # "A_strided", "B_dyck", "C_relational", "base"
    description: str
    oracle_fn: Callable[[str], bool]
    train_pool: List[Tuple[str, bool]]
    holdout_pool: List[Tuple[str, bool]]


def _strided_eval(w: str, stride: int, offset: int, char: str, mod: int, target: int) -> bool:
    sub = w[offset::stride]
    return sub.count(char) % mod == target


def _dyck_eval(w: str, max_depth: int = 10) -> bool:
    depth = 0
    for ch in w:
        depth += 1 if ch == "a" else -1
        if depth < 0 or depth > max_depth:
            return False
    return depth == 0


def _split_relational_eval(w: str, mod: int) -> bool:
    h = len(w) // 2
    left = w[:h]
    right = w[h:]
    return (left.count("a") % mod) == (right.count("a") % mod)


class StridedModTask:
    @staticmethod
    def create(task_id: str, stride: int, offset: int, char: str, mod: int, target: int) -> F12Task:
        oracle = lambda w: _strided_eval(w, stride, offset, char, mod, target)
        train, holdout = _generate_task_pools(task_id, oracle)
        return F12Task(
            task_id=task_id,
            family="A_strided",
            description=f"Strided count w[{offset}::{stride}] of '{char}' mod {mod} == {target}",
            oracle_fn=oracle,
            train_pool=train,
            holdout_pool=holdout,
        )


class DyckBalanceTask:
    @staticmethod
    def create(task_id: str, max_depth: int = 10) -> F12Task:
        oracle = lambda w: _dyck_eval(w, max_depth=max_depth)
        train, holdout = _generate_task_pools(task_id, oracle)
        return F12Task(
            task_id=task_id,
            family="B_dyck",
            description=f"Dyck balanced bracket language (depth in [0, {max_depth}])",
            oracle_fn=oracle,
            train_pool=train,
            holdout_pool=holdout,
        )


class RelationalSplitTask:
    @staticmethod
    def create(task_id: str, mod: int) -> F12Task:
        oracle = lambda w: _split_relational_eval(w, mod)
        train, holdout = _generate_task_pools(task_id, oracle)
        return F12Task(
            task_id=task_id,
            family="C_relational",
            description=f"Equal count of 'a' in left and right halves mod {mod}",
            oracle_fn=oracle,
            train_pool=train,
            holdout_pool=holdout,
        )


def _generate_task_pools(
    task_id: str, oracle: Callable[[str], bool]
) -> Tuple[List[Tuple[str, bool]], List[Tuple[str, bool]]]:
    """Generate disjoint training (length 1..6) and holdout (length 8..14) sample pools."""
    train: List[Tuple[str, bool]] = []
    holdout: List[Tuple[str, bool]] = []

    # 1. Deterministic train pool from short words
    short_words = ["", "a", "b", "aa", "ab", "ba", "bb", "aaa", "aab", "aba", "abb", "baa", "bab", "bba", "bbb"]
    for w in short_words:
        train.append((w, bool(oracle(w))))

    # 2. Balanced holdout generation using SHA-256 draws
    pos_holdout: List[Tuple[str, bool]] = []
    neg_holdout: List[Tuple[str, bool]] = []
    seen = set(short_words)

    for draw in range(4000):
        if len(pos_holdout) >= 16 and len(neg_holdout) >= 16:
            break
        dig = hashlib.sha256(f"f12_holdout|{task_id}|{draw}".encode("utf-8")).digest()
        length = 8 + (dig[0] % 7)  # Lengths 8..14
        bits = int.from_bytes(dig[1:9], "big")
        w = "".join(ALPHABET[(bits >> j) & 1] for j in range(length))
        if w in seen:
            continue
        seen.add(w)
        lbl = bool(oracle(w))
        if lbl and len(pos_holdout) < 16:
            pos_holdout.append((w, True))
        elif (not lbl) and len(neg_holdout) < 16:
            neg_holdout.append((w, False))

    holdout = pos_holdout + neg_holdout
    return train, holdout


def create_f12_task_suite() -> Dict[str, F12Task]:
    """Create complete suite across the 3 disjoint families (2 tasks per family)."""
    suite: Dict[str, F12Task] = {}

    # Family A: Strided Modular Parity
    suite["task_a1_even_a_mod2"] = StridedModTask.create("task_a1_even_a_mod2", stride=2, offset=0, char="a", mod=2, target=0)
    suite["task_a2_odd_b_mod2"] = StridedModTask.create("task_a2_odd_b_mod2", stride=2, offset=1, char="b", mod=2, target=1)

    # Family B: Dyck Nested Balance
    suite["task_b1_dyck_bal"] = DyckBalanceTask.create("task_b1_dyck_bal", max_depth=8)
    suite["task_b2_dyck_deep"] = DyckBalanceTask.create("task_b2_dyck_deep", max_depth=16)

    # Family C: Relational Split-Frame Equivalence
    suite["task_c1_split_eq_mod2"] = RelationalSplitTask.create("task_c1_split_eq_mod2", mod=2)
    suite["task_c2_split_eq_mod3"] = RelationalSplitTask.create("task_c2_split_eq_mod3", mod=3)

    return suite

