"""OMEGA-09 — Mutation, Recombination and Diversity Engine.

Candidates in this programme are *genotypes*: structured configurations
(planner, algorithm, representation, learning method, architecture,
tool set, prompt template, numeric parameters). The engine proposes
children by mutation (seven classes, mirroring the programme document)
and recombination, under three hard rules:

* **Admission before existence.** A child genotype is validated against
  the schema — enumerated fields may only take enumerated values, tools
  must come from the allowed universe, numeric parameters must sit
  inside their bounds. Invalid proposals are rejected *with reasons*
  and returned as negative results, never silently dropped.
* **Regression preservation.** Each mutation class may touch only its
  own field group. A parameter mutation that quietly changes the
  planner is not a parameter mutation, and the engine's own diff proves
  it: every proposal carries the exact field diff against its parent.
* **Novelty is structural, and claims are capped.** Novelty is a
  distance measurement against the known population (with an epsilon
  dead-zone so cosmetic jitter is not "novel"). The highest class the
  engine will ever assign is ``novel``. There is no code path that
  certifies a "new primitive": such a claim is recorded as unverified,
  per the OMEGA-09 gate.

Search is bounded (a proposal budget) and deterministic under a seed.
The engine proposes genotypes; it does not evaluate them and it makes
no capability claims — evaluation belongs to OMEGA-06's kernel and
selection to OMEGA-08's archive.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
from typing import Any


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def genotype_digest(genotype: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(genotype).encode("utf-8")).hexdigest()


# field -> (kind, spec, mutation class)
SCHEMA: dict[str, tuple[str, Any, str]] = {
    "planner": ("enum", ["greedy", "best-first", "beam", "mcts-lite"], "planner"),
    "algorithm": ("enum", ["hill-climb", "simulated-annealing", "genetic", "random-restart"], "algorithm"),
    "representation": ("enum", ["ast", "token-stream", "graph", "diff"], "representation"),
    "learning": ("enum", ["none", "bandit", "imitation", "self-distill"], "learning"),
    "architecture": ("enum", ["single", "planner-worker", "critic-loop", "ensemble"], "architecture"),
    "prompt_template": ("enum", ["direct", "plan-first", "verify-each-step", "socratic"], "prompt"),
    "tool_set": ("toolset", ["read", "search", "edit", "test", "shell"], "tool"),
    "max_tokens": ("numeric", (128, 4096, 8), "parameter"),
    "temperature": ("numeric", (0.0, 1.5, 0.02), "parameter"),
    "max_attempts": ("numeric", (1, 8, 0.5), "parameter"),
}
MUTATION_CLASSES = sorted({spec[2] for spec in SCHEMA.values()})


def validate_genotype(genotype: dict[str, Any]) -> list[str]:
    """Return the list of admission errors (empty = admissible)."""
    errors = []
    for field, (kind, spec, _cls) in SCHEMA.items():
        if field not in genotype:
            errors.append(f"missing field: {field}")
            continue
        value = genotype[field]
        if kind == "enum" and value not in spec:
            errors.append(f"{field}: {value!r} not in {spec}")
        elif kind == "toolset":
            unknown = [t for t in value if t not in spec]
            if unknown:
                errors.append(f"tool_set: unknown tools {unknown}")
            if not value:
                errors.append("tool_set: must not be empty")
        elif kind == "numeric":
            low, high, _eps = spec
            if not isinstance(value, (int, float)) or not low <= value <= high:
                errors.append(f"{field}: {value!r} outside [{low}, {high}]")
    for field in genotype:
        if field not in SCHEMA:
            errors.append(f"unknown field: {field}")
    return errors


def genotype_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    """Mean per-field distance in [0, 1]; numeric deltas below epsilon are 0."""
    total = 0.0
    for field, (kind, spec, _cls) in SCHEMA.items():
        va, vb = a.get(field), b.get(field)
        if kind == "enum":
            total += 0.0 if va == vb else 1.0
        elif kind == "toolset":
            sa, sb = set(va or []), set(vb or [])
            union = sa | sb
            total += 0.0 if not union else 1.0 - len(sa & sb) / len(union)
        elif kind == "numeric":
            low, high, eps = spec
            delta = abs(float(va) - float(vb))
            total += 0.0 if delta < eps else min(1.0, delta / (high - low))
    return total / len(SCHEMA)


def field_diff(a: dict[str, Any], b: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {field: {"from": a.get(field), "to": b.get(field)}
            for field in SCHEMA if a.get(field) != b.get(field)}


def classify_novelty(child: dict[str, Any], population: list[dict[str, Any]],
                     *, threshold: float = 0.3,
                     claims_primitive: bool = False) -> dict[str, Any]:
    """Classify a child against the known population.

    duplicate: distance 0 to some member. variant: nearer than the
    threshold to some member. novel: at least the threshold from every
    member, or an unseen categorical combination at half threshold.
    The class ``primitive`` does not exist here by design.
    """
    if not population:
        return {"class": "novel", "nearest_distance": None,
                "primitive_claim_unverified": claims_primitive}
    distances = [genotype_distance(child, member) for member in population]
    nearest = min(distances)
    if nearest == 0.0:
        label = "duplicate"
    elif nearest >= threshold:
        label = "novel"
    else:
        categorical = ["planner", "algorithm", "representation",
                       "learning", "architecture", "prompt_template"]
        combos = {tuple(member[f] for f in categorical) for member in population}
        unseen_combo = tuple(child[f] for f in categorical) not in combos
        label = "novel" if (unseen_combo and nearest >= threshold / 2) else "variant"
    return {"class": label, "nearest_distance": nearest,
            "primitive_claim_unverified": claims_primitive}


class MutationEngine:
    """Bounded, deterministic proposal search over genotypes."""

    def __init__(self, *, seed: int = 0):
        self.rng = random.Random(seed)

    # ------------------------------------------------------------------
    def mutate(self, parent: dict[str, Any], mutation_class: str) -> dict[str, Any]:
        """Apply exactly one mutation class to a copy of the parent."""
        if mutation_class not in MUTATION_CLASSES:
            raise ValueError(f"unknown mutation class {mutation_class!r}")
        child = copy.deepcopy(parent)
        fields = [f for f, spec in SCHEMA.items() if spec[2] == mutation_class]
        field = self.rng.choice(fields)
        kind, spec, _cls = SCHEMA[field]
        if kind == "enum":
            choices = [v for v in spec if v != child[field]]
            child[field] = self.rng.choice(choices)
        elif kind == "toolset":
            tools = list(child[field])
            universe = list(spec)
            if len(tools) < len(universe) and (len(tools) == 1 or self.rng.random() < 0.5):
                tools.append(self.rng.choice([t for t in universe if t not in tools]))
            else:
                tools.remove(self.rng.choice(tools))
            child[field] = sorted(tools)
        elif kind == "numeric":
            low, high, eps = spec
            step = (high - low) / 8 * self.rng.choice([-1, 1])
            value = min(high, max(low, float(child[field]) + step))
            if field == "max_tokens" or field == "max_attempts":
                value = int(round(value))
            child[field] = value
        return child

    def recombine(self, parent_a: dict[str, Any],
                  parent_b: dict[str, Any]) -> dict[str, Any]:
        """Uniform crossover: every field comes from one parent or the other."""
        return {field: copy.deepcopy(
            parent_a[field] if self.rng.random() < 0.5 else parent_b[field])
            for field in SCHEMA}

    # ------------------------------------------------------------------
    def propose(self, parents: list[dict[str, Any]], *, budget: int,
                population: list[dict[str, Any]] | None = None,
                claims_primitive: bool = False) -> dict[str, Any]:
        """Propose up to ``budget`` children; return admitted + rejected.

        ``population`` is the known-genotype set used for novelty and
        duplicate checks (the parents are always included in it).
        Rejected proposals are negative results and are returned, with
        reasons — never dropped.
        """
        known = list(population or []) + list(parents)
        admitted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        attempts = 0
        while len(admitted) + len(rejected) < budget and attempts < budget * 4:
            attempts += 1
            parent = self.rng.choice(parents)
            if len(parents) >= 2 and self.rng.random() < 0.3:
                other = self.rng.choice(parents)
                child = self.recombine(parent, other)
                parent_ids = sorted({genotype_digest(parent), genotype_digest(other)})
                mutation_class = "recombination"
            else:
                mutation_class = self.rng.choice(MUTATION_CLASSES)
                child = self.mutate(parent, mutation_class)
                parent_ids = [genotype_digest(parent)]
            proposal = {
                "genotype": child,
                "digest": genotype_digest(child),
                "parents": parent_ids,
                "mutation_class": mutation_class,
                "diff_from_first_parent": field_diff(parent, child),
            }
            errors = validate_genotype(child)
            if errors:
                proposal["rejection_reasons"] = errors
                rejected.append(proposal)
                continue
            novelty = classify_novelty(child, known + [p["genotype"] for p in admitted],
                                       claims_primitive=claims_primitive)
            proposal["novelty"] = novelty
            if novelty["class"] == "duplicate":
                proposal["rejection_reasons"] = ["duplicate of a known genotype"]
                rejected.append(proposal)
                continue
            admitted.append(proposal)
        return {"admitted": admitted, "rejected": rejected, "attempts": attempts}

    # ------------------------------------------------------------------
    @staticmethod
    def verify_invariants(parent: dict[str, Any], child: dict[str, Any],
                          mutation_class: str,
                          other_parent: dict[str, Any] | None = None) -> bool:
        """Regression preservation check.

        For a mutation: the child may differ from the parent only inside
        the mutation class's own field group. For recombination: every
        child field must come from one of the two parents.
        """
        if mutation_class == "recombination":
            if other_parent is None:
                return False
            return all(child[f] == parent[f] or child[f] == other_parent[f]
                       for f in SCHEMA)
        touched = set(field_diff(parent, child))
        allowed = {f for f, spec in SCHEMA.items() if spec[2] == mutation_class}
        return touched <= allowed
