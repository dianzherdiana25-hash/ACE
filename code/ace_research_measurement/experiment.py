"""Deterministic public falsification experiments for ACE R8 measurement validity."""
from __future__ import annotations
import argparse
from dataclasses import replace
import json
from pathlib import Path

from .measurement import Record, measure, semantic_fingerprint

# The expanded solver is deliberately hand-coded: it is a positive *measurement*
# control, never evidence of autonomous learning or ACE capability.
FAMILIES = ("add", "multiply", "affine", "square", "nested", "parity", "mod", "negshift")
DEV_FAMILIES = FAMILIES[:4]
OOD_FAMILIES = FAMILIES[4:]


def truth(family: str, x: int, a: int, b: int) -> int:
    if family == "add":
        return x + a
    if family == "multiply":
        return x * a
    if family == "affine":
        return (x + a) * b
    if family == "square":
        return (x + a) ** 2
    if family == "nested":
        return ((x + a) * b) ** 2
    if family == "parity":
        return (x + a) % 2
    if family == "mod":
        return (x * a + b) % 7
    if family == "negshift":
        return -x + a
    raise ValueError("unknown family")


def solve_catalog(family: str, x: int, a: int, b: int) -> int:
    if family == "add":
        return x + a
    if family == "multiply":
        return x * a
    return -10_000_000  # deliberate bounded baseline abstention-as-error


def make_rows(*, unbalanced: bool = False) -> list[Record]:
    rows = []
    for split in ("development", "validation", "evaluation"):
        families = DEV_FAMILIES if split != "evaluation" else FAMILIES
        for fidx, family in enumerate(families):
            count = 8 if split != "evaluation" else (96 if unbalanced and family == "add" else 8)
            for j in range(count):
                split_shift = {"development": 0, "validation": 100, "evaluation": 200}[split]
                x = 11 * (j + 1) + split_shift + fidx
                a = fidx + 2
                b = (j % 3) + 2
                spec = {"family": family, "x": x, "a": a, "b": b}
                expected = truth(family, x, a, b)
                baseline_ok = solve_catalog(family, x, a, b) == expected
                rows.append(Record(
                    case_id=f"{split}:{family}:{j}", split=split, family=family,
                    fingerprint=semantic_fingerprint(spec), structure=family,
                    novel=family in OOD_FAMILIES, compositional=family in {"affine", "square", "nested", "mod"},
                    baseline_correct=baseline_ok, candidate_correct=expected == truth(family, x, a, b),
                    pre_correct=baseline_ok, post_correct=True,
                    baseline_ops=10, candidate_ops=12,
                    baseline_labels=0, candidate_labels=0,
                ))
    return rows


def memorizer_control(rows: list[Record]) -> list[Record]:
    seen = {r.fingerprint for r in rows if r.split == "development"}
    return [replace(r, candidate_correct=(r.baseline_correct or r.fingerprint in seen),
                    post_correct=(r.baseline_correct or r.fingerprint in seen),
                    candidate_ops=10) for r in rows]


def score_gamer_control(rows: list[Record]) -> list[Record]:
    """Reward abundant easy items while damaging six families: Goodhart witness."""
    # For purpose of synthetic audit, make seven families and let one dominate.
    keep = [r for r in rows if r.family != "multiply"]
    return [replace(r,
                    baseline_correct=(r.family != "add"),
                    candidate_correct=(r.family == "add"),
                    pre_correct=(r.family != "add"),
                    post_correct=(r.family == "add"),
                    candidate_ops=10) for r in keep]


def run() -> dict:
    balanced = make_rows()
    unbalanced = make_rows(unbalanced=True)
    return {
        "experiment": "R8 controlled public synthetic validity probes",
        "seed_rule": "integer arithmetic from family index, split offset and j; no ambient RNG",
        "comparisons": {
            "expanded_handcoded_positive_control": measure(balanced),
            "exact_instance_memorizer_negative_control": measure(memorizer_control(balanced)),
            "goodhart_easy_family_overweight_control": measure(score_gamer_control(unbalanced)),
        },
        "interpretation": "Only tests the sensitivity of the measurement method; no ACE candidate was run.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run()
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")


if __name__ == "__main__":
    main()
