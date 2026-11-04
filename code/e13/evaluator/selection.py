"""Evaluator-only admission and ranking for the E1.3 selection split."""

import hashlib
import inspect
import json
import random
import re
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from functools import partial
from pathlib import Path

from ..contract import canonical_json, input_value, parse_fit_request, read_json
from ..isolation import _sandbox_python
from ..public_bank import _graph_reference, public_fixtures
from .bank import GROUPS, _REFERENCES, _witness_inputs, development_bank, structural_relation
from .boundary import boundary_report
from .selection_budget import LIMITS, evaluate_arm
from .transfer_bank import _exact_edges, _symbol_reference, transfer_bank

POLICIES = ("structured", "enumerative", "beam")
ORDER_SEED = 131506
REPO_ROOT = Path(__file__).resolve().parents[3]


class SelectionError(ValueError):
    """A selection bank did not meet the evaluator admission rules."""


@dataclass(frozen=True)
class Rule:
    name: str
    family: str
    shape: tuple
    reference: object


def digest(value):
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _input(family, raw):
    input_value(family, raw)
    return raw if family == "S" else {**raw, "edges": sorted(raw["edges"])}


def input_key(family, raw):
    return canonical_json(_input(family, raw))


def _case_keys(episode):
    fit = json.loads(episode.fit_request)
    demos = [item["input"] for role in ("source", "target") for item in fit[role]]
    probes = [json.loads(probe.input) for probe in episode.in_distribution + episode.extrapolation]
    return {input_key(episode.family, value) for value in demos + probes}


def public_rules():
    rules = [Rule(name, family, shape, partial(_REFERENCES[family], name))
             for family, groups in GROUPS.items() for group in groups for name, shape in group]
    for period in (5, 6):
        for phase in (0, 2):
            rules.append(Rule(f"down_{period}_{phase}", "S", ("periodic", ("count", "down")),
                              partial(_symbol_reference, period=period, phase=phase)))
        rules.append(Rule(f"length_{period}", "G", ("exact", ("count", "edges")),
                          partial(_exact_edges, length=period)))
    rules.extend((
        Rule("rise_periodic", "S", ("periodic", ("count", "rise")),
             partial(_symbol_reference, period=2, phase=0, rise=True)),
        Rule("length_three", "G", ("exact", ("count", "edges")), partial(_exact_edges, length=3)),
        Rule("unrestricted_path", "G", ("shortest", "unrestricted"),
             partial(_graph_reference, rule="any")),
        Rule("different_path", "G", ("shortest", ("every", "switch")),
             partial(_graph_reference, rule="different")),
    ))
    return tuple(rules)


def public_inputs():
    keys = {"S": set(), "G": set()}
    for episode in (*development_bank()[0], *transfer_bank()):
        keys[episode.family].update(_case_keys(episode))
    for fixture in public_fixtures():
        fit = json.loads(fixture.fit_request)
        family = fit["family"]
        for examples in (fit["source"], fit["target"]):
            keys[family].update(input_key(family, example["input"]) for example in examples)
        keys[family].update(input_key(family, json.loads(probe.input)) for probe in fixture.probes)
    for report in boundary_report()["families"]:
        family = report["family"]
        for witness in report["witnesses"]:
            keys[family].update(input_key(family, value) for value in witness["inputs"])
    return keys


def _shape(value):
    if isinstance(value, tuple) and 2 <= len(value) <= 8:
        return all(_shape(child) for child in value)
    return isinstance(value, str) and re.fullmatch(r"[a-z][a-z_]{0,31}", value) is not None


def _oracle_path(reference):
    while isinstance(reference, partial):
        reference = reference.func
    path = inspect.getsourcefile(reference)
    if path is None:
        raise SelectionError("oracle source path is unavailable")
    return Path(path).resolve(strict=True)


def _distinct_demos(rule, demos, alternatives):
    inputs = [item["input"] for item in demos]
    labels = canonical_json([item["output"] for item in demos])
    if labels != canonical_json([rule.reference(value) for value in inputs]):
        raise SelectionError("demonstration label disagrees with oracle")
    for alternative in alternatives:
        if alternative is not rule and labels == canonical_json(
            [alternative.reference(value) for value in inputs],
        ):
            raise SelectionError("ambiguous demonstrations")


def audit_bank(episodes, rules):
    """Check normalized structure and finite behavior before any isolated fit."""
    expected = Counter({(f, r): 3 for f in ("S", "G") for r in ("related", "unrelated")})
    if Counter((ep.family, ep.regime) for ep in episodes) != expected:
        raise SelectionError("selection requires three related and three unrelated episodes per family")
    by_name = {(rule.family, rule.name): rule for rule in rules}
    if len(by_name) != len(rules) or not 2 <= len(rules) <= 24:
        raise SelectionError("invalid rule inventory")
    public = public_rules()
    keys = public_inputs()
    witnesses = _witness_inputs()
    public_shapes = {(rule.family, canonical_json(rule.shape)) for rule in public}
    fingerprints = set()
    records = []
    oracle_paths = set()
    for rule in rules:
        if rule.family not in ("S", "G") or not isinstance(rule.shape, tuple) or not _shape(rule.shape):
            raise SelectionError("invalid normalized rule shape")
        if (rule.family, canonical_json(rule.shape)) in public_shapes:
            raise SelectionError("public rule shape overlap")
        path = _oracle_path(rule.reference)
        if path.is_relative_to(REPO_ROOT):
            raise SelectionError("selection oracle is inside candidate checkout")
        oracle_paths.add(path)
        inputs = (*witnesses[rule.family], *(json.loads(key) for key in sorted(keys[rule.family])))
        outputs = digest([rule.reference(value) for value in inputs])
        if any(rule.family == old.family and outputs == digest([old.reference(value) for value in inputs])
               for old in public):
            raise SelectionError("public witness behavior overlap")
        if (rule.family, outputs) in fingerprints:
            raise SelectionError("selection rules indistinguishable on finite witnesses")
        fingerprints.add((rule.family, outputs))
        records.append((rule.family, rule.name, rule.shape, outputs))

    used_ids, used_targets, used_rules, task_hashes = set(), set(), set(), set()
    seen_inputs = {family: set(values) for family, values in keys.items()}
    episode_hashes = []
    for episode in episodes:
        request = parse_fit_request(episode.fit_request)
        if request.family != episode.family or request.task_id in used_ids:
            raise SelectionError("invalid or reused episode identity")
        used_ids.add(request.task_id)
        source = by_name.get((episode.family, episode.source_rule))
        target = by_name.get((episode.family, episode.target_rule))
        if source is None or target is None or (target.family, target.name) in used_targets:
            raise SelectionError("missing rule or reused target block")
        distance, shared = structural_relation(source.shape, target.shape)
        if distance == 0 or shared != (episode.regime == "related"):
            raise SelectionError("source/target structure does not match regime")
        used_targets.add((target.family, target.name))
        used_rules.update(((source.family, source.name), (target.family, target.name)))
        fit = json.loads(episode.fit_request)
        alternatives = [rule for rule in (*rules, *public) if rule.family == episode.family]
        _distinct_demos(source, fit["source"], alternatives)
        _distinct_demos(target, fit["target"], alternatives)
        values = []
        for role in ("source", "target"):
            values.extend(input_key(episode.family, demo["input"]) for demo in fit[role])
        for probes in (episode.in_distribution, episode.extrapolation):
            if len(probes) != 4:
                raise SelectionError("selection requires four ordinary and four extrapolation probes")
            for probe in probes:
                value = read_json(probe.input, 4_096)
                values.append(input_key(episode.family, value))
                if canonical_json(probe.expected) != canonical_json(target.reference(value)):
                    raise SelectionError("probe label disagrees with oracle")
        if len(values) != len(set(values)) or seen_inputs[episode.family].intersection(values):
            raise SelectionError("normalized input overlap")
        seen_inputs[episode.family].update(values)
        task = digest([episode.family, sorted(value.hex() for value in values)])
        if task in task_hashes:
            raise SelectionError("normalized task overlap")
        task_hashes.add(task)
        episode_hashes.append(digest([episode.regime, episode.source_rule, episode.target_rule,
                                      fit, [(json.loads(p.input), p.expected)
                                            for p in episode.in_distribution + episode.extrapolation]]))
    if used_rules != by_name.keys():
        raise SelectionError("unused evaluator rule")
    return {
        "split": "selection", "status": "admitted", "episodes": len(episodes),
        "target_blocks": len(used_targets), "oracle_rules": len(rules),
        "bank_sha256": digest([sorted(records), episode_hashes]),
        "public_inputs": {family: len(cases) for family, cases in keys.items()},
        "oracle_source_sha256": sorted(hashlib.sha256(path.read_bytes()).hexdigest()
                                       for path in oracle_paths),
        "equivalence": "UNKNOWN outside finite witnesses",
    }


def rank(rows):
    """Equal family weights, then lower measured CPU and lexical policy ID."""
    ranked = []
    for policy in POLICIES:
        subset = [row for row in rows if row["policy"] == policy]
        families = {}
        for family in ("S", "G"):
            outcomes = [score for row in subset if row["family"] == family
                        for score in row["scores"].values()]
            families[family] = {"correct": sum(s["correct"] for s in outcomes),
                                "total": sum(s["total"] for s in outcomes),
                                "failures": sum(s["failures"] for s in outcomes)}
        if any(not s["total"] for s in families.values()):
            raise SelectionError("missing family or policy in selection ranking")
        accuracy = sum(Fraction(s["correct"], s["total"]) for s in families.values()) / 2
        cpu = sum(row["total_cpu_us"] for row in subset)
        ranked.append((accuracy, cpu, policy, families))
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [{"policy": p, "accuracy": float(a), "cpu_us": c, "families": f}
            for a, c, p, f in ranked]


def run_selection(episodes, rules):
    audit = audit_bank(episodes, rules)
    paths = sorted({_oracle_path(rule.reference) for rule in rules})
    script = """
import sys
for name in sys.argv[1:]:
    try:
        with open(name, 'rb'):
            pass
    except FileNotFoundError:
        continue
    raise RuntimeError('private evaluator source is visible')
print('evaluator sources inaccessible')
"""
    result, _ = _sandbox_python(["-c", script, *(str(path) for path in paths)])
    if result != b"evaluator sources inaccessible\n":
        raise SelectionError("evaluator source isolation canary failed")
    audit["worker_canary"] = "pass"
    schedule = [(episode, policy) for episode in episodes for policy in POLICIES]
    random.Random(ORDER_SEED).shuffle(schedule)
    rows = [evaluate_arm(episode, policy) for episode, policy in schedule]
    ranking = rank(rows)
    public = {"mode": "selection", "audit": audit, "budget": LIMITS,
              "order_seed": ORDER_SEED, "ranking": ranking,
              "selected": ranking[0]["policy"], "arms": len(rows),
              "fit_status": {p: dict(Counter(r["fit_status"] for r in rows if r["policy"] == p))
                             for p in POLICIES},
              "score_cap_arms": sum(row["cap_reached"] for row in rows)}
    return public, rows
