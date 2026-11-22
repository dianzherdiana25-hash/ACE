"""Pecah ramalan majemuk menjadi subpertanyaan yang dapat diuji.

Tabel kebenaran menyimpan saksi untuk struktur pertanyaan bahkan ketika
asumsi probabilitas tidak tersedia. Perhitungan peluang memerlukan model
independensi eksplisit untuk variabel yang berbeda. Pengulangan satu
variabel di beberapa cabang tetap menunjuk peristiwa yang sama.
"""
from dataclasses import dataclass
from fractions import Fraction
from itertools import product

from ._advanced import InputError, json_main, probability, rows, shape, text, unique
from .brier_scorer import _rational


MAX_ATOMS = 10
MAX_NODES = 100
MAX_DEPTH = 12
OPERATORS = {"all", "any", "not"}


@dataclass(frozen=True, slots=True)
class Node:
    op: str
    operands: tuple
    variate: str | None = None

    def value(self, assignment):
        if self.variate is not None:
            return assignment[self.variate]
        if self.op == "all":
            return all(child.value(assignment) for child in self.operands)
        if self.op == "any":
            return any(child.value(assignment) for child in self.operands)
        return not self.operands[0].value(assignment)

    def export(self):
        if self.variate is not None:
            return {"atom": self.variate}
        return {"op": self.op, "children": [child.export() for child in self.operands]}


def _parse(raw, occurrences, budget, depth=0):
    if depth >= MAX_DEPTH or not budget:
        raise InputError("Pohon pertanyaan terlalu besar.")
    budget.pop()
    if isinstance(raw, dict) and raw.keys() == {"atom"}:
        name = text(raw["atom"], "subpertanyaan")
        occurrences[name] = occurrences.get(name, 0) + 1
        return Node("atom", (), name)
    shape(raw, ("op", "children"))
    op = text(raw["op"], "operator")
    if op not in OPERATORS:
        raise InputError("Operator pertanyaan tidak dikenal.")
    minimum, maximum = (1, 1) if op == "not" else (2, MAX_ATOMS)
    children = rows(raw["children"], minimum, maximum)
    return Node(op, tuple(_parse(child, occurrences, budget, depth + 1) for child in children))


@dataclass(frozen=True, slots=True)
class Atom:
    name: str
    question: str
    source: str
    estimate: Fraction | None
    forecast_ref: str | None

    @classmethod
    def read(cls, row):
        shape(row, ("id", "question", "source_ref", "probability", "forecast_ref"))
        estimate, ref = row["probability"], row["forecast_ref"]
        if (estimate is None) != (ref is None):
            raise InputError("Peluang dan rujukan ramalan harus hadir berpasangan.")
        return cls(
            text(row["id"], "ID"), text(row["question"], "pertanyaan", 2000),
            text(row["source_ref"], "sumber pertanyaan"),
            probability(estimate) if estimate is not None else None,
            text(ref, "sumber ramalan") if ref is not None else None,
        )


def _joint(assignment, atoms):
    weight = Fraction(1)
    for atom in atoms:
        weight *= atom.estimate if assignment[atom.name] else 1 - atom.estimate
    return weight


def _enumerate(root, atoms, calculate):
    table = {}
    hits = 0
    evidence = {False: None, True: None}
    likelihood = Fraction()
    for values in product((False, True), repeat=len(atoms)):
        assignment = dict(zip((atom.name for atom in atoms), values))
        outcome = root.value(assignment)
        table[values] = outcome
        hits += int(outcome)
        if evidence[outcome] is None:
            evidence[outcome] = assignment
        if calculate and outcome:
            likelihood += _joint(assignment, atoms)
    pivotal = {}
    for index, atom in enumerate(atoms):
        pivotal[atom.name] = sum(
            outcome != table[values[:index] + (True,) + values[index + 1:]]
            for values, outcome in table.items()
            if not values[index]
        )
    return hits, evidence, pivotal, likelihood


def decompose(raw):
    shape(raw, ("question_id", "question_ref", "expression", "atoms", "independence_ref"))
    identifier = text(raw["question_id"], "ID induk")
    source = text(raw["question_ref"], "sumber induk")
    model_ref = raw["independence_ref"]
    if model_ref is not None:
        model_ref = text(model_ref, "sumber asumsi")
        if source == model_ref:
            raise InputError("Sumber induk dan asumsi bertabrakan.")
    atoms, references, occurrences = {}, {source}, {}
    if model_ref is not None:
        references.add(model_ref)
    for row in rows(raw["atoms"], 1, MAX_ATOMS):
        atom = Atom.read(row)
        if atom.name == identifier or atom.name in atoms:
            raise InputError("ID subpertanyaan bertabrakan.")
        if atom.forecast_ref is not None:
            unique(atom.forecast_ref, references)
        atoms[atom.name] = atom
    root = _parse(raw["expression"], occurrences, [None] * MAX_NODES)
    unknown = sorted(occurrences.keys() - atoms.keys())
    unused = sorted(atoms.keys() - occurrences.keys())
    if unknown or unused:
        raise InputError(f"Variabel tak dikenal {unknown}; variabel tak dipakai {unused}.")
    ordered = [atoms[key] for key in sorted(atoms)]
    missing = [atom.name for atom in ordered if atom.estimate is None]
    calculated = model_ref is not None and not missing
    hits, evidence, pivotal, likelihood = _enumerate(root, ordered, calculated)
    assignments = 2 ** len(ordered)
    if hits in (0, assignments):
        status, value = "logical_constant", _rational(int(hits == assignments))
    elif calculated:
        status, value = "conditional_on_independence", _rational(likelihood)
    else:
        status, value = "missing_assumption_or_forecasts", None
    return {
        "schema": "ace.question-decomposition.v1",
        "question_id": identifier, "question_ref": source,
        "expression": root.export(), "assignments": assignments, "satisfying": hits,
        "first_true_witness": evidence[True], "first_false_witness": evidence[False],
        "probability_status": status, "probability": value,
        "independence_ref": model_ref, "missing_forecasts": missing,
        "subquestions": [
            {"id": atom.name, "question": atom.question, "source_ref": atom.source,
             "forecast_ref": atom.forecast_ref, "occurrences": occurrences[atom.name],
             "pivotal_assignments": pivotal[atom.name]}
            for atom in sorted(ordered, key=lambda item: (-pivotal[item.name], item.name))
        ],
    }


def main(argv=None):
    return json_main(argv, __doc__, decompose)


if __name__ == "__main__":
    raise SystemExit(main())
