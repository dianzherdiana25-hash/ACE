"""Bounded composition of unchanged R1 guards and S2 counter programs.

The product grammar is authored; guard structure is induced from labeled errors.
Public development only. No learned program is deployed or executed as source.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import random

from ace_candidate_search import model
from ace_research_primitives import primitive_discovery as r1
from . import structural as s

PROTOCOL_COMMIT = "7b9eea945175c67300118187ab55f1e8e776f005"
PROTOCOL_AMENDMENT = "54030a3226da020298ee2cc0f7f65649bc364f93"
TASKS = ("equal", "starts", "ends", "boundaries", "contains",
         "ratio2_boundaries", "ratio4", "dyck")
SEEDS = (20261106, 20261107, 20261108)
GUARDS = ("true", "starts", "ends", "boundaries", "contains")


def guard(kind, word):
    return {"true": lambda: True,
            "starts": lambda: word.startswith("a"),
            "ends": lambda: word.endswith("b"),
            "boundaries": lambda: word.startswith("a") and word.endswith("b"),
            "contains": lambda: "ab" in word}[kind]()


@dataclass
class Work:
    predictions: int = 0
    ast_nodes: int = 0
    dfa_character_upper_bound: int = 0


@dataclass(frozen=True)
class Program:
    kind: str
    weights: tuple[int, int] | None = None
    automaton: object = field(default=None, repr=False, compare=False)
    fixed_guard: str = "true"

    def data(self):
        return {"kind": self.kind,
                "counter_ast": s.typed_ast(model, self.weights).data() if self.weights else None,
                "weights": list(self.weights) if self.weights else None,
                "dfa": self.automaton.signature() if self.automaton else None,
                "fixed_guard": self.fixed_guard}

    @property
    def identity(self):
        return s.digest(self.data())

    def predict(self, word, work=None):
        if type(word) is not str or set(word) - {"a", "b"} or len(word) > 100:
            raise ValueError("bounded binary input required")
        work = work if work is not None else Work()
        work.predictions += 1
        if self.weights:
            meter = model.Meter(100)
            value = model.interpret(s.typed_ast(model, self.weights),
                                    word.count("a"), word.count("b"), meter)
            work.ast_nodes += meter.work
            if value != 0:
                return False
        if self.automaton:
            work.dfa_character_upper_bound += len(word)
            return self.automaton.run(word)
        return guard(self.fixed_guard, word)


def validate_rows(rows, limit):
    if not isinstance(rows, (list, tuple)) or not 1 <= len(rows) <= limit:
        raise ValueError("observation budget exceeded")
    seen = set()
    for row in rows:
        if (not isinstance(row, (list, tuple)) or len(row) != 2 or
                type(row[0]) is not str or type(row[1]) is not bool or
                set(row[0]) - {"a", "b"} or len(row[0]) > 100 or row[0] in seen):
            raise ValueError("invalid or duplicate observation")
        seen.add(row[0])


def correct(program, rows, work):
    return sum(program.predict(word, work) == label for word, label in rows)


def select(candidates, train, validation):
    work = Work()
    scores = [(correct(p, validation, work), correct(p, train, work), p.identity, p)
              for p in candidates]
    val, tr, _, best = min(scores, key=lambda row: (-row[0], -row[1], row[2]))
    return best, {"train_correct": tr, "validation_correct": val,
                  "admitted": tr == len(train) and val == len(validation),
                  "candidate_count": len(candidates), "work": vars(work)}


def fit(train, validation):
    """No task identity, oracle or terminal observations enter this interface."""
    validate_rows(train, 63)
    validate_rows(validation, 128)
    if {w for w, _ in train} & {w for w, _ in validation}:
        raise ValueError("overlapping train/validation")
    baseline, base_merges = r1.infer(train)
    counters = [Program("counter", weights) for weights in s.coefficient_grammar()]
    products = []
    triggers = []
    proposal_work = Work()
    residual_merges = 0
    for counter in counters:
        predictions = [(word, label, counter.predict(word, proposal_work))
                       for word, label in train]
        residual = [(word, label) for word, label, accepted in predictions if accepted]
        false_positives = [word for word, label in residual if not label]
        false_negatives = sum(label and not accepted for _, label, accepted in predictions)
        if false_positives and any(label for _, label in residual) and not false_negatives:
            learned, attempts = r1.infer(residual)
            residual_merges += attempts
            product = Program("product", counter.weights, learned)
            products.append(product)
            triggers.append({"counter": counter.identity, "product": product.identity,
                             "false_positive_words": false_positives,
                             "residual_labels": len(residual), "merge_attempts": attempts})
    fixed = [Program("fixed_product", weights, fixed_guard=g)
             for weights in s.coefficient_grammar() for g in GUARDS]
    arms = {"dfa": [Program("dfa", automaton=baseline)], "counter": counters,
            "composition": [Program("dfa", automaton=baseline)] + counters + products,
            "fixed_product": fixed}
    selected, reports = {}, {}
    for arm, candidates in arms.items():
        selected[arm], reports[arm] = select(candidates, train, validation)
        reports[arm]["program"] = selected[arm].data()
        reports[arm]["identity"] = selected[arm].identity
    return selected, {"arms": reports, "counterexample_triggers": triggers,
                      "source_heads": {"R1": s.R1_HEAD, "S2": s.S2_HEAD},
                      "base_merge_attempts": base_merges,
                      "residual_merge_attempts": residual_merges,
                      "proposal_work": vars(proposal_work),
                      "train_sha256": s.digest(train),
                      "validation_sha256": s.digest(validation)}


def truth(task, word):
    ratio = 2 if task == "ratio2_boundaries" else 4 if task == "ratio4" else 1
    counts = word.count("a") == ratio * word.count("b")
    if task == "dyck":
        return r1.dyck(word)
    kind = "boundaries" if task == "ratio2_boundaries" else task
    return counts and (guard(kind, word) if kind in GUARDS else True)


def balanced(task, seed, lengths):
    rng = random.Random(seed)
    groups = []
    for positive in (False, True):
        words = set()
        for _ in range(100000):
            n = rng.choice(lengths)
            if positive:
                ratio = 2 if task == "ratio2_boundaries" else 4 if task == "ratio4" else 1
                possible = [v for v in lengths if v % (ratio + 1) == 0]
                n = rng.choice(possible)
                b = n // (ratio + 1)
                chars = ["a"] * (n - b) + ["b"] * b
                rng.shuffle(chars)
                word = "".join(chars)
            else:
                word = "".join(rng.choice("ab") for _ in range(n))
            if truth(task, word) == positive:
                words.add(word)
            if len(words) == 64:
                break
        if len(words) != 64:
            raise RuntimeError("balanced sample budget exhausted")
        groups.extend(words)
    return [(w, truth(task, w)) for w in sorted(groups, key=lambda w: (len(w), w))]


def bank(task, seed):
    if task not in TASKS:
        raise ValueError("unknown evaluator task")
    train = [(w, truth(task, w)) for w in r1.training_words()]
    validation = balanced(task, seed, tuple(range(6, 16)))
    terminal = balanced(task, seed + 100000, tuple(range(16, 31)))
    return train, validation, terminal


def replay(program_data, word):
    """Independent semantics for serialized counter/product/DFA decisions."""
    weights = program_data["weights"]
    if weights and weights[0] * word.count("a") + weights[1] * word.count("b") != 0:
        return False
    signature = program_data["dfa"]
    if signature:
        state = 0
        for char in word:
            edges = dict(signature[state][1])
            if char not in edges:
                return False
            state = edges[char]
        return signature[state][0] is True
    return guard(program_data["fixed_guard"], word)


def run():
    rows, retained = [], []
    for seed in SEEDS:
        for task in TASKS:
            train, validation, terminal = bank(task, seed)
            selected, report = fit(train, validation)
            for arm, program in selected.items():
                work = Work()
                predictions = [program.predict(w, work) for w, _ in terminal]
                independent = [replay(program.data(), w) for w, _ in terminal]
                if predictions != independent:
                    raise RuntimeError("independent semantic replay mismatch")
                report["arms"][arm]["terminal_correct"] = sum(
                    pred == label for pred, (_, label) in zip(predictions, terminal))
                report["arms"][arm]["terminal_work"] = vars(work)
                report["arms"][arm]["terminal_predictions_sha256"] = s.digest(predictions)
            report.update(task=task, seed=seed, terminal_total=len(terminal),
                          terminal_sha256=s.digest(terminal))
            rows.append(report)
            retained.append((selected["composition"], selected["composition"].identity))
    if not all(p.identity == identity for p, identity in retained):
        raise RuntimeError("retained model changed")
    summaries = {arm: sum(row["arms"][arm]["terminal_correct"] for row in rows)
                 for arm in ("dfa", "counter", "composition", "fixed_product")}
    witness = rows[0]["arms"]["composition"]
    return {"schema": "ace.composition.public.v03", "protocol_commit": PROTOCOL_COMMIT,
            "protocol_amendment": PROTOCOL_AMENDMENT,
            "trials": rows, "terminal_total": len(rows) * 128,
            "terminal_correct": summaries,
            "product_selections": sum(row["arms"]["composition"]["program"]["kind"] == "product"
                                      for row in rows),
            "retained_fingerprints": [identity for _, identity in retained],
            "nominal_label_presentations": len(rows) * (63 + 128 + 128),
            "late_flip_witness": {"task": "equal", "seed": SEEDS[0],
                                  "identical_training_validation": True,
                                  "same_selected_identity": witness["identity"],
                                  "ordinary_correct": witness["terminal_correct"],
                                  "inverted_correct": 128 - witness["terminal_correct"],
                                  "total": 128},
            "beats_fixed_library": summaries["composition"] > summaries["fixed_product"],
            "compute_matched": False, "open_world_safe": False,
            "complete_compute_accounting": False,
            "work_accounting_scope": "R1 merge attempts and controller predictions/AST nodes; "
                                     "excludes internal R1 consistency checks and semantic replay",
            "protocol_deviations": ["Full internal R1 prediction accounting remains OPEN"],
            "scientific_decision": "NOT_ASSESSED", "oaie_established": False,
            "candidate_deployed": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(s.canonical(result))
    print(json.dumps({key: result[key] for key in (
        "terminal_total", "terminal_correct", "product_selections",
        "beats_fixed_library", "scientific_decision")}, sort_keys=True))


if __name__ == "__main__":
    main()
