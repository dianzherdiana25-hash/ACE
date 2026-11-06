"""R1 public-development experiment: induce finite-state abstraction from labels.

No arbitrary candidate code execution, source edits, external oracle, or promotions.
RPNI-style deterministic state merging is standard prior art, not a new algorithm.
"""
from __future__ import annotations
import argparse
from collections import deque
import hashlib
import itertools
import json
import random
from dataclasses import dataclass
from typing import Callable

ALPHABET = ("a", "b")
MAX_MERGES = 10000
SEED = 20261105


def words(length: int):
    return ("".join(x) for x in itertools.product(ALPHABET, repeat=length))


def training_words():
    return [s for n in range(6) for s in words(n)]


def validation_words():
    return [s for n in (6, 7) for s in words(n)]


def dyck(s):
    level = 0
    for c in s:
        level += 1 if c == "a" else -1
        if level < 0:
            return False
    return level == 0


def regular_tasks():
    # Keep ordering fixed: index participates in holdout seed.
    return [
        ("a_parity", lambda s: s.count("a") % 2 == 0),
        ("a_mod3", lambda s: s.count("a") % 3 == 0),
        ("contains_ab", lambda s: "ab" in s),
        ("avoids_bb", lambda s: "bb" not in s),
        ("ends_ba", lambda s: s.endswith("ba")),
        ("odd_length", lambda s: len(s) % 2 == 1),
        ("avoids_aba", lambda s: "aba" not in s),
        ("a_mod4", lambda s: s.count("a") % 4 == 0),
        ("first_equals_last", lambda s: bool(s) and s[0] == s[-1]),
    ]


def stress_tasks():
    return [
        ("equal_counts", lambda s: s.count("a") == s.count("b")),
        ("dyck_balanced", dyck),
    ]


def heldout_regular(index: int):
    rng = random.Random(SEED + index)
    pool = [s for n in range(8, 14) for s in words(n)]
    return sorted(rng.sample(pool, 256), key=lambda s: (len(s), s))


def heldout_stress(index: int, judge: Callable[[str], bool]):
    # Balanced positive/negative pool; no train/validation words.
    rng = random.Random(SEED + 100 + index)
    pool = [s for n in (10, 12, 14) for s in words(n)]
    positives = [s for s in pool if judge(s)]
    negatives = [s for s in pool if not judge(s)]
    assert len(positives) >= 128 and len(negatives) >= 128
    return sorted(rng.sample(positives, 128) + rng.sample(negatives, 128), key=lambda s: (len(s), s))


@dataclass
class Automaton:
    # Parallel arrays, immutable-by-convention (explicit deepcopy on each trial).
    labels: list[bool | None]
    edges: list[dict[str, int]]
    parent: list[int]

    def find(self, state: int) -> int:
        while self.parent[state] != state:
            state = self.parent[state]
        return state

    def run(self, s: str) -> bool:
        state = self.find(0)
        for c in s:
            dest = self.edges[state].get(c)
            if dest is None:
                return False
            state = self.find(dest)
        return self.labels[state] is True

    def reachable(self):
        start = self.find(0)
        seen = {start}
        queue = deque([start])
        while queue:
            u = queue.popleft()
            for v in self.edges[u].values():
                v = self.find(v)
                if v not in seen:
                    seen.add(v)
                    queue.append(v)
        return len(seen)

    def signature(self):
        # Canonical BFS fingerprint based solely on reachable behavior.
        start = self.find(0)
        ids = {start: 0}
        queue = deque([start])
        records = []
        while queue:
            u = queue.popleft()
            row = [self.labels[u], []]
            for c in ALPHABET:
                v = self.edges[u].get(c)
                if v is not None:
                    v = self.find(v)
                    if v not in ids:
                        ids[v] = len(ids)
                        queue.append(v)
                    row[1].append([c, ids[v]])
            records.append(row)
        return records


def prefix_tree(examples):
    labels = [None]
    edges = [{}]
    for s, expected in sorted(examples, key=lambda x: (len(x[0]), x[0])):
        if type(s) is not str or set(s) - set(ALPHABET) or type(expected) is not bool:
            raise ValueError("invalid example")
        state = 0
        for c in s:
            if c not in edges[state]:
                edges[state][c] = len(labels)
                labels.append(None)
                edges.append({})
            state = edges[state][c]
        if labels[state] is not None and labels[state] != expected:
            raise ValueError("contradictory example")
        labels[state] = expected
    return Automaton(labels, edges, list(range(len(labels))))


def try_merge(original: Automaton, left: int, right: int, examples):
    # Confluent union/folding of deterministic graph; reject conflicting labels.
    m = Automaton(original.labels[:], [e.copy() for e in original.edges], original.parent[:])
    queue = [(left, right)]
    while queue:
        a, b = map(m.find, queue.pop())
        if a == b:
            continue
        a, b = sorted((a, b))
        la, lb = m.labels[a], m.labels[b]
        if la is not None and lb is not None and la != lb:
            return None
        m.parent[b] = a
        if la is None:
            m.labels[a] = lb
        for c, dst in m.edges[b].items():
            if c in m.edges[a]:
                queue.append((m.edges[a][c], dst))
            else:
                m.edges[a][c] = dst
    if any(m.run(s) != label for s, label in examples):
        return None
    return m


def infer(examples, max_merges=MAX_MERGES):
    m = prefix_tree(examples)
    if len(m.labels) > 63:
        raise ValueError("node budget exceeded")
    trials = 0
    red = [0]
    # BFS ordered original prefix states; every state begins as data-derived.
    for q in range(1, len(m.labels)):
        if m.find(q) != q:
            continue
        success = False
        for p in red:
            if trials >= max_merges:
                raise RuntimeError("state merge attempt budget exceeded")
            p = m.find(p)
            if p == q:
                success = True
                break
            trials += 1
            candidate = try_merge(m, p, q, examples)
            if candidate is not None:
                m = candidate
                success = True
                break
        if not success:
            red.append(q)
    if any(m.run(s) != label for s, label in examples):
        raise AssertionError("training consistency violated")
    return m, trials


def fixed_predicates():
    result = [("false", lambda s: False), ("true", lambda s: True)]
    patterns = ["".join(p) for n in (1, 2, 3) for p in itertools.product(ALPHABET, repeat=n)]
    for p in patterns:
        for kind, pred in (("starts", lambda s, p=p: s.startswith(p)),
                           ("ends", lambda s, p=p: s.endswith(p))):
            result.append((f"{kind}:{p}", pred))
    for p in patterns:
        if len(p) >= 2:
            result.extend(((f"contains:{p}", lambda s, p=p: p in s),
                           (f"avoids:{p}", lambda s, p=p: p not in s)))
    for letter in ALPHABET:
        for mod in (2, 3):
            for residue in range(mod):
                result.append((f"count:{letter}%{mod}=={residue}",
                               lambda s, letter=letter, mod=mod, residue=residue: s.count(letter) % mod == residue))
    result.append(("odd_length", lambda s: len(s) % 2 == 1))
    result.extend(("not_" + name, lambda s, pred=pred: not pred(s))
                  for name, pred in result[:])
    return result


def suffix_majority(examples, s):
    suffix = s[-3:]
    labels = [label for word, label in examples if word[-3:] == suffix]
    if not labels:
        labels = [label for _, label in examples]
    return sum(labels) * 2 > len(labels)


def metric(predict, examples):
    correct = sum(bool(predict(s)) == label for s, label in examples)
    return {"correct": correct, "n": len(examples), "accuracy": round(correct / len(examples), 6)}


def sample_hash(strings):
    return hashlib.sha256(json.dumps(strings, separators=(",", ":")).encode()).hexdigest()


def run_experiment():
    report = {"schema": "r1-0.1", "seed": SEED, "train_labels_per_task": 63,
              "validation_labels_per_task": 192, "holdout_labels_per_task": 256,
              "tasks": [], "fixed_library_size": len(fixed_predicates()), "scientific_status": "NOT_ASSESSED"}
    tasks = [(n, j, "regular") for n, j in regular_tasks()] + [(n, j, "stress") for n, j in stress_tasks()]
    predicates = fixed_predicates()
    for i, (name, judge, family) in enumerate(tasks):
        t = training_words()
        v = validation_words()
        h = heldout_regular(i) if family == "regular" else heldout_stress(i - len(regular_tasks()), judge)
        assert len(set(t)) == 63 and len(set(v)) == 192 and len(set(h)) == 256
        assert not (set(t) & set(v) or set(v) & set(h) or set(t) & set(h))
        train = [(s, bool(judge(s))) for s in t]
        val = [(s, bool(judge(s))) for s in v]
        hold = [(s, bool(judge(s))) for s in h]
        model, attempts = infer(train)
        fixed_name, fixed = min(predicates, key=lambda x: sum(bool(x[1](s)) != label for s, label in train))
        methods = {"induced": model.run,
                   "prefix_memorizer": lambda s, lookup=dict(train): lookup.get(s, False),
                   "suffix3": lambda s, train=train: suffix_majority(train, s),
                   "fixed_library": fixed}
        entry = {"name": name, "family": family, "samples_sha256": {
                    "train": sample_hash(t), "validation": sample_hash(v), "holdout": sample_hash(h)},
                 "induced_states": model.reachable(), "initial_states": len(t), "merge_attempts": attempts,
                 "automaton": model.signature(), "chosen_fixed_predicate": fixed_name,
                 "scores": {}, "counterexamples": {}}
        for method, predict in methods.items():
            entry["scores"][method] = {"train": metric(predict, train), "validation": metric(predict, val),
                                        "holdout": metric(predict, hold)}
            failures = [(s, int(expected), int(bool(predict(s)))) for s, expected in hold
                        if bool(predict(s) != expected)]
            entry["counterexamples"][method] = failures[:3]
        assert entry["scores"]["induced"]["train"]["accuracy"] == 1.0
        report["tasks"].append(entry)
    regs = [x for x in report["tasks"] if x["family"] == "regular"]
    best_control_mean = max(sum(x["scores"][c]["holdout"]["accuracy"] for x in regs) / len(regs)
                            for c in ("prefix_memorizer", "suffix3", "fixed_library"))
    # Stronger per-task oracle control: highest-performing control per task, scored terminally.
    oracle_mean = sum(max(x["scores"][c]["holdout"]["accuracy"]
                          for c in ("prefix_memorizer", "suffix3", "fixed_library")) for x in regs) / len(regs)
    induced_mean = sum(x["scores"]["induced"]["holdout"]["accuracy"] for x in regs) / len(regs)
    success_count = sum(x["scores"]["induced"]["holdout"]["accuracy"] >= .9 for x in regs)
    report["primary"] = {"induced_mean_holdout_accuracy": round(induced_mean, 6),
                        "best_single_control_mean": round(best_control_mean, 6),
                        "per_task_oracle_control_mean": round(oracle_mean, 6),
                        "gain_vs_oracle_control": round(induced_mean - oracle_mean, 6),
                        "tasks_at_least_90_percent": success_count,
                        "predeclared_h1_accepted": induced_mean - oracle_mean >= .05 and success_count >= 6}
    report["total_evaluator_labels"] = len(tasks) * (63 + 192 + 256)
    report["total_merge_attempts"] = sum(x["merge_attempts"] for x in report["tasks"])
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="optional path for canonical JSON report")
    args = parser.parse_args()
    result = run_experiment()
    data = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(data)
    print(json.dumps({"primary": result["primary"], "total_evaluator_labels": result["total_evaluator_labels"],
                      "total_merge_attempts": result["total_merge_attempts"],
                      "tasks": [{"name": t["name"], "states": t["induced_states"],
                                "induced": t["scores"]["induced"]["holdout"]["accuracy"],
                                "fixed": t["scores"]["fixed_library"]["holdout"]["accuracy"]}
                               for t in result["tasks"]]}, sort_keys=True))


if __name__ == "__main__":
    main()
