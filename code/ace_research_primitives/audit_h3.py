"""Independent H3 scorer: reconstruct bank and rescore canonical automata.

Does not import H3 experiment runner or learner; keeps a separate source oracle,
fixed-baseline evaluator, and bank sampling implementation.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
from pathlib import Path

SEED = 20261105
ALPHABET = ("a", "b")
STATES = (6, 8, 10, 12)


def insist(condition, message):
    if not condition:
        raise AssertionError(message)


def label_digest(items):
    return hashlib.sha256(json.dumps(items, separators=(",", ":")).encode()).hexdigest()


def strings_between(a, b):
    return ["".join(t) for n in range(a, b + 1) for t in itertools.product(ALPHABET, repeat=n)]


def independent_oracle(target, word):
    table, accepting = target
    state = 0
    for character in word:
        state = table[state][0] if character == "a" else table[state][1]
    return bool(accepting[state])


def independently_draw_targets():
    train = strings_between(0, 5)
    observed = set()
    accepted = []
    for n in STATES:
        found = 0
        for attempt in range(50000):
            rand = random.Random(SEED + 4000 + n * 10000 + attempt)
            moves = [[rand.randrange(n) for _ in range(2)] for _ in range(n)]
            accepting = [rand.randrange(2) for _ in range(n)]
            frontier, reachable = [0], {0}
            while frontier:
                for neighbor in moves[frontier.pop()]:
                    if neighbor not in reachable:
                        reachable.add(neighbor)
                        frontier.append(neighbor)
            if len(reachable) != n:
                continue
            labels = tuple(independent_oracle((moves, accepting), word) for word in train)
            positives = sum(labels)
            if not 0.2 <= positives / 63 <= 0.8 or labels in observed:
                continue
            observed.add(labels)
            accepted.append((n, attempt, moves, accepting))
            found += 1
            if found == 12:
                break
        insist(found == 12, f"bank exhaustion for n={n}")
    return accepted


def independently_sample_holdout(task_idx):
    rand = random.Random(SEED + 6000 + task_idx)
    words = set()
    attempts = 0
    while len(words) < 256 and attempts < 10000:
        attempts += 1
        length = rand.randrange(14, 21)
        words.add("".join(ALPHABET[rand.randrange(2)] for _ in range(length)))
    insist(len(words) == 256, "holdout exhaustion")
    return sorted(words, key=lambda word: (len(word), word))


def reconstruct_frozen_library():
    names = ["false", "true"]
    patterns = ["".join(p) for n in (1, 2, 3) for p in itertools.product(ALPHABET, repeat=n)]
    for pattern in patterns:
        for operation in ("starts", "ends"):
            names.append(f"{operation}:{pattern}")
    for pattern in patterns:
        if len(pattern) >= 2:
            for operation in ("contains", "avoids"):
                names.append(f"{operation}:{pattern}")
    for letter in ALPHABET:
        for mod in (2, 3):
            for residue in range(mod):
                names.append(f"count:{letter}%{mod}=={residue}")
    names.append("odd_length")
    names.extend(["not_" + n for n in names[:]])
    return names


def eval_frozen(name, word):
    if name.startswith("not_"):
        return not eval_frozen(name[4:], word)
    if name == "false":
        return False
    if name == "true":
        return True
    if name == "odd_length":
        return len(word) % 2 == 1
    if name.startswith("count:"):
        desc = name[len("count:"):]
        letter, expression = desc.split("%")
        divisor, residue = expression.split("==")
        return word.count(letter) % int(divisor) == int(residue)
    operator, pattern = name.split(":")
    if operator == "starts":
        return word.startswith(pattern)
    if operator == "ends":
        return word.endswith(pattern)
    if operator == "contains":
        return pattern in word
    if operator == "avoids":
        return pattern not in word
    raise ValueError(f"unexpected frozen predicate: {name}")


def predict_canonical(machine, word):
    insist(isinstance(machine, list) and 1 <= len(machine) <= 63, "machine size")
    state = 0
    for char in word:
        moves = dict(machine[state][1])
        if char not in moves:
            return False
        state = moves[char]
    return machine[state][0] is True


def validate_machine(machine):
    insist(isinstance(machine, list) and 1 <= len(machine) <= 63, "machine type/size")
    for label, edges in machine:
        insist(label is None or type(label) is bool, "machine label type")
        insist(isinstance(edges, list), "machine edge type")
        keys = set()
        for symbol, destination in edges:
            insist(symbol in ALPHABET and symbol not in keys, "edge alphabet or determinism")
            insist(type(destination) is int and 0 <= destination < len(machine), "edge destination")
            keys.add(symbol)
    reached, frontier = {0}, [0]
    while frontier:
        state = frontier.pop()
        for _, destination in machine[state][1]:
            if destination not in reached:
                frontier.append(destination)
                reached.add(destination)
    insist(len(reached) == len(machine), "unreachable canonical states")


def suffix3_prediction(train, word):
    matching = [truth for s, truth in train if s[-3:] == word[-3:]]
    if not matching:
        matching = [truth for _, truth in train]
    return sum(matching) * 2 > len(matching)


def independent_metrics(predictor, rows):
    correct = sum(bool(predictor(s)) == expected for s, expected in rows)
    return {"correct": correct, "n": len(rows), "accuracy": round(correct / len(rows), 6)}


def verify(report):
    insist(report["schema"] == "r1-h3-1", "schema")
    insist(report["scientific_status"] == "NOT_ASSESSED", "scientific status")
    insist(report["number_of_worlds"] == 48 and len(report["cases"]) == 48, "world count")
    insist(report["true_oracle_calls"] == 24528, "evaluator call budget")
    bank = independently_draw_targets()
    train_words = strings_between(0, 5)
    val_words = strings_between(6, 7)
    assert len(train_words) == 63 and len(val_words) == 192
    library = reconstruct_frozen_library()
    counts = {}
    for idx, (case, (size, attempt, table, accept)) in enumerate(zip(report["cases"], bank)):
        insist(case["index"] == idx and case["target_source_states"] == size, "world id/size")
        insist(case["target_draw_attempt"] == attempt, "bank draw selection")
        insist(case["target_transitions"] == table and case["target_acceptance"] == accept,
               "source target mismatch")
        target = (table, accept)
        train = [(s, independent_oracle(target, s)) for s in train_words]
        val = [(s, independent_oracle(target, s)) for s in val_words]
        hold_words = independently_sample_holdout(idx)
        hold = [(s, independent_oracle(target, s)) for s in hold_words]
        insist(case["train_label_sha256"] == label_digest([int(y) for _, y in train]), "train labels hash")
        insist(case["holdout_words_sha256"] == label_digest(hold_words), "holdout sample hash")
        flip = random.Random(SEED + 8000 + idx).randrange(63)
        insist(case["single_flip_index"] == flip, "corruption index")
        insist(case["single_flip_word"] == train[flip][0], "corruption word")
        for mode in ("clean", "noisy"):
            arm = case[mode]
            arm_train = train[:]
            if mode == "noisy":
                w, y = arm_train[flip]
                arm_train[flip] = (w, not y)
            machine = arm["automaton"]
            validate_machine(machine)
            insist(len(machine) == arm["states"], "reported state count")
            insist(type(arm["attempts"]) is int and 0 <= arm["attempts"] <= 10000,
                   "merge attempt budget")
            best = min(library, key=lambda name: sum(eval_frozen(name, s) != y for s, y in arm_train))
            insist(arm["fixed_predicate"] == best, "fixed model selection mismatch")
            methods = {
                "induced": lambda word, m=machine: predict_canonical(m, word),
                "prefix_memorizer": lambda word, known=dict(arm_train): known.get(word, False),
                "suffix3": lambda word, training=arm_train: suffix3_prediction(training, word),
                "fixed_library": lambda word, name=best: eval_frozen(name, word),
            }
            for method, predictor in methods.items():
                for split, rows in (("train", arm_train), ("validation", val), ("holdout", hold)):
                    observed = independent_metrics(predictor, rows)
                    insist(arm["scores"][method][split] == observed,
                           f"score drift world={idx} mode={mode} method={method} split={split}")
            errors = [[s, int(y), int(predict_canonical(machine, s))]
                      for s, y in hold if predict_canonical(machine, s) != y]
            insist(arm["first_errors"] == errors[:3], "counterexample drift")
            counts[(mode, size)] = counts.get((mode, size), 0) + arm["scores"]["induced"]["holdout"]["correct"]
    summary = report["modes"]
    for mode in ("clean", "noisy"):
        correct = sum(counts[(mode, size)] for size in STATES)
        insist(summary[mode]["induced_correct"] == correct, "aggregate correct count")
    insist(report["predeclared"]["combined_h3_go"] is False, "unexpected gate status")
    return {"independently_audited_worlds": 48, "scored_arm_splits": 48 * 2 * 4 * 3,
            "oracle_labels_verified": 24528, "heldout_induced_correct": {
                mode: summary[mode]["induced_correct"] for mode in ("clean", "noisy")},
            "clean_by_size": {str(size): counts[("clean", size)] for size in STATES},
            "noisy_by_size": {str(size): counts[("noisy", size)] for size in STATES}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    raw = args.evidence.read_bytes()
    report = json.loads(raw)
    outcome = verify(report)
    outcome["evidence_sha256"] = hashlib.sha256(raw).hexdigest()
    print(json.dumps(outcome, sort_keys=True))


if __name__ == "__main__":
    main()
