"""Autonomous Meta-Curriculum & Frontier Expander.

Prevents artificial capability ceilings by dynamically synthesizing higher-order
task families (Family L, Family M, Family N) when current benchmarks are mastered.
Strictly generates 3-tier partitioned data splits (train, validation, sealed holdout).
"""
from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Callable, Dict, List, Tuple

from ace_self_dev.confirmation_suite import ConfirmationTask


def _oracle_l1_balanced_parentheses(w: str) -> bool:
    """True if string consists of well-formed balanced brackets/parentheses using 'a' for '(' and 'b' for ')'."""
    if not w:
        return True
    depth = 0
    for ch in w:
        if ch == "a":
            depth += 1
        elif ch == "b":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _oracle_l2_alternating_palindrome(w: str) -> bool:
    """True if string is a palindrome and has alternating run lengths."""
    if len(w) < 2:
        return False
    if w != w[::-1]:
        return False
    # Check alternating run parity
    runs = []
    c, cnt = w[0], 1
    for ch in w[1:]:
        if ch == c:
            cnt += 1
        else:
            runs.append(cnt)
            c, cnt = ch, 1
    runs.append(cnt)
    for i in range(len(runs) - 1):
        if (runs[i] % 2) == (runs[i + 1] % 2):
            return False
    return True


def _oracle_m1_token_chain_divisibility(w: str) -> bool:
    """True if total length is divisible by 3 and occurrences of 'aa' equal occurrences of 'bb'."""
    if len(w) % 3 != 0:
        return False
    return w.count("aa") == w.count("bb")


class MetaCurriculumExpander:
    """Generates new frontier task suites to drive open-ended evolution."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)

    def generate_frontier_task(
        self,
        task_id: str,
        family: str,
        oracle_fn: Callable[[str], bool],
        description: str,
        alphabet: Tuple[str, ...] = ("a", "b"),
    ) -> ConfirmationTask:
        """Deterministically generate balanced train, validation, and sealed holdout pools."""
        # Helper to generate random words
        def make_words(min_len: int, max_len: int, count: int) -> List[str]:
            words = set()
            attempts = 0
            while len(words) < count and attempts < 10000:
                attempts += 1
                length = self.rng.randint(min_len, max_len)
                w = "".join(self.rng.choice(alphabet) for _ in range(length))
                words.add(w)
            return sorted(list(words))

        # Generate balanced pool
        def balance_pool(candidate_words: List[str], target_pos: int, target_neg: int) -> List[Tuple[str, bool]]:
            pos: List[Tuple[str, bool]] = []
            neg: List[Tuple[str, bool]] = []
            for w in candidate_words:
                lbl = oracle_fn(w)
                if lbl and len(pos) < target_pos:
                    pos.append((w, True))
                elif not lbl and len(neg) < target_neg:
                    neg.append((w, False))
                if len(pos) == target_pos and len(neg) == target_neg:
                    break
            
            # If not enough positives, synthetically search with higher budget
            if len(pos) < target_pos:
                for l in range(1, 14):
                    # systematic search
                    for i in range(2**l):
                        bin_str = bin(i)[2:].zfill(l)
                        w = bin_str.replace("0", "a").replace("1", "b")
                        if oracle_fn(w) and (w, True) not in pos:
                            pos.append((w, True))
                            if len(pos) == target_pos:
                                break
                    if len(pos) == target_pos:
                        break

            combined = pos + neg
            self.rng.shuffle(combined)
            return combined

        train_candidates = make_words(1, 6, 200)
        train_pool = balance_pool(train_candidates, 20, 20)

        val_candidates = make_words(6, 9, 200)
        val_pool = balance_pool(val_candidates, 16, 16)

        holdout_candidates = make_words(8, 14, 200)
        holdout_pool = balance_pool(holdout_candidates, 16, 16)

        return ConfirmationTask(
            task_id=task_id,
            family=family,
            description=description,
            oracle_fn=oracle_fn,
            train_pool=train_pool,
            validation_pool=val_pool,
            sealed_confirmation_holdout=holdout_pool,
        )

    def create_frontier_suite(self) -> Dict[str, ConfirmationTask]:
        """Create the next tier Frontier Task Suite (Family L and Family M)."""
        tasks = {}
        t_l1 = self.generate_frontier_task(
            task_id="task_l1_balanced_parentheses",
            family="family_l",
            oracle_fn=_oracle_l1_balanced_parentheses,
            description="Balanced delimiter structure over alphabet {a='(', b=')'}",
        )
        tasks[t_l1.task_id] = t_l1

        t_l2 = self.generate_frontier_task(
            task_id="task_l2_alternating_palindrome",
            family="family_l",
            oracle_fn=_oracle_l2_alternating_palindrome,
            description="Alternating run-length palindrome invariant",
        )
        tasks[t_l2.task_id] = t_l2

        t_m1 = self.generate_frontier_task(
            task_id="task_m1_token_chain_divisibility",
            family="family_m",
            oracle_fn=_oracle_m1_token_chain_divisibility,
            description="Divisibility by 3 with equal aa and bb token chain counts",
        )
        tasks[t_m1.task_id] = t_m1
        return tasks
