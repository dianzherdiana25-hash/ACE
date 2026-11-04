"""Generate and audit public development episodes before exposing their fit bytes."""

import argparse
import hashlib
import json
import random
from dataclasses import dataclass
from functools import partial
from itertools import product

from ..contract import canonical_json, parse_fit_request
from ..public_bank import Probe
from ..split_audit import RuleBlock, audit_splits
from . import oracle


@dataclass(frozen=True)
class Episode:
    family: str
    regime: str
    source_rule: str
    target_rule: str
    fit_request: bytes
    in_distribution: tuple[Probe, ...]
    extrapolation: tuple[Probe, ...]


# The trees encode semantic operators and erase incidental constants and names.
GROUPS = {
    "S": (
        (("repeat", ("emit", ("pair", "equal"))),
         ("repeat_run", ("conjoin_previous", ("pair", "equal"))),
         ("down", ("emit", ("pair", "down")))),
        (("rise", ("emit", ("pair", "rise"))),
         ("rise_start", ("rising_event", ("pair", "rise"))),
         ("down_parity", ("event_parity", ("pair", "down")))),
    ),
    "G": (
        (("repeat_once", ("exact", ("count", "repeat"))),
         ("repeat_odd", ("odd", ("count", "repeat"))),
         ("edge_even", ("even", ("count", "edges")))),
        (("switch_once", ("exact", ("count", "switch"))),
         ("switch_at_least_two", ("at_least", ("count", "switch"))),
         ("edge_min_three", ("at_least", ("count", "edges")))),
    ),
}
_REFERENCES = {"S": oracle.symbols, "G": oracle.graph}
_REGIMES = ("related", "unrelated")


def _size(tree):
    return 1 + sum(_size(child) for child in tree[1:]) if isinstance(tree, tuple) else 1


def _distance(left, right):
    """Ordered edit cost with unit relabeling and whole-subtree insertion/deletion."""
    left = left if isinstance(left, tuple) else (left,)
    right = right if isinstance(right, tuple) else (right,)
    row = [0]
    for child in right[1:]:
        row.append(row[-1] + _size(child))
    for a in left[1:]:
        new = [row[0] + _size(a)]
        for i, b in enumerate(right[1:], 1):
            new.append(min(new[-1] + _size(b), row[i] + _size(a),
                           row[i - 1] + _distance(a, b)))
        row = new
    return int(left[0] != right[0]) + row[-1]


def _subtrees(tree):
    if not isinstance(tree, tuple):
        return set()
    return {tree}.union(*(_subtrees(child) for child in tree[1:]))


def structural_relation(source, target):
    distance = _distance(source, target) / (_size(source) + _size(target))
    return distance, bool(_subtrees(source) & _subtrees(target))


def _chain(labels, costs=None):
    if costs is None:
        costs = [1] * len(labels)
    return {"nodes": len(labels) + 1, "start": 0, "goal": len(labels),
            "edges": [[i, i + 1, label, costs[i]] for i, label in enumerate(labels)]}


def _witness_inputs():
    # Exhaustive finite witness domains, shared across all blocks in each family.
    return {
        "S": tuple(list(values) for n in range(5) for values in product(range(3), repeat=n)),
        "G": tuple(_chain(labels) for n in range(7) for labels in product(range(2), repeat=n)),
    }


def _case(family, rng, extrapolation):
    if family == "S":
        length = rng.randint(17, 28) if extrapolation else rng.randint(5, 9)
        return [rng.randrange(4) for _ in range(length)]
    length = rng.randint(9, 12) if extrapolation else rng.randint(2, 6)
    value = _chain([rng.randrange(2) for _ in range(length)],
                   [rng.randrange(1, 8) for _ in range(length)])
    for _ in range(length + 1):
        value["edges"].append([rng.randrange(value["nodes"]), rng.randrange(value["nodes"]),
                               rng.randrange(2), rng.randrange(8)])
    value["edges"].sort()
    return value


def _examples(family, rule, rules, witnesses, rng, used):
    reference = _REFERENCES[family]
    competitors = set(rules) - {rule}
    examples = []
    for _ in range(128):
        if not competitors and len(examples) >= 4:
            return examples
        value = _case(family, rng, False)
        key = canonical_json(value)
        if key in used:
            continue
        expected = reference(rule, value)
        ruled_out = {other for other in competitors if reference(other, value) != expected}
        if ruled_out or len(examples) < 4:
            used.add(key)
            examples.append({"input": value, "output": expected})
            competitors -= ruled_out

    # A bounded witness fallback separates rules whose random examples were ambiguous.
    for value in witnesses:
        key = canonical_json(value)
        if key in used:
            continue
        expected = reference(rule, value)
        ruled_out = {other for other in competitors if reference(other, value) != expected}
        if ruled_out:
            used.add(key)
            examples.append({"input": value, "output": expected})
            competitors -= ruled_out
        if not competitors and len(examples) >= 4:
            return examples
    raise ValueError("quarantined ambiguous demonstrations")


def _probes(family, rule, rng, used, extrapolation):
    result = []
    for _ in range(64):
        value = _case(family, rng, extrapolation)
        key = canonical_json(value)
        if key not in used:
            used.add(key)
            result.append(Probe(key, _REFERENCES[family](rule, value)))
            if len(result) == 6:
                return tuple(result)
    raise ValueError("insufficient distinct probe inputs")


def development_bank(seed=1304):
    """Build 12 episodes per family and validate all blocks before returning."""
    rng = random.Random(seed)
    witnesses = _witness_inputs()
    episodes, blocks = [], []
    for family, groups in GROUPS.items():
        rules = {rule: shape for group in groups for rule, shape in group}
        task_payloads = {rule: [] for rule in rules}
        inputs = {rule: [] for rule in rules}
        for (source, source_shape), *targets in groups:
            for regime, (target, target_shape) in zip(_REGIMES, targets, strict=True):
                distance, shared = structural_relation(source_shape, target_shape)
                if not distance or shared != (regime == "related"):
                    raise ValueError("rule block violates structural regime")
                for _ in range(3):
                    used = set()
                    source_examples = _examples(family, source, rules, witnesses[family], rng, used)
                    target_examples = _examples(family, target, rules, witnesses[family], rng, used)
                    ordinary = _probes(family, target, rng, used, extrapolation=False)
                    extrapolation = _probes(family, target, rng, used, extrapolation=True)
                    task_payloads[source].append(sorted(source_examples, key=canonical_json))
                    inputs[source].extend(example["input"] for example in source_examples)
                    test_inputs = [json.loads(probe.input) for probe in ordinary + extrapolation]
                    inputs[target].extend(example["input"] for example in target_examples)
                    inputs[target].extend(test_inputs)
                    task_payloads[target].append({
                        "demos": sorted(target_examples, key=canonical_json),
                        "probes": sorted(test_inputs, key=canonical_json),
                    })
                    payload = canonical_json({
                        "version": 1, "family": family, "task_id": f"{rng.getrandbits(128):032x}",
                        "seed": rng.getrandbits(32), "fuel": 30_000,
                        "source": source_examples, "target": target_examples,
                    })
                    parse_fit_request(payload)
                    episodes.append(Episode(family, regime, source, target, payload,
                                            ordinary, extrapolation))
        behaviors = set()
        for rule, shape in rules.items():
            reference = partial(_REFERENCES[family], rule)
            signature = canonical_json([reference(value) for value in witnesses[family]])
            if signature in behaviors:
                raise ValueError("indistinguishable development rule block")
            behaviors.add(signature)
            blocks.append(RuleBlock(family, "development", shape,
                                    tuple(task_payloads[rule]), reference, tuple(inputs[rule])))
    audit_splits(blocks, witnesses)
    return tuple(episodes), tuple(blocks), witnesses


def bank_digest(episodes):
    records = [{
        "fit": json.loads(episode.fit_request), "regime": episode.regime,
        "source_rule": episode.source_rule, "target_rule": episode.target_rule,
        "in_distribution": [(json.loads(probe.input), probe.expected)
                            for probe in episode.in_distribution],
        "extrapolation": [(json.loads(probe.input), probe.expected)
                          for probe in episode.extrapolation],
    } for episode in episodes]
    return hashlib.sha256(canonical_json(records)).hexdigest()


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    episodes, blocks, witnesses = development_bank()
    print(json.dumps({
        "split": "development", "seed": 1304, "episodes": len(episodes),
        "rule_blocks": len(blocks), "witness_inputs": {f: len(w) for f, w in witnesses.items()},
        "sha256": bank_digest(episodes),
    }, indent=2))


if __name__ == "__main__":
    main()
