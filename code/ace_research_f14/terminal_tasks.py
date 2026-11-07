"""Independent Terminal Task Suite for ACE F14 Mechanism Discovery Validation.

Provides completely new task families DISJOINT from F12 training tasks:
- Family D (Alternating & Run-Length Structure): D1 (Even Runs of 'a'), D2 (Bounded Alternation)
- Family E (Hierarchical Prefix-Depth & Symmetry): E1 (Prefix Depth Mod 3), E2 (Mirror Parity)
- Family F (Modular Cross-Stride Invariants): F1 (Cross-Stride 2x3 Parity), F2 (Triplet Parity)

These tasks evaluate whether grammar search over G_mech can autonomously discover
or approximate novel structural invariants without human-curated feature lists.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Callable, Dict, List, Tuple


@dataclass(frozen=True)
class TerminalF14Task:
    task_id: str
    family: str  # "family_d", "family_e", "family_f"
    generation_target: int  # 1 for G1 target, 2 for G2 target
    description: str
    oracle_fn: Callable[[str], bool]
    train_pool: List[Tuple[str, bool]]
    holdout_pool: List[Tuple[str, bool]]


def _oracle_d1_even_runs(w: str) -> bool:
    """All contiguous runs of 'a' must have even length."""
    cur_a = 0
    for ch in w:
        if ch == "a":
            cur_a += 1
        else:
            if cur_a > 0 and cur_a % 2 != 0:
                return False
            cur_a = 0
    return (cur_a % 2 == 0)


def _oracle_d2_bounded_alt(w: str) -> bool:
    """No contiguous runs of identical characters exceeding length 2 (no 'aaa' or 'bbb')."""
    return ("aaa" not in w) and ("bbb" not in w)


def _oracle_e1_prefix_depth_mod3(w: str) -> bool:
    """(a_count - b_count) mod 3 == 0 and all prefix counts have a_count >= b_count."""
    depth = 0
    for ch in w:
        depth += 1 if ch == "a" else -1
        if depth < 0:
            return False
    return (w.count("a") - w.count("b")) % 3 == 0


def _oracle_e2_mirror_parity(w: str) -> bool:
    """Symmetric mirror parity: w[i] == w[len(w)-1-i] for all i (palindrome)."""
    return w == w[::-1]


def _oracle_f1_stride3_cross(w: str) -> bool:
    """Parity of characters at stride 3 (0, 3, 6...) matches parity of characters at stride 2."""
    s3 = sum(1 for i, c in enumerate(w) if i % 3 == 0 and c == "a") % 2
    s2 = sum(1 for i, c in enumerate(w) if i % 2 == 0 and c == "a") % 2
    return s3 == s2


def _oracle_f2_triplet_parity(w: str) -> bool:
    """Every non-overlapping triplet of characters has an even number of 'a's."""
    for i in range(0, len(w) - 2, 3):
        chunk = w[i : i + 3]
        if chunk.count("a") % 2 != 0:
            return False
    return True


def _generate_pools(
    oracle: Callable[[str], bool], n_holdout_per_class: int = 16
) -> Tuple[List[Tuple[str, bool]], List[Tuple[str, bool]]]:
    """Deterministically generate train and holdout pools."""
    short_words = [
        "", "a", "b", "aa", "ab", "ba", "bb",
        "aaa", "aab", "aba", "abb", "baa", "bab", "bba", "bbb",
        "aaaa", "aaab", "aaba", "aabb", "abaa", "abab", "abba", "abbb",
        "baaa", "baab", "baba", "babb", "bbaa", "bbab", "bbba", "bbbb",
        "aaaaa", "aaaab", "aaaba", "aabaa", "aabba", "ababa", "abbba",
        "baaaa", "babaa", "babba", "bbaaa", "bbbaa", "bbbab", "bbbbb",
    ]
    train: List[Tuple[str, bool]] = [(w, oracle(w)) for w in short_words]

    holdout_pos: List[Tuple[str, bool]] = []
    holdout_neg: List[Tuple[str, bool]] = []

    # Longer words for terminal holdout evaluation (length 6..10)
    for length in range(6, 11):
        for idx in range(64):
            # Deterministic word synthesis from bits
            chars = []
            val = idx
            for pos in range(length):
                chars.append("b" if (val >> (pos % 6)) & 1 else "a")
                val = (val * 1103515245 + 12345) & 0x7FFFFFFF
            w = "".join(chars)
            lbl = oracle(w)
            if lbl and len(holdout_pos) < n_holdout_per_class:
                if (w, lbl) not in holdout_pos:
                    holdout_pos.append((w, lbl))
            elif not lbl and len(holdout_neg) < n_holdout_per_class:
                if (w, lbl) not in holdout_neg:
                    holdout_neg.append((w, lbl))
            if len(holdout_pos) >= n_holdout_per_class and len(holdout_neg) >= n_holdout_per_class:
                break
        if len(holdout_pos) >= n_holdout_per_class and len(holdout_neg) >= n_holdout_per_class:
            break

    holdout = holdout_pos + holdout_neg
    return train, holdout


def create_f14_terminal_suite() -> Dict[str, TerminalF14Task]:
    """Create the independent 6-task terminal benchmark suite."""
    train_d1, hold_d1 = _generate_pools(_oracle_d1_even_runs)
    train_d2, hold_d2 = _generate_pools(_oracle_d2_bounded_alt)
    train_e1, hold_e1 = _generate_pools(_oracle_e1_prefix_depth_mod3)
    train_e2, hold_e2 = _generate_pools(_oracle_e2_mirror_parity)
    train_f1, hold_f1 = _generate_pools(_oracle_f1_stride3_cross)
    train_f2, hold_f2 = _generate_pools(_oracle_f2_triplet_parity)

    tasks = [
        TerminalF14Task(
            task_id="task_d1_even_runs",
            family="family_d",
            generation_target=1,
            description="Even length contiguous runs of symbol 'a'",
            oracle_fn=_oracle_d1_even_runs,
            train_pool=train_d1,
            holdout_pool=hold_d1,
        ),
        TerminalF14Task(
            task_id="task_d2_bounded_alt",
            family="family_d",
            generation_target=1,
            description="Bounded alternation without runs of length > 2",
            oracle_fn=_oracle_d2_bounded_alt,
            train_pool=train_d2,
            holdout_pool=hold_d2,
        ),
        TerminalF14Task(
            task_id="task_e1_prefix_depth_mod3",
            family="family_e",
            generation_target=1,
            description="Prefix depth non-negative with total depth mod 3 == 0",
            oracle_fn=_oracle_e1_prefix_depth_mod3,
            train_pool=train_e1,
            holdout_pool=hold_e1,
        ),
        TerminalF14Task(
            task_id="task_e2_mirror_parity",
            family="family_e",
            generation_target=1,
            description="Mirror symmetric palindrome parity invariant",
            oracle_fn=_oracle_e2_mirror_parity,
            train_pool=train_e2,
            holdout_pool=hold_e2,
        ),
        TerminalF14Task(
            task_id="task_f1_stride3_cross",
            family="family_f",
            generation_target=2,
            description="Modular cross-stride (stride 2 vs stride 3) parity equality",
            oracle_fn=_oracle_f1_stride3_cross,
            train_pool=train_f1,
            holdout_pool=hold_f1,
        ),
        TerminalF14Task(
            task_id="task_f2_triplet_parity",
            family="family_f",
            generation_target=2,
            description="Even parity across consecutive non-overlapping triplets",
            oracle_fn=_oracle_f2_triplet_parity,
            train_pool=train_f2,
            holdout_pool=hold_f2,
        ),
    ]

    return {t.task_id: t for t in tasks}
