"""Independent Terminal Task Suite V3 for ACE F14 Mechanism Discovery Validation.

Provides completely new task families DISJOINT from F12 (A, B, C) and F14-V1 (D, E, F):
- Family G (Context-Sensitive & Sequential Constraint):
    G1 (Strict a^n b^n Balance)
    G2 (Sandwich Prefix-Suffix Equality with Odd Parity)
- Family H (Block State-Machine & Sliding Window):
    H1 (Chunk Length Parity Alternation)
    H2 (Sliding Window Density Invariant: at least two 'a's per 4-gram)
- Family I (Hierarchical Depth & Center Symmetry):
    I1 (Dyck Depth Even-Modulo Constraint)
    I2 (Mirror Palindrome with Fixed Center Constraint)

Strictly separates:
- train_pool: for error diagnosis & heuristic search
- validation_pool: for candidate selection & Pareto ranking
- terminal_holdout_pool: SEALED; accessed strictly by Host Controller evaluator
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple


@dataclass(frozen=True)
class TerminalV3Task:
    task_id: str
    family: str  # "family_g", "family_h", "family_i"
    generation_target: int  # 1 for G1 target, 2 for G2 target
    description: str
    oracle_fn: Callable[[str], bool]
    train_pool: List[Tuple[str, bool]]
    validation_pool: List[Tuple[str, bool]]
    terminal_holdout_pool: List[Tuple[str, bool]]


def _oracle_g1_an_bn(w: str) -> bool:
    """Exact a^n b^n for n >= 1 (context-sensitive, non-regular)."""
    if not w or len(w) % 2 != 0:
        return False
    n = len(w) // 2
    return w == ("a" * n + "b" * n)


def _oracle_g2_sandwich_parity(w: str) -> bool:
    """Length >= 4, first 2 characters match last 2, and odd 'a' count."""
    if len(w) < 4:
        return False
    return (w[:2] == w[-2:]) and (w.count("a") % 2 == 1)


def _oracle_h1_chunk_alternation(w: str) -> bool:
    """Contiguous character runs alternate strictly between even and odd lengths."""
    if not w:
        return True
    runs: List[int] = []
    c, cnt = w[0], 1
    for ch in w[1:]:
        if ch == c:
            cnt += 1
        else:
            runs.append(cnt)
            c = ch
            cnt = 1
    runs.append(cnt)
    for i in range(len(runs) - 1):
        if (runs[i] % 2) == (runs[i + 1] % 2):
            return False
    return True


def _oracle_h2_sliding_window_atleast2(w: str) -> bool:
    """Every sliding window of size 4 contains at least two 'a' characters."""
    if len(w) < 4:
        return w.count("a") >= 1
    for i in range(len(w) - 3):
        if w[i : i + 4].count("a") < 2:
            return False
    return True


def _oracle_i1_nested_bracket_mod(w: str) -> bool:
    """Dyck bracket balance where prefix depth >= 0, terminal depth == 0, and max depth is even > 0."""
    d = 0
    max_d = 0
    for ch in w:
        d += 1 if ch == "a" else -1
        if d < 0:
            return False
        if d > max_d:
            max_d = d
    return (d == 0) and (max_d % 2 == 0) and (max_d > 0)


def _oracle_i2_mirror_center_invariant(w: str) -> bool:
    """String is a palindrome and center character is 'b' (or 'bb' if even)."""
    if not w or w != w[::-1]:
        return False
    mid = len(w) // 2
    if len(w) % 2 == 1:
        return w[mid] == "b"
    return w[mid - 1 : mid + 1] == "bb"


def _generate_structured_positives(oracle: Callable[[str], bool], task_id: str, n_needed: int) -> List[str]:
    """Generate valid positive instances for sparse formal languages."""
    positives: List[str] = []
    if "g1_an_bn" in task_id:
        for n in range(1, 40):
            w = "a" * n + "b" * n
            if oracle(w) and w not in positives:
                positives.append(w)
            if len(positives) >= n_needed:
                break
    elif "i1_nested_bracket" in task_id:
        depth2_blocks = ["aabb", "aababb", "abaabb", "aabaabbb"]
        for b1 in depth2_blocks:
            if oracle(b1) and b1 not in positives:
                positives.append(b1)
            for b2 in depth2_blocks:
                comb = b1 + b2
                if oracle(comb) and comb not in positives:
                    positives.append(comb)
                nested = "aa" + b1 + "bb"
                if oracle(nested) and nested not in positives:
                    positives.append(nested)
                for b3 in depth2_blocks:
                    comb3 = b1 + b2 + b3
                    if oracle(comb3) and comb3 not in positives:
                        positives.append(comb3)
                    nested2 = "aa" + comb + "bb"
                    if oracle(nested2) and nested2 not in positives:
                        positives.append(nested2)
                    if len(positives) >= n_needed:
                        break
                if len(positives) >= n_needed:
                    break
            if len(positives) >= n_needed:
                break
    elif "i2_mirror_center" in task_id:
        for length in range(3, 20):
            for idx in range(64):
                half_len = (length - 1) // 2 if length % 2 == 1 else (length - 2) // 2
                chars = []
                val = idx
                for _ in range(half_len):
                    chars.append("b" if val & 1 else "a")
                    val >>= 1
                half = "".join(chars)
                center = "b" if length % 2 == 1 else "bb"
                w = half + center + half[::-1]
                if oracle(w) and w not in positives:
                    positives.append(w)
                if len(positives) >= n_needed:
                    break
            if len(positives) >= n_needed:
                break
    return positives



def _generate_three_tier_pools(
    oracle: Callable[[str], bool],
    task_id: str,
    n_per_class: int = 16,
    task_seed: int = 42,
) -> Tuple[List[Tuple[str, bool]], List[Tuple[str, bool]], List[Tuple[str, bool]]]:
    """Deterministically synthesize train, validation, and sealed terminal holdout pools."""
    short_words = [
        "", "a", "b", "aa", "ab", "ba", "bb",
        "aaa", "aab", "aba", "abb", "baa", "bab", "bba", "bbb",
        "aaaa", "aaab", "aaba", "aabb", "abaa", "abab", "abba", "abbb",
        "baaa", "baab", "baba", "babb", "bbaa", "bbab", "bbba", "bbbb",
        "aaaaa", "aaaab", "aaaba", "aabaa", "aabba", "ababa", "abbba",
        "baaaa", "babaa", "babba", "bbaaa", "bbbaa", "bbbab", "bbbbb",
    ]
    train = [(w, oracle(w)) for w in short_words]

    # Pre-generate structural positives if language is sparse
    struct_pos = _generate_structured_positives(oracle, task_id, n_needed=n_per_class * 3)

    # 1. Validation pool (lengths 6..9)
    val_pos: List[Tuple[str, bool]] = []
    val_neg: List[Tuple[str, bool]] = []
    # Seed struct positives into val
    for sp in struct_pos[:n_per_class]:
        val_pos.append((sp, True))

    for length in range(6, 10):
        for idx in range(128):
            chars = []
            val = (idx ^ (task_seed * 1103515245 + 13579)) & 0x7FFFFFFF
            for pos in range(length):
                chars.append("b" if (val >> (pos % 6)) & 1 else "a")
                val = (val * 1664525 + 1013904223) & 0x7FFFFFFF
            w = "".join(chars)
            lbl = oracle(w)
            if lbl and len(val_pos) < n_per_class and (w, lbl) not in val_pos:
                val_pos.append((w, lbl))
            elif not lbl and len(val_neg) < n_per_class and (w, lbl) not in val_neg:
                val_neg.append((w, lbl))
            if len(val_pos) >= n_per_class and len(val_neg) >= n_per_class:
                break
        if len(val_pos) >= n_per_class and len(val_neg) >= n_per_class:
            break

    validation_pool = val_pos[:n_per_class] + val_neg[:n_per_class]
    val_words = {w for w, _ in validation_pool}

    # 2. Sealed Terminal Holdout pool (lengths 8..15)
    ho_pos: List[Tuple[str, bool]] = []
    ho_neg: List[Tuple[str, bool]] = []
    for sp in struct_pos[n_per_class : n_per_class * 2]:
        if sp not in val_words:
            ho_pos.append((sp, True))

    for length in range(8, 16):
        for idx in range(256):
            chars = []
            val = (idx ^ (task_seed * 2654435761 + 99991)) & 0x7FFFFFFF
            for pos in range(length):
                chars.append("b" if (val >> (pos % 6)) & 1 else "a")
                val = (val * 214013 + 2531011) & 0x7FFFFFFF
            w = "".join(chars)
            lbl = oracle(w)
            if lbl and len(ho_pos) < n_per_class and (w, lbl) not in ho_pos and w not in val_words:
                ho_pos.append((w, lbl))
            elif not lbl and len(ho_neg) < n_per_class and (w, lbl) not in ho_neg and w not in val_words:
                ho_neg.append((w, lbl))
            if len(ho_pos) >= n_per_class and len(ho_neg) >= n_per_class:
                break
        if len(ho_pos) >= n_per_class and len(ho_neg) >= n_per_class:
            break

    terminal_holdout_pool = ho_pos[:n_per_class] + ho_neg[:n_per_class]
    return train, validation_pool, terminal_holdout_pool


def create_f14_v3_terminal_suite(task_generation_seed: int = 42) -> Dict[str, TerminalV3Task]:
    """Create the independent 6-task V3 benchmark suite parameterized by task_generation_seed."""
    configs = [
        ("task_g1_an_bn", "family_g", 1, "Context-sensitive exact an_bn language", _oracle_g1_an_bn),
        ("task_g2_sandwich_parity", "family_g", 1, "Sandwich prefix-suffix equality with odd parity", _oracle_g2_sandwich_parity),
        ("task_h1_chunk_alternation", "family_h", 1, "Contiguous run length parity alternation", _oracle_h1_chunk_alternation),
        ("task_h2_sliding_window_atleast2", "family_h", 1, "Sliding 4-gram density invariant", _oracle_h2_sliding_window_atleast2),
        ("task_i1_nested_bracket_mod", "family_i", 2, "Nested bracket depth even-modulo invariant", _oracle_i1_nested_bracket_mod),
        ("task_i2_mirror_center_invariant", "family_i", 2, "Mirror palindrome with fixed center invariant", _oracle_i2_mirror_center_invariant),
    ]

    tasks: Dict[str, TerminalV3Task] = {}
    for tid, fam, gen_tgt, desc, fn in configs:
        tr, val, ho = _generate_three_tier_pools(fn, task_id=tid, n_per_class=16, task_seed=task_generation_seed)
        tasks[tid] = TerminalV3Task(
            task_id=tid,
            family=fam,
            generation_target=gen_tgt,
            description=desc,
            oracle_fn=fn,
            train_pool=tr,
            validation_pool=val,
            terminal_holdout_pool=ho,
        )
    return tasks
