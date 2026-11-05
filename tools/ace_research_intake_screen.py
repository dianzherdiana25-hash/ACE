"""Coordinator-owned public R1 transfer screen; frozen protocol in docs.

Requires the unchanged R1 primitive_discovery module from pinned PR #38.
No R1 source edits, oracle purchases, source execution, or policy promotion.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import random
import time

SEED = 76543000
HOLDOUT_SEED = 987654321
STATES = (6, 8, 10, 12)
MAX_DRAWS = 50000


def train_words():
    return ["".join(word) for n in range(6)
            for word in itertools.product("ab", repeat=n)]


def truth(target, word):
    transitions, accepting = target
    state = 0
    for symbol in word:
        state = transitions[state][0 if symbol == "a" else 1]
    return bool(accepting[state])


def reachable(target):
    transitions, _ = target
    found, todo = {0}, [0]
    while todo:
        for nxt in transitions[todo.pop()]:
            if nxt not in found:
                found.add(nxt)
                todo.append(nxt)
    return len(found)


def new_targets():
    train = train_words()
    observed = set()
    records = []
    for n in STATES:
        accepted = 0
        for j in range(MAX_DRAWS):
            rng = random.Random(SEED + n * 50000 + j)
            target = (
                tuple(tuple(rng.randrange(n) for _ in "ab") for _ in range(n)),
                tuple(bool(rng.randrange(2)) for _ in range(n)),
            )
            if reachable(target) != n:
                continue
            labels = tuple(truth(target, word) for word in train)
            fraction = sum(labels) / len(labels)
            if not 0.2 <= fraction <= 0.8 or labels in observed:
                continue
            observed.add(labels)
            records.append({"nominal_states": n, "draw_attempt": j, "target": target,
                            "train_true": sum(labels)})
            accepted += 1
            if accepted == 6:
                break
        if accepted != 6:
            raise RuntimeError(f"HALT: exhausted task generation for {n} states")
    return records


def holdout_words(index):
    rng = random.Random(HOLDOUT_SEED + index)
    selected = set()
    for _ in range(200000):
        if len(selected) == 256:
            break
        n = rng.randrange(12, 21)
        selected.add("".join("ab"[rng.randrange(2)] for _ in range(n)))
    if len(selected) != 256:
        raise RuntimeError("HALT: heldout sample exhausted")
    return sorted(selected, key=lambda word: (len(word), word))


def sample_digest(items):
    return hashlib.sha256(json.dumps(items, separators=(",", ":")).encode("utf-8")).hexdigest()


def score(predict, pairs):
    return sum(bool(predict(word)) == label for word, label in pairs)


def fit_models(source, samples):
    model, merges = source.infer(samples, max_merges=10000)
    known = dict(samples)
    name, fixed = min(source.fixed_predicates(),
                      key=lambda row: sum(bool(row[1](word)) != label for word, label in samples))
    return {"induced": model.run,
            "memorizer": lambda word: known.get(word, False),
            "suffix3": lambda word: source.suffix_majority(samples, word),
            "fixed_library": fixed}, name, merges, model.reachable()


def evaluate(source):
    train = train_words()
    if train != source.training_words() or len(train) != 63:
        raise RuntimeError("HALT: R1 training API differs from locked protocol")
    names = ("induced", "memorizer", "suffix3", "fixed_library")
    records, cpu_seconds = [], 0.
    for i, item in enumerate(new_targets()):
        target = item["target"]
        hold = holdout_words(i)
        if set(train) & set(hold) or len(set(hold)) != 256:
            raise RuntimeError("HALT: train/holdout leakage")
        labels = [truth(target, word) for word in train]
        hold_truth = [truth(target, word) for word in hold]
        terminal = list(zip(hold, hold_truth))
        arms = {}
        for arm in ("clean", "one_flip"):
            labels_arm = labels[:]
            flipped_index = None
            if arm == "one_flip":
                flipped_index = (i * 17 + 7) % 63
                labels_arm[flipped_index] = not labels_arm[flipped_index]
            examples = list(zip(train, labels_arm))
            tic = time.process_time()
            methods, predicate, merges, states = fit_models(source, examples)
            cpu_seconds += time.process_time() - tic
            if any(bool(methods["induced"](word)) != label for word, label in examples):
                raise RuntimeError("HALT: learner not consistent with acquired labels")
            correct = {name: score(methods[name], terminal) for name in names}
            oracle = max(correct[name] for name in names if name != "induced")
            arms[arm] = {"correct": correct, "hindsight_best_control_correct": oracle,
                         "predicate_selected_on_train": predicate, "merge_attempts": merges,
                         "model_states": states, "flipped_training_index": flipped_index}
        # No abstain output from R1's unchanged .run() boolean interface:
        # identical training data is compatible with inverted post-length-11 truth.
        stable = arms["clean"]["correct"]["induced"]
        witness = next(({"word": word, "stable_truth": y, "drift_truth": not y}
                        for word, y in terminal), None)
        records.append({"id": i, "nominal_states": item["nominal_states"],
                        "target_draw_attempt": item["draw_attempt"],
                        "target_transitions": target[0], "target_accepting": target[1],
                        "train_true": item["train_true"],
                        "train_labels_sha256": sample_digest([int(x) for x in labels]),
                        "holdout_words_sha256": sample_digest(hold),
                        "holdout_labels_sha256": sample_digest([int(x) for x in hold_truth]),
                        "clean": arms["clean"], "one_flip": arms["one_flip"],
                        "indistinguishable_drift": {"correct_under_inversion": 256-stable,
                             "forced_predictions": 256, "abstentions": 0,
                             "counterexample": witness}})
    def mean_correct(arm, method):
        return sum(row[arm]["correct"][method] for row in records) / (len(records)*256)
    def oracle(arm):
        return sum(row[arm]["hindsight_best_control_correct"] for row in records) / (len(records)*256)
    clean, noisy = mean_correct("clean", "induced"), mean_correct("one_flip", "induced")
    clean90 = sum(row["clean"]["correct"]["induced"] >= 231 for row in records)
    noisy90 = sum(row["one_flip"]["correct"]["induced"] >= 231 for row in records)
    clean_gain, noise_gain = clean-oracle("clean"), noisy-oracle("one_flip")
    gates = {"clean_gain_and_coverage": clean_gain >= .05 and clean90 >= 18,
             "noise_resilience_and_coverage": (clean-noisy <= .05 and noisy90 >= 16
                                                and noise_gain >= .02),
             "semantic_shift_safe_transfer": False}
    report = {"schema":"ace.coord.r1.r8.intake.public.v1",
              "pinned_r1_source_head":"cf8948144919d41a70d1da6f3fb289d1dc818e36",
              "seed":SEED,"holdout_seed":HOLDOUT_SEED,"tasks":records,
              "label_budget":{"tasks":24, "unique_training":24*63,
                              "unique_terminal":24*256,"total_unique":24*(63+256),
                              "replayed_training_and_terminal_across_two_arms":2*24*(63+256),
                              "inverted_drift_counterfactual_queries":24*256},
              "metrics":{"clean_accuracy":round(clean,6),"noisy_accuracy":round(noisy,6),
                         "clean_hindsight_control":round(oracle("clean"),6),
                         "noisy_hindsight_control":round(oracle("one_flip"),6),
                         "clean_gain":round(clean_gain,6),"noise_gain":round(noise_gain,6),
                         "clean_tasks_at_90":clean90,"noisy_tasks_at_90":noisy90,
                         "total_merge_attempts":sum(row[arm]["merge_attempts"] for row in records
                                                    for arm in ("clean","one_flip")),
                         "unprotected_drift_tasks":24},
              "predeclared_gates":gates,
              "scientific_decision":"NOT_ASSESSED_NO_AUTOMATIC_PROMOTION"}
    return report, {"learner_fit_cpu_seconds_diagnostic":round(cpu_seconds,6),
                    "nondeterministic_runtime_not_in_evidence_hash":True}


def canonical(report):
    return (json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args(argv)
    from ace_research_primitives import primitive_discovery as source
    report, timing = evaluate(source)
    data = canonical(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(json.dumps({"report_sha256": hashlib.sha256(data).hexdigest(),
                      "decision":report["scientific_decision"],
                      "metrics":report["metrics"],
                      "gates":report["predeclared_gates"],
                      "runtime":timing}, sort_keys=True))


if __name__ == "__main__":
    main()
