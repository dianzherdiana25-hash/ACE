"""Check whether existing bounded programs cover the public rule witnesses."""

import json

from ..contract import canonical_json
from ..dsl import Fuel, predict
from ..isolation import fit_isolated
from .bank import GROUPS, _REFERENCES, development_bank


def development_capacity():
    """Find a bounded witness program for each rule by counterexample refinement.

    This separate evaluator exercise uses public labels and is never part of fit,
    model selection, or the development pilot's scored runs.
    """
    episodes, _, common = development_bank()
    output = []
    for family, groups in GROUPS.items():
        reference = _REFERENCES[family]
        for group in groups:
            for rule, _ in group:
                cases = {canonical_json(value): reference(rule, value) for value in common[family]}
                for episode in episodes:
                    if episode.family != family:
                        continue
                    data = json.loads(episode.fit_request)
                    if episode.source_rule == rule:
                        cases.update((canonical_json(d["input"]), reference(rule, d["input"]))
                                     for d in data["source"])
                    if episode.target_rule == rule:
                        cases.update((canonical_json(d["input"]), reference(rule, d["input"]))
                                     for d in data["target"])
                        cases.update((probe.input, probe.expected)
                                     for probe in episode.in_distribution + episode.extrapolation)
                first = next(iter(cases))
                demos = [{"input": json.loads(first), "output": cases[first]}]
                match = None
                while len(demos) <= 16:
                    request = canonical_json({
                        "version": 1, "family": family, "task_id": "0" * 32,
                        "seed": 0, "fuel": 100_000, "source": demos[:1], "target": demos,
                    })
                    fit = fit_isolated(request, policy="blind")
                    mismatch = next((value for value, expected in cases.items()
                                     if predict(fit.program.ast, value, Fuel(100_000)) != expected),
                                    None)
                    if mismatch is None:
                        match = fit.program
                        break
                    example = {"input": json.loads(mismatch), "output": cases[mismatch]}
                    if example in demos:
                        break
                    demos.append(example)
                output.append({
                    "family": family, "rule": rule, "witnesses": len(cases),
                    "status": "covered_on_witnesses" if match else "unknown",
                    "ast_sha256": match.sha256 if match else None,
                    "ast": json.loads(match.ast) if match else None,
                })
    return output


def main():
    print(json.dumps({"mode": "development", "rules": development_capacity()}, indent=2))


if __name__ == "__main__":
    main()
