"""Family 3 prototype — text_transform (slug pipeline) tasks.

The third problem family for the discovery/transfer science,
after grid (curriculum_lab grid tasks) and pricing
(pricing_adapter + pricing_substrate). Design:
docs/research/ACE_FAMILY3_DESIGN_20261113.md.

Shape: a staged string pipeline

    def transform(text):
        words = text.split()
        words = [w.<case_mode>() for w in words]
        slug = "<sep>".join(words)
        if len(slug) > <limit>:
            slug = slug[:<limit>-3] + "..."
        return slug

(The ellipsis body is deliberate: a bare slug[:limit] body
would make the truncation-condition boundary unobservable —
at len == limit the slice is the identity — and a defect
class that cannot change any output is not a defect class.)

rendered from seed parameters (case_mode, sep, limit baked in
as literals, exactly as pricing bakes its threshold). Buggy
variants come from a named defect catalog of text transforms
of the reference — the curriculum_lab pattern. A task is
valid only if the buggy program fails at least one shown
case (the gate build_pricing_task inherits from the lab).

This is a PROTOTYPE: it is not registered in
curriculum_lab.FAMILIES, has no authored baseline substrate,
and no discovery run has touched it. The TextAdapter below
only demonstrates the FamilyAdapter binding shape.
"""
from __future__ import annotations

import itertools
import random
from typing import Any

from .curriculum_lab import InvalidTaskError, _run_cases
from .reasoning_lab import Budget

ENTRYPOINT = "transform"
FAMILY_ID = "text_transform"

CASE_MODES = ("lower", "upper", "title")
SEPARATORS = ("-", "_")
LIMITS = (8, 12, 16, 20)

# Case-mode a defect swaps TO (a wrong case op, never identity).
_CASE_SWAP = {"lower": "upper", "upper": "lower", "title": "lower"}
_SEP_SWAP = {"-": "_", "_": "-"}

_WORDS = (
    "ace", "omega", "kode", "data", "teks", "surat", "kabar",
    "langit", "bumi", "api", "air", "batu", "kayu", "jalan",
    "rumah", "buku", "pena", "meja", "kursi", "pintu", "waktu",
    "hari", "malam", "cerita", "sistem", "mesin", "sinyal",
    "program", "fungsi", "nilai", "urut", "gabung", "potong",
    "huruf", "spasi",
)


# ---------------------------------------------------------------------------
# Reference rendering + defect catalog
# ---------------------------------------------------------------------------

def render_reference(case_mode: str, sep: str, limit: int) -> str:
    return (
        "def transform(text):\n"
        "    words = text.split()\n"
        f"    words = [w.{case_mode}() for w in words]\n"
        f"    slug = \"{sep}\".join(words)\n"
        f"    if len(slug) > {limit}:\n"
        f"        slug = slug[:{limit - 3}] + \"...\"\n"
        "    return slug\n")


def _defect_case_mode_swap(case_mode, sep, limit):
    def apply(code: str) -> str:
        return code.replace(f"w.{case_mode}()",
                            f"w.{_CASE_SWAP[case_mode]}()")
    return apply


def _defect_separator_swap(case_mode, sep, limit):
    def apply(code: str) -> str:
        return code.replace(f"\"{sep}\".join",
                            f"\"{_SEP_SWAP[sep]}\".join")
    return apply


def _defect_truncate_off_by_one(case_mode, sep, limit):
    def apply(code: str) -> str:
        return code.replace(f"slug[:{limit - 3}]",
                            f"slug[:{limit - 4}]")
    return apply


def _defect_truncate_condition_boundary(case_mode, sep, limit):
    def apply(code: str) -> str:
        return code.replace(f"if len(slug) > {limit}:",
                            f"if len(slug) >= {limit}:")
    return apply


def _defect_split_whitespace_semantics(case_mode, sep, limit):
    def apply(code: str) -> str:
        return code.replace("text.split()", "text.split(\" \")")
    return apply


def _defect_word_order_reversal(case_mode, sep, limit):
    def apply(code: str) -> str:
        return code.replace(".join(words)", ".join(reversed(words))")
    return apply


# name -> (subtlety, factory(params) -> transform of correct code)
DEFECT_CATALOG = {
    "case_mode_swap": (1, _defect_case_mode_swap),
    "separator_swap": (1, _defect_separator_swap),
    "truncate_off_by_one": (2, _defect_truncate_off_by_one),
    "truncate_condition_boundary": (2,
                                    _defect_truncate_condition_boundary),
    "split_whitespace_semantics": (2,
                                   _defect_split_whitespace_semantics),
    "word_order_reversal": (1, _defect_word_order_reversal),
}

DEFECT_NAMES = tuple(sorted(DEFECT_CATALOG))


# ---------------------------------------------------------------------------
# Case generation
# ---------------------------------------------------------------------------

def _slug_length(words: list[str]) -> int:
    return sum(len(w) for w in words) + max(0, len(words) - 1)


def _words_for_slug_length(rng: random.Random, target: int) -> list[str]:
    """Words whose slug length (single-char separators) is
    exactly `target`, or a deterministic filler construction."""
    pool = list(_WORDS)
    rng.shuffle(pool)
    chosen: list[str] = []
    total = 0
    for word in pool:
        add = len(word) + (1 if chosen else 0)
        if total + add > target:
            continue
        chosen.append(word)
        total += add
        if total == target:
            return chosen
    # Deterministic fallback: two filler words hitting the
    # target exactly (a + 1 + b == target).
    if target >= 3:
        a = target // 2
        return ["a" * a, "b" * (target - a - 1)]
    return ["a" * target]


def _case_pool(rng: random.Random, limit: int) -> list[tuple]:
    """The full candidate case pool for one task (inputs only;
    truth always comes from running the reference)."""
    texts: list[str] = []

    def add(words, dressing=None):
        text = " ".join(words)
        if dressing == "caps":
            text = " ".join(w.capitalize() for w in words)
        elif dressing == "messy":
            text = "  " + "   ".join(words) + "\t"
        texts.append(text)

    # Single word, short slug: no truncation anywhere.
    add([rng.choice(_WORDS)])
    # Ordinary multi-word slugs under the limit.
    add(rng.sample(_WORDS, 3))
    add(rng.sample(_WORDS, 2), dressing="caps")
    # Boundary cases against the baked limit.
    if limit - 1 >= 2:
        add(_words_for_slug_length(rng, limit - 1))
    add(_words_for_slug_length(rng, limit))
    add(_words_for_slug_length(rng, limit + 3))
    # Over the limit: plain truncation territory.
    add(rng.sample(_WORDS, 5))
    # Messy whitespace: split() vs split(" ") territory.
    add(rng.sample(_WORDS, 3), dressing="messy")
    add(rng.sample(_WORDS, 2), dressing="messy")
    # De-duplicate, keep order (deterministic).
    seen: set[str] = set()
    cases = []
    for text in texts:
        if text not in seen:
            seen.add(text)
            cases.append((text,))
    return cases


# ---------------------------------------------------------------------------
# Task builder (mirrors build_pricing_task's contract)
# ---------------------------------------------------------------------------

def build_text_task(*, seed: int, level: int) -> dict[str, Any]:
    """One text_transform task in the discovery core's contract.

    level 1 = one defect, level 2 = two defects. Raises
    InvalidTaskError when no defect combination in the
    catalog yields a task passing the validity gate (the
    buggy program must fail at least one shown case, and at
    least one holdout case must expose it too, so a fix is
    checkable beyond the shown set).
    """
    if level not in (1, 2):
        raise InvalidTaskError(f"text_transform level {level} unsupported")
    rng = random.Random(seed)
    case_mode = rng.choice(CASE_MODES)
    sep = rng.choice(SEPARATORS)
    limit = rng.choice(LIMITS)
    reference = render_reference(case_mode, sep, limit)
    cases = _case_pool(rng, limit)
    truth = _run_cases(reference, ENTRYPOINT, cases)

    combos = [list(c) for c in
              itertools.combinations(DEFECT_NAMES, level)]
    rng.shuffle(combos)
    for combo in combos:
        buggy = reference
        ok = True
        for name in combo:
            _subtlety, factory = DEFECT_CATALOG[name]
            new = factory(case_mode, sep, limit)(buggy)
            if new == buggy:
                ok = False
                break
            buggy = new
        if not ok:
            continue
        buggy_out = _run_cases(buggy, ENTRYPOINT, cases)
        exposing = [i for i in range(len(cases))
                    if buggy_out[i] != truth[i]]
        if len(exposing) < 2:
            continue  # need exposure in shown AND holdout
        # Select shown cases so L2 pairs are identifiable on shown while preserving
        # at least 1 exposing case (and >= 2 total cases) in holdout.
        max_shown = min(6, len(cases) - 2)
        partial_fails_shown = True
        partial_variants: list[str] = []
        if level == 2:
            for kept in combo:
                _, factory = DEFECT_CATALOG[kept]
                p_code = factory(case_mode, sep, limit)(reference)
                if p_code != reference:
                    partial_variants.append(p_code)

        # Sample exposing indices evenly across case categories (first, middle, late messy/boundary)
        exposing_rest = list(exposing)
        holdout_reserve = exposing_rest.pop()  # guarantees >=1 exposing case stays in holdout
        non_exposing = [i for i in range(len(cases)) if i not in exposing]

        # Order exposing_rest alternating tail (messy/boundary) and head (simple/short)
        ordered_exp: list[int] = []
        lo, hi = 0, len(exposing_rest) - 1
        while lo <= hi:
            ordered_exp.append(exposing_rest[lo])
            lo += 1
            if lo <= hi:
                ordered_exp.append(exposing_rest[hi])
                hi -= 1

        chosen = ordered_exp[:max_shown]
        if len(chosen) < max_shown:
            for idx in non_exposing:
                if idx not in chosen:
                    chosen.append(idx)
                if len(chosen) >= max_shown:
                    break
        shown_idx = sorted(chosen)
        if level == 2 and partial_variants:
            for p_code in partial_variants:
                p_out = _run_cases(p_code, ENTRYPOINT, [cases[i] for i in shown_idx])
                if p_out == [truth[i] for i in shown_idx]:
                    partial_fails_shown = False
                    break
            if not partial_fails_shown:
                continue
        shown_set = set(shown_idx)
        assert holdout_reserve not in shown_set
        holdout_idx = [i for i in range(len(cases))
                       if i not in shown_set]
        spec = (
            f"Aturan slug: pisah teks per kata, ubah tiap kata ke "
            f"mode {case_mode}, gabung dengan '{sep}'; bila hasil "
            f"lebih panjang dari {limit} karakter, potong menjadi "
            f"{limit - 3} karakter pertama ditambah '...'.")
        return {
            "task_id": f"text_transform-{seed}-l{level}",
            "family": FAMILY_ID,
            "level": level,
            "seed": seed,
            "buggy_code": buggy,
            "reference_code": reference,
            "shown_cases": [list(cases[i]) for i in shown_idx],
            "shown_truth": [truth[i] for i in shown_idx],
            "holdout_cases": [list(cases[i]) for i in holdout_idx],
            "holdout_truth": [truth[i] for i in holdout_idx],
            "defects": list(combo),
            "entrypoint": ENTRYPOINT,
            "spec": spec,
        }
    raise InvalidTaskError(
        f"text_transform seed {seed} level {level}: no defect "
        "combination passes the validity gate")


def text_rivals(task: dict[str, Any]) -> list[tuple[str, str]]:
    """Construct rival (wrong/partial) programs for curriculum_generator's
    identifiability control. Checks partial repairs leaving individual defects
    unfixed plus alternative boundary/mode twins from DEFECT_CATALOG."""
    import re

    ref = task.get("reference_code") or ""
    m_mode = re.search(r"w\.(lower|upper|title)\(\)", ref)
    m_sep = re.search(r'"([_-])"\.join\(words\)', ref)
    m_lim = re.search(r"len\(slug\)\s*>\s*(\d+):", ref)
    if not (m_mode and m_sep and m_lim):
        return []
    case_mode = m_mode.group(1)
    sep = m_sep.group(1)
    limit = int(m_lim.group(1))
    defects = list(task.get("defects", []))
    rivals: list[tuple[str, str]] = []
    # Partial-fix rivals: fix all defects except one.
    if len(defects) >= 2:
        for kept in defects:
            _, factory = DEFECT_CATALOG[kept]
            code = factory(case_mode, sep, limit)(ref)
            if code != ref and code != task.get("buggy_code"):
                rivals.append((f"partial_keeps_{kept}", code))
    # Alternative single-defect confusion twins.
    for name in DEFECT_NAMES:
        if name in defects:
            continue
        _, factory = DEFECT_CATALOG[name]
        code = factory(case_mode, sep, limit)(ref)
        if code != ref and code != task.get("buggy_code"):
            rivals.append((f"wrong_class_{name}", code))
    return rivals


# ---------------------------------------------------------------------------
# Adapter binding (prototype — demonstrates the FamilyAdapter shape)
# ---------------------------------------------------------------------------

def _run_one(code: str, case: tuple) -> Any:
    try:
        namespace: dict[str, Any] = {}
        exec(compile(code, "<cand>", "exec"), namespace)
        return namespace[ENTRYPOINT](*case)
    except Exception:
        return None


class TextAdapter:
    """FamilyAdapter-protocol binding for text_transform.

    PROTOTYPE ONLY: baseline_variants is empty because this
    family has no authored substrate yet — any baseline arm
    measured through it today is the generic schema
    enumeration alone, and numbers must be labeled as such.
    """

    family_id = FAMILY_ID

    def make_budget(self, task):
        return Budget(1_000_000, entrypoint=ENTRYPOINT,
                      shown_cases=[tuple(c)
                                   for c in task["shown_cases"]],
                      shown_expected=list(task["shown_truth"]))

    def passes(self, code, cases, truth) -> int:
        return sum(1 for case, want in zip(cases, truth)
                   if _run_one(code, tuple(case)) == want)

    def baseline_variants(self, code) -> list:
        return []

    def baseline_catalog_id(self) -> str:
        return "text-prototype-v0:no-authored-substrate"

    def extra_string_candidates(self, code) -> set:
        return {"-", "_", " ", ""}


TEXT_ADAPTER = TextAdapter()
