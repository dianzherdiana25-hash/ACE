"""Curriculum Task Suite for ACE F13 Causal Memory Validation.

Provides a structured curriculum with explicit transfer hierarchies across two structural clusters:
- Cluster 1 (Periodic / Modular): T0 (Warmup) -> T1 (Transfer Target 1) -> T2 (Transfer Target 2)
- Cluster 2 (Balance / Symmetry): T3 (Warmup) -> T4 (Transfer Target 3) -> T5 (Transfer Target 4)
- Distractor Cluster: Unrelated tasks (lexicographical sorting, substring matching) for irrelevant-memory control.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Callable, Dict, List, Tuple

ALPHABET = ("a", "b")


@dataclass(frozen=True)
class F13Task:
    task_id: str
    cluster: str  # "periodic", "balance", "distractor"
    is_transfer_target: bool
    description: str
    oracle_fn: Callable[[str], bool]
    train_pool: List[Tuple[str, bool]]
    holdout_pool: List[Tuple[str, bool]]


def _generate_pools(
    task_id: str, oracle: Callable[[str], bool], n_holdout_per_class: int = 16
) -> Tuple[List[Tuple[str, bool]], List[Tuple[str, bool]]]:
    """Deterministically generate short train pool and balanced holdout pool."""
    # 1. Deterministic train pool from short words (lengths 0..4)
    train: List[Tuple[str, bool]] = []
    short_words = [
        "", "a", "b", "aa", "ab", "ba", "bb",
        "aaa", "aab", "aba", "abb", "baa", "bab", "bba", "bbb",
        "aaaa", "aaab", "aaba", "aabb", "abaa", "abab", "abba", "abbb",
        "baaa", "baab", "baba", "babb", "bbaa", "bbab", "bbba", "bbbb",
    ]
    for w in short_words:
        train.append((w, bool(oracle(w))))

    # 2. Balanced holdout generation using deterministic pseudo-random draws
    pos_holdout: List[Tuple[str, bool]] = []
    neg_holdout: List[Tuple[str, bool]] = []
    seen = set(short_words)

    for draw in range(5000):
        if len(pos_holdout) >= n_holdout_per_class and len(neg_holdout) >= n_holdout_per_class:
            break
        dig = hashlib.sha256(f"f13_holdout|{task_id}|{draw}".encode("utf-8")).digest()
        length = 8 + (dig[0] % 9)  # Lengths 8..16
        bits = int.from_bytes(dig[1:9], "big")
        w = "".join(ALPHABET[(bits >> j) & 1] for j in range(length))
        if w in seen:
            continue
        seen.add(w)
        lbl = bool(oracle(w))
        if lbl and len(pos_holdout) < n_holdout_per_class:
            pos_holdout.append((w, True))
        elif (not lbl) and len(neg_holdout) < n_holdout_per_class:
            neg_holdout.append((w, False))

    holdout = pos_holdout + neg_holdout
    return train, holdout


# Oracle Definitions
def _t0_flat_parity(w: str) -> bool:
    """T0 Warmup: count('a') is even."""
    return w.count("a") % 2 == 0


def _t1_strided_even_parity(w: str) -> bool:
    """T1 Transfer Target 1: w[0::2] count('a') is even."""
    return w[0::2].count("a") % 2 == 0


def _t2_strided_mod3(w: str) -> bool:
    """T2 Transfer Target 2: w[1::3] count('b') is odd."""
    return w[1::3].count("b") % 2 == 1


def _t3_dyck_warmup(w: str) -> bool:
    """T3 Warmup: Dyck-1 balanced bracket language."""
    depth = 0
    for ch in w:
        depth += 1 if ch == "a" else -1
        if depth < 0:
            return False
    return depth == 0


def _t4_dyck_depth_bounded(w: str) -> bool:
    """T4 Transfer Target 3: Dyck with maximum prefix depth 4."""
    depth = 0
    for ch in w:
        depth += 1 if ch == "a" else -1
        if depth < 0 or depth > 4:
            return False
    return depth == 0


def _t5_relational_half_split(w: str) -> bool:
    """T5 Transfer Target 4: Left half has same count of 'a' as right half."""
    h = len(w) // 2
    return w[:h].count("a") == w[h:].count("a")


def _distractor_sorted(w: str) -> bool:
    """Distractor 1: Lexicographically sorted ('a'* 'b'*)."""
    return w == "".join(sorted(w))


def _distractor_substring(w: str) -> bool:
    """Distractor 2: Contains substring 'ab' at least twice."""
    return w.count("ab") >= 2


def create_f13_curriculum() -> Dict[str, F13Task]:
    """Create complete ordered curriculum task sequence."""
    tasks: Dict[str, F13Task] = {}

    # Cluster 1: Periodic
    train0, hold0 = _generate_pools("t0_flat_parity", _t0_flat_parity)
    tasks["t0_flat_parity"] = F13Task(
        task_id="t0_flat_parity",
        cluster="periodic",
        is_transfer_target=False,
        description="Binary parity of 'a' count is even",
        oracle_fn=_t0_flat_parity,
        train_pool=train0,
        holdout_pool=hold0,
    )

    train1, hold1 = _generate_pools("t1_strided_even_parity", _t1_strided_even_parity)
    tasks["t1_strided_even_parity"] = F13Task(
        task_id="t1_strided_even_parity",
        cluster="periodic",
        is_transfer_target=True,
        description="Even index strided count w[0::2] of 'a' is even",
        oracle_fn=_t1_strided_even_parity,
        train_pool=train1,
        holdout_pool=hold1,
    )

    train2, hold2 = _generate_pools("t2_strided_mod3", _t2_strided_mod3)
    tasks["t2_strided_mod3"] = F13Task(
        task_id="t2_strided_mod3",
        cluster="periodic",
        is_transfer_target=True,
        description="Stride 3 count w[1::3] of 'b' is odd",
        oracle_fn=_t2_strided_mod3,
        train_pool=train2,
        holdout_pool=hold2,
    )

    # Cluster 2: Balance
    train3, hold3 = _generate_pools("t3_dyck_warmup", _t3_dyck_warmup)
    tasks["t3_dyck_warmup"] = F13Task(
        task_id="t3_dyck_warmup",
        cluster="balance",
        is_transfer_target=False,
        description="Dyck-1 balanced brackets ('a' open, 'b' close)",
        oracle_fn=_t3_dyck_warmup,
        train_pool=train3,
        holdout_pool=hold3,
    )

    train4, hold4 = _generate_pools("t4_dyck_depth_bounded", _t4_dyck_depth_bounded)
    tasks["t4_dyck_depth_bounded"] = F13Task(
        task_id="t4_dyck_depth_bounded",
        cluster="balance",
        is_transfer_target=True,
        description="Dyck brackets with max depth bounded at 4",
        oracle_fn=_t4_dyck_depth_bounded,
        train_pool=train4,
        holdout_pool=hold4,
    )

    train5, hold5 = _generate_pools("t5_relational_half_split", _t5_relational_half_split)
    tasks["t5_relational_half_split"] = F13Task(
        task_id="t5_relational_half_split",
        cluster="balance",
        is_transfer_target=True,
        description="Equal 'a' count in left and right halves",
        oracle_fn=_t5_relational_half_split,
        train_pool=train5,
        holdout_pool=hold5,
    )

    return tasks


def create_distractor_tasks() -> Dict[str, F13Task]:
    """Create distractor tasks for irrelevant-memory control."""
    tasks: Dict[str, F13Task] = {}
    train_d1, hold_d1 = _generate_pools("dist_sorted", _distractor_sorted)
    tasks["dist_sorted"] = F13Task(
        task_id="dist_sorted",
        cluster="distractor",
        is_transfer_target=False,
        description="Lexicographically sorted string",
        oracle_fn=_distractor_sorted,
        train_pool=train_d1,
        holdout_pool=hold_d1,
    )
    train_d2, hold_d2 = _generate_pools("dist_substring", _distractor_substring)
    tasks["dist_substring"] = F13Task(
        task_id="dist_substring",
        cluster="distractor",
        is_transfer_target=False,
        description="Substring 'ab' appears at least twice",
        oracle_fn=_distractor_substring,
        train_pool=train_d2,
        holdout_pool=hold_d2,
    )
    return tasks
