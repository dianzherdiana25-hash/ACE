"""ACE R1 H3: preregistered larger-state and one-label-corruption stress.

Deterministic public synthetic worlds, no generated Python execution, no paid oracle.
Only the predeclared train labels are supplied to the inference procedure.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter

try:
    from . import primitive_discovery as d
    from .random_dfa_bank import run_target, source_reachable
except ImportError:
    import primitive_discovery as d
    from random_dfa_bank import run_target, source_reachable

STATES = (6, 8, 10, 12)
WORLDS_PER_SIZE = 12
HOLDOUT_SIZE = 256
MAX_DRAWS = 50000


def make_targets():
    train = d.training_words()
    selected = []
    signatures = set()
    for n in STATES:
        accepted = 0
        for attempt in range(MAX_DRAWS):
            rng = random.Random(d.SEED + 4000 + n * 10000 + attempt)
            target = (
                [tuple(rng.randrange(n) for _ in d.ALPHABET) for _ in range(n)],
                [rng.randrange(2) for _ in range(n)],
            )
            if source_reachable(target) != n:
                continue
            labels = tuple(run_target(target, s) for s in train)
            proportion = sum(labels) / len(labels)
            if not 0.2 <= proportion <= 0.8 or labels in signatures:
                continue
            signatures.add(labels)
            selected.append((n, attempt, target))
            accepted += 1
            if accepted >= WORLDS_PER_SIZE:
                break
        if accepted != WORLDS_PER_SIZE:
            raise RuntimeError(f"could not generate {WORLDS_PER_SIZE} valid worlds for size {n}")
    return selected


def make_holdout(index: int):
    rng = random.Random(d.SEED + 6000 + index)
    found = set()
    attempts = 0
    while len(found) < HOLDOUT_SIZE and attempts < 10000:
        attempts += 1
        length = rng.randrange(14, 21)
        word = "".join(d.ALPHABET[rng.randrange(2)] for _ in range(length))
        found.add(word)
    if len(found) != HOLDOUT_SIZE:
        raise RuntimeError("holdout generation exhausted")
    return sorted(found, key=lambda s: (len(s), s))


def estimate(examples, val, hold, fixed_preds):
    model, trials = d.infer(examples)
    fixed_name, fixed = min(
        fixed_preds,
        key=lambda row: sum(row[1](s) != y for s, y in examples),
    )
    predictors = {
        "induced": model.run,
        "prefix_memorizer": lambda s, known=dict(examples): known.get(s, False),
        "suffix3": lambda s, known=examples: d.suffix_majority(known, s),
        "fixed_library": fixed,
    }
    score = {
        name: {
            "train": d.metric(pred, examples),
            "validation": d.metric(pred, val),
            "holdout": d.metric(pred, hold),
        }
        for name, pred in predictors.items()
    }
    errors = [
        [s, int(y), int(model.run(s))]
        for s, y in hold
        if model.run(s) != y
    ]
    return {
        "states": model.reachable(),
        "attempts": trials,
        "fixed_predicate": fixed_name,
        "scores": score,
        "first_errors": errors[:3],
    }


def run_h3():
    bank = make_targets()
    predicates = d.fixed_predicates()
    train_words = d.training_words()
    val_words = d.validation_words()
    assert len(train_words) == 63 and len(val_words) == 192 and len(bank) == 48
    cases = []
    for index, (n, attempt, target) in enumerate(bank):
        oracle = lambda s, target=target: run_target(target, s)
        held = make_holdout(index)
        assert len(held) == 256
        assert not (set(held) & set(train_words + val_words))
        original = [(s, oracle(s)) for s in train_words]
        validation = [(s, oracle(s)) for s in val_words]
        holdout = [(s, oracle(s)) for s in held]
        noisy_index = random.Random(d.SEED + 8000 + index).randrange(63)
        perturbed = original[:]
        w, label = perturbed[noisy_index]
        perturbed[noisy_index] = (w, not label)
        clean = estimate(original, validation, holdout, predicates)
        noisy = estimate(perturbed, validation, holdout, predicates)
        cases.append({
            "index": index,
            "target_source_states": n,
            "target_draw_attempt": attempt,
            "target_transitions": target[0],
            "target_acceptance": target[1],
            "train_label_sha256": d.sample_hash([int(y) for _, y in original]),
            "holdout_words_sha256": d.sample_hash(held),
            "single_flip_index": noisy_index,
            "single_flip_word": w,
            "clean": clean,
            "noisy": noisy,
        })

    modes = {}
    for mode in ("clean", "noisy"):
        induced_correct = sum(c[mode]["scores"]["induced"]["holdout"]["correct"] for c in cases)
        oracle_correct = sum(
            max(c[mode]["scores"][k]["holdout"]["correct"] for k in
                ("prefix_memorizer", "suffix3", "fixed_library"))
            for c in cases
        )
        high_accuracy = sum(c[mode]["scores"]["induced"]["holdout"]["correct"] >= 231 for c in cases)
        modes[mode] = {
            "induced_accuracy": round(induced_correct / (48 * 256), 6),
            "induced_correct": induced_correct,
            "oracle_control_accuracy": round(oracle_correct / (48 * 256), 6),
            "oracle_control_correct": oracle_correct,
            "gain_vs_oracle": round((induced_correct-oracle_correct) / (48 * 256), 6),
            "high_accuracy_tasks": high_accuracy,
            "merge_attempts": sum(c[mode]["attempts"] for c in cases),
        }
    # Since holdout sizes are identical, unweighted mean equals pooled accuracy.
    degradation = (modes["clean"]["induced_correct"] - modes["noisy"]["induced_correct"]) / (48 * 256)
    h3a = modes["clean"]["gain_vs_oracle"] >= .05 and modes["clean"]["high_accuracy_tasks"] >= 36
    h3b = degradation <= .05 and modes["noisy"]["high_accuracy_tasks"] >= 36

    by_source_size = {}
    for n in STATES:
        rows = [r for r in cases if r["target_source_states"] == n]
        by_source_size[str(n)] = {
            arm: {
                "induced_correct": sum(r[arm]["scores"]["induced"]["holdout"]["correct"] for r in rows),
                "total": len(rows) * 256,
                "high_accuracy_tasks": sum(
                    r[arm]["scores"]["induced"]["holdout"]["correct"] >= 231 for r in rows
                ),
                "mean_inferred_states": round(sum(r[arm]["states"] for r in rows) / len(rows), 3),
            }
            for arm in ("clean", "noisy")
        }
    return {
        "schema": "r1-h3-1",
        "seed": d.SEED,
        "source_state_sizes": STATES,
        "number_of_worlds": len(cases),
        "true_oracle_calls": 48 * (63 + 192 + 256),
        "training_labels_per_world": 63,
        "synthetic_single_flip_per_world": 1,
        "sample_holdout_size": HOLDOUT_SIZE,
        "by_source_size": by_source_size,
        "modes": modes,
        "predeclared": {
            "noise_degradation": round(degradation, 6),
            "h3a_clean_scaling_pass": h3a,
            "h3b_noise_robustness_pass": h3b,
            "combined_h3_go": bool(h3a and h3b),
        },
        "cases": cases,
        "scientific_status": "NOT_ASSESSED",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output")
    args = ap.parse_args()
    result = run_h3()
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "modes": result["modes"],
        "gates": result["predeclared"],
        "by_source_size": result["by_source_size"],
        "failed_clean": [
            c["index"] for c in result["cases"]
            if c["clean"]["scores"]["induced"]["holdout"]["correct"] < 231
        ],
        "failed_noisy": [
            c["index"] for c in result["cases"]
            if c["noisy"]["scores"]["induced"]["holdout"]["correct"] < 231
        ],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
