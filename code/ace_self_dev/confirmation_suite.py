"""Independent Confirmation Task Suite V4 for ACE Autonomous Self-Development Loop.

Provides novel task families (Family J, Family K) strictly DISJOINT from F12 (A, B, C),
F14-V1 (D, E, F), and F14-V3 (G, H, I).

Tasks:
- Family J (Multi-Scale Run-Length Invariants):
    J1 (Multiscale Run Parity: contiguous character runs alternate between even and odd lengths)
    J2 (Symmetric Run Boundary: first run length equals last run length)
- Family K (Relational Substring Parity & Center Pivot):
    K1 (Center Pivot Density: center character determines left vs right density equality)
    K2 (Modular Stride Shift: stride 2 vs stride 3 parity balance under modular shift)

Strict 3-tier partitioning:
- train_pool: 40 short strings (lengths 1..6) for diagnosis and mutation search.
- validation_pool: 32 intermediate strings (lengths 6..9, balanced 16 pos / 16 neg).
- sealed_confirmation_holdout: 32 long strings (lengths 8..15, balanced 16 pos / 16 neg) SEALED.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple


@dataclass(frozen=True)
class ConfirmationTask:
    task_id: str
    family: str  # "family_j", "family_k"
    description: str
    oracle_fn: Callable[[str], bool]
    train_pool: List[Tuple[str, bool]]
    validation_pool: List[Tuple[str, bool]]
    sealed_confirmation_holdout: List[Tuple[str, bool]]


def _oracle_j1_multiscale_run_parity(w: str) -> bool:
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


def _oracle_j2_symmetric_run_boundary(w: str) -> bool:
    """Length >= 3, first contiguous character run length equals last run length."""
    if len(w) < 3:
        return False
    # count first run
    c_start = w[0]
    len_first = 0
    for ch in w:
        if ch == c_start:
            len_first += 1
        else:
            break
    # count last run
    c_end = w[-1]
    len_last = 0
    for ch in reversed(w):
        if ch == c_end:
            len_last += 1
        else:
            break
    return (len_first == len_last) and (w.count("a") % 2 == 0)


def _oracle_k1_center_pivot_density(w: str) -> bool:
    """Odd length >= 3: if center char is 'a', left-half 'a' count == right-half 'a' count."""
    if len(w) < 3 or len(w) % 2 == 0:
        return False
    mid = len(w) // 2
    pivot = w[mid]
    left = w[:mid]
    right = w[mid + 1:]
    if pivot == "a":
        return left.count("a") == right.count("a")
    else:
        return left.count("b") == right.count("b")


def _oracle_k2_modular_stride_shift(w: str) -> bool:
    """Length >= 4: count('a') at even indices equals count('a') at odd indices modulo 3."""
    if len(w) < 4:
        return False
    even_a = sum(1 for i, ch in enumerate(w) if i % 2 == 0 and ch == "a")
    odd_a = sum(1 for i, ch in enumerate(w) if i % 2 == 1 and ch == "a")
    return (even_a % 3) == (odd_a % 3)


def _generate_confirmation_pools(
    oracle: Callable[[str], bool],
    task_id: str,
    n_per_class: int = 16,
    task_seed: int = 42,
) -> Tuple[List[Tuple[str, bool]], List[Tuple[str, bool]], List[Tuple[str, bool]]]:
    """Deterministically partition strings into train, validation, and sealed holdout."""
    # 1. Train pool: 40 short strings (lengths 1..6)
    train: List[Tuple[str, bool]] = []
    seen = set()
    for length in range(1, 7):
        for idx in range(2 ** length):
            w = bin(idx)[2:].zfill(length).replace("0", "a").replace("1", "b")
            lbl = oracle(w)
            train.append((w, lbl))
            seen.add(w)
            if len(train) >= 40:
                break
        if len(train) >= 40:
            break

    # 2. Validation pool (lengths 6..9, balanced 16 pos / 16 neg)
    val_pos: List[Tuple[str, bool]] = []
    val_neg: List[Tuple[str, bool]] = []
    for length in range(6, 10):
        for idx in range(256):
            chars = []
            val = (idx ^ (task_seed * 1103515245 + 12345)) & 0x7FFFFFFF
            for pos in range(length):
                chars.append("b" if (val >> (pos % 5)) & 1 else "a")
                val = (val * 1664525 + 1013904223) & 0x7FFFFFFF
            w = "".join(chars)
            lbl = oracle(w)
            if lbl and len(val_pos) < n_per_class and (w, lbl) not in val_pos and w not in seen:
                val_pos.append((w, lbl))
                seen.add(w)
            elif not lbl and len(val_neg) < n_per_class and (w, lbl) not in val_neg and w not in seen:
                val_neg.append((w, lbl))
                seen.add(w)
            if len(val_pos) >= n_per_class and len(val_neg) >= n_per_class:
                break
        if len(val_pos) >= n_per_class and len(val_neg) >= n_per_class:
            break

    # If positive generation is sparse, synthesize structured positives
    if len(val_pos) < n_per_class:
        for idx in range(n_per_class - len(val_pos)):
            if task_id == "task_j1_multiscale_run_parity":
                synth = "aa" + "b" * ((idx % 3) * 2 + 1) + "aa"
            elif task_id == "task_j2_symmetric_run_boundary":
                synth = "aa" + "b" * (idx + 1) + "aa"
            elif task_id == "task_k1_center_pivot_density":
                side = "a" * (idx + 1)
                synth = side + "a" + side
            else:
                synth = "ab" * (idx + 2)
            lbl = oracle(synth)
            if lbl and (synth, True) not in val_pos:
                val_pos.append((synth, True))
                seen.add(synth)

    # If negative generation is sparse
    while len(val_neg) < n_per_class:
        cand = "a" * (len(val_neg) + 4)
        if not oracle(cand) and (cand, False) not in val_neg:
            val_neg.append((cand, False))
            seen.add(cand)
        else:
            cand = "b" * (len(val_neg) + 5)
            val_neg.append((cand, False))
            seen.add(cand)

    validation_pool = val_pos[:n_per_class] + val_neg[:n_per_class]

    # 3. Sealed Confirmation Holdout (lengths 8..15, balanced 16 pos / 16 neg)
    ho_pos: List[Tuple[str, bool]] = []
    ho_neg: List[Tuple[str, bool]] = []
    for length in range(8, 16):
        for idx in range(256):
            chars = []
            val = (idx ^ (task_seed * 2654435761 + 99991)) & 0x7FFFFFFF
            for pos in range(length):
                chars.append("b" if (val >> (pos % 6)) & 1 else "a")
                val = (val * 214013 + 2531011) & 0x7FFFFFFF
            w = "".join(chars)
            lbl = oracle(w)
            if lbl and len(ho_pos) < n_per_class and (w, lbl) not in ho_pos and w not in seen:
                ho_pos.append((w, lbl))
                seen.add(w)
            elif not lbl and len(ho_neg) < n_per_class and (w, lbl) not in ho_neg and w not in seen:
                ho_neg.append((w, lbl))
                seen.add(w)
            if len(ho_pos) >= n_per_class and len(ho_neg) >= n_per_class:
                break
        if len(ho_pos) >= n_per_class and len(ho_neg) >= n_per_class:
            break

    # Structured positives for holdout if needed
    if len(ho_pos) < n_per_class:
        for idx in range(n_per_class - len(ho_pos)):
            if task_id == "task_j1_multiscale_run_parity":
                synth = "aaaa" + "b" * ((idx % 3) * 2 + 1) + "aaaa"
            elif task_id == "task_j2_symmetric_run_boundary":
                synth = "aaa" + "b" * (idx + 2) + "aaa"
            elif task_id == "task_k1_center_pivot_density":
                side = "a" * (idx + 3)
                synth = side + "a" + side
            else:
                synth = "abab" * (idx + 2)
            lbl = oracle(synth)
            if lbl and (synth, True) not in ho_pos and synth not in seen:
                ho_pos.append((synth, True))
                seen.add(synth)

    while len(ho_neg) < n_per_class:
        cand = "a" * (len(ho_neg) + 8)
        if not oracle(cand) and (cand, False) not in ho_neg and cand not in seen:
            ho_neg.append((cand, False))
            seen.add(cand)
        else:
            cand = "b" * (len(ho_neg) + 9)
            ho_neg.append((cand, False))
            seen.add(cand)

    sealed_confirmation_holdout = ho_pos[:n_per_class] + ho_neg[:n_per_class]
    return train, validation_pool, sealed_confirmation_holdout


def create_confirmation_suite(task_seed: int = 42) -> Dict[str, ConfirmationTask]:
    """Instantiate the 4-task confirmation benchmark suite for self-development gating."""
    configs = [
        ("task_j1_multiscale_run_parity", "family_j", "Multiscale Run Parity Alternation", _oracle_j1_multiscale_run_parity),
        ("task_j2_symmetric_run_boundary", "family_j", "Symmetric Run Boundary Invariant", _oracle_j2_symmetric_run_boundary),
        ("task_k1_center_pivot_density", "family_k", "Center Pivot Half-Density Equality", _oracle_k1_center_pivot_density),
        ("task_k2_modular_stride_shift", "family_k", "Modular Stride Shift Invariant", _oracle_k2_modular_stride_shift),
    ]

    tasks: Dict[str, ConfirmationTask] = {}
    for tid, fam, desc, fn in configs:
        tr, val, ho = _generate_confirmation_pools(fn, task_id=tid, n_per_class=16, task_seed=task_seed)
        tasks[tid] = ConfirmationTask(
            task_id=tid,
            family=fam,
            description=desc,
            oracle_fn=fn,
            train_pool=tr,
            validation_pool=val,
            sealed_confirmation_holdout=ho,
        )
    return tasks
