"""ACE R8: fail-closed, task-family-aware measurement for public synthetic studies.

Input rows are evaluator-produced records, not candidate-authored claims. A
row's fingerprint must identify its full semantic instance, not a display ID.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
import random
from typing import Iterable


@dataclass(frozen=True)
class Record:
    case_id: str
    split: str  # development / validation / evaluation
    family: str
    fingerprint: str  # canonical semantic instance digest
    structure: str  # normalized program shape or mechanism
    novel: bool
    compositional: bool
    baseline_correct: bool
    candidate_correct: bool
    pre_correct: bool
    post_correct: bool
    baseline_ops: int
    candidate_ops: int
    baseline_labels: int = 0
    candidate_labels: int = 0


def semantic_fingerprint(spec: dict) -> str:
    """Hash unambiguous canonical task semantics, excluding public display IDs."""
    serialized = json.dumps(spec, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def validate(records: Iterable[Record]) -> list[Record]:
    rows = list(records)
    if not rows:
        raise ValueError("empty dataset")
    identifiers = set()
    fingerprints = {}
    for r in rows:
        if not isinstance(r, Record):
            raise ValueError("unsupported record")
        if not r.case_id or not r.family or not r.structure:
            raise ValueError("missing identity/family/structure")
        if r.split not in {"development", "validation", "evaluation"}:
            raise ValueError("invalid split")
        if len(r.fingerprint) != 64 or any(c not in "0123456789abcdef" for c in r.fingerprint):
            raise ValueError("fingerprint must be canonical lowercase SHA256")
        if r.case_id in identifiers:
            raise ValueError("duplicate case ID")
        identifiers.add(r.case_id)
        if r.fingerprint in fingerprints:
            raise ValueError("semantic duplicate or cross-split contamination: " + r.case_id)
        fingerprints[r.fingerprint] = r.split
        for name in ("novel", "compositional", "baseline_correct", "candidate_correct",
                     "pre_correct", "post_correct"):
            if type(getattr(r, name)) is not bool:
                raise ValueError("invalid boolean " + name)
        for name in ("baseline_ops", "candidate_ops", "baseline_labels", "candidate_labels"):
            v = getattr(r, name)
            if type(v) is not int or v < 0:
                raise ValueError("invalid nonnegative integer cost " + name)
    if not any(r.split == "development" for r in rows):
        raise ValueError("missing development records")
    if not any(r.split == "evaluation" for r in rows):
        raise ValueError("missing evaluation records")
    development_structures = {r.structure for r in rows if r.split == "development"}
    development_families = {r.family for r in rows if r.split == "development"}
    for r in rows:
        if r.split == "evaluation" and r.novel and (r.structure in development_structures or r.family in development_families):
            raise ValueError("novel task shares development structure or family: " + r.case_id)
    return rows


def _rates(rows: list[Record]) -> dict:
    groups = defaultdict(list)
    for r in rows:
        groups[r.family].append(r)
    family_deltas = {
        family: sum(int(r.candidate_correct) - int(r.baseline_correct) for r in rs) / len(rs)
        for family, rs in sorted(groups.items())
    }
    return {
        "n": len(rows),
        "families": len(groups),
        "baseline_accuracy": sum(r.baseline_correct for r in rows) / len(rows),
        "candidate_accuracy": sum(r.candidate_correct for r in rows) / len(rows),
        "micro_delta": sum(int(r.candidate_correct) - int(r.baseline_correct) for r in rows) / len(rows),
        "family_macro_delta": sum(family_deltas.values()) / len(groups),
        "family_deltas": family_deltas,
        "baseline_ops": sum(r.baseline_ops for r in rows),
        "candidate_ops": sum(r.candidate_ops for r in rows),
        "baseline_labels": sum(r.baseline_labels for r in rows),
        "candidate_labels": sum(r.candidate_labels for r in rows),
        "post_minus_pre": sum(int(r.post_correct) - int(r.pre_correct) for r in rows) / len(rows),
    }


def _bootstrap_family_ci(deltas: dict[str, float], *, seed: int = 932, draws: int = 3000) -> list[float] | None:
    """Exploratory cluster bootstrap by family; NOT a confirmatory interval."""
    values = list(deltas.values())
    if len(values) < 4:
        return None
    rng = random.Random(seed)
    n = len(values)
    samples = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(draws))
    return [samples[int(0.025 * draws)], samples[min(draws - 1, int(0.975 * draws))]]


def measure(records: Iterable[Record]) -> dict:
    rows = validate(records)
    evaluation = [r for r in rows if r.split == "evaluation"]
    subsets = {
        "all": evaluation,
        "novel": [r for r in evaluation if r.novel],
        "compositional": [r for r in evaluation if r.compositional],
        "routine": [r for r in evaluation if not r.novel and not r.compositional],
    }
    summaries = {name: (_rates(group) if group else None) for name, group in subsets.items()}
    overall = summaries["all"]
    ci = _bootstrap_family_ci(overall["family_deltas"])
    signals = []
    if overall["micro_delta"] > 0 and overall["family_macro_delta"] <= 0:
        signals.append("GOODHART_MICRO_MACRO_INVERSION")
    if summaries["novel"] is None or summaries["novel"]["families"] < 4:
        signals.append("INSUFFICIENT_NOVEL_FAMILY_COVERAGE")
    if summaries["compositional"] is None or summaries["compositional"]["families"] < 4:
        signals.append("INSUFFICIENT_COMPOSITIONAL_FAMILY_COVERAGE")
    if ci is None or ci[0] <= 0:
        signals.append("NO_POSITIVE_EXPLORATORY_FAMILY_CI")
    if overall["candidate_ops"] > 2 * max(1, overall["baseline_ops"]):
        signals.append("OVER_2X_OPERATION_BUDGET")
    dev_families = sorted({r.family for r in rows if r.split == "development"})
    return {
        "schema": "ace.r8.measurement.v1",
        "status": "PUBLIC_SYNTHETIC_DIAGNOSTIC_ONLY",
        "development_families": dev_families,
        "evaluation_families": sorted(overall["family_deltas"]),
        "evaluation": summaries,
        "exploratory_family_bootstrap_95pct": ci,
        "signals": signals,
        "claim_gate": "NOT_CONFIRMED",  # no synthetic suite alone may prove intelligence growth
        "notes": [
            "All splits and task generators in this package are public; evaluation is NOT sealed.",
            "Records must originate from trusted evaluator and independently verified semantics.",
            "CPU operations and evaluator labels are separate units; no equivalent wall-clock cap is claimed.",
            "Exploratory CIs do not account for experiment selection or researcher degrees of freedom.",
        ],
    }
