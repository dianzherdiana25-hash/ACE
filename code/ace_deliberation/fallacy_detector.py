"""Tunjukkan countermodel bagi bentuk inferensi yang bisa diperiksa mekanis.

Pernyataan harus sudah dinyatakan sebagai formula proposisional. Pemeriksa
tidak menebak makna prosa atau niat penulis. Countermodel memperlihatkan
mengapa premis yang benar masih dapat mendampingi kesimpulan yang salah.
"""
from dataclasses import dataclass
from itertools import product
import json
from pathlib import Path
import re


MAX_ATOMS = 10
MAX_PREMISES = 24
MAX_NODES = 96
MAX_DEPTH = 16
MAX_BYTES = 1_000_000
_ATOM = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,39}")
_ARITY = {"not": (1, 1), "and": (2, 8), "or": (2, 8), "implies": (2, 2)}


class FormulaError(ValueError):
    """Formula tidak dapat dihitung dalam model logika yang didukung."""


@dataclass(frozen=True, slots=True)
class Formula:
    op: str
    args: tuple = ()
    atom: str = ""

    def value(self, assignment):
        if self.op == "atom":
            return assignment[self.atom]
        if self.op == "not":
            return not self.args[0].value(assignment)
        if self.op == "and":
            return all(child.value(assignment) for child in self.args)
        if self.op == "or":
            return any(child.value(assignment) for child in self.args)
        antecedent, consequent = self.args
        return not antecedent.value(assignment) or consequent.value(assignment)


class _Parser:
    def __init__(self):
        self.atoms = set()
        self.nodes = 0

    def formula(self, raw, *, depth=1):
        self.nodes += 1
        if depth > MAX_DEPTH or self.nodes > MAX_NODES or not isinstance(raw, dict):
            raise FormulaError("Formula melampaui batas atau bukan objek.")
        if raw.keys() == {"atom"}:
            atom = raw["atom"]
            if not isinstance(atom, str) or not _ATOM.fullmatch(atom):
                raise FormulaError("Nama atom tidak sah.")
            self.atoms.add(atom)
            if len(self.atoms) > MAX_ATOMS:
                raise FormulaError(f"Formula memakai lebih dari {MAX_ATOMS} atom.")
            return Formula("atom", atom=atom)
        if raw.keys() != {"op", "args"} or not isinstance(raw["op"], str) or raw["op"] not in _ARITY:
            raise FormulaError("Operator formula tidak dikenal.")
        operation = raw["op"]
        needed, allowed = _ARITY[operation]
        if not isinstance(raw["args"], list) or not needed <= len(raw["args"]) <= allowed:
            raise FormulaError("Jumlah argumen formula tidak sesuai operator.")
        return Formula(operation, tuple(self.formula(child, depth=depth + 1) for child in raw["args"]))


def _ref(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 512 or "\0" in value:
        raise FormulaError("Formula perlu rujukan sumber.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise FormulaError("Rujukan formula bukan teks UTF-8 yang sah.") from exc
    return value.strip()


def _parse_entry(raw, parser):
    if not isinstance(raw, dict) or raw.keys() != {"formula", "source_ref"}:
        raise FormulaError("Entri harus memiliki formula dan source_ref.")
    return parser.formula(raw["formula"]), _ref(raw["source_ref"])


def _truth_table(premises, conclusion, atoms):
    satisfying = 0
    counterexample = None
    counterexample_count = 0
    pivotal = {}
    for values in product((False, True), repeat=len(atoms)):
        model = dict(zip(atoms, values))
        failing = [ref for formula, ref in premises if not formula.value(model)]
        if not failing:
            satisfying += 1
        if conclusion.value(model):
            continue
        if not failing:
            counterexample_count += 1
            if counterexample is None:
                counterexample = model
        elif len(failing) == 1:
            pivotal.setdefault(failing[0], model)
    return satisfying, counterexample, counterexample_count, pivotal


def _named_patterns(premises, conclusion):
    refs = {}
    for formula, ref in premises:
        refs.setdefault(formula, []).append(ref)
    found = []
    for formula, primary in premises:
        if formula.op == "implies":
            antecedent, consequent = formula.args
            if conclusion == antecedent:
                for secondary in refs.get(consequent, ()):
                    found.append(("affirming_consequent", primary, secondary))
            if conclusion == Formula("not", (consequent,)):
                for secondary in refs.get(Formula("not", (antecedent,)), ()):
                    found.append(("denying_antecedent", primary, secondary))
        elif formula.op == "or" and len(formula.args) == 2:
            left, right = formula.args
            for asserted, denied in ((left, right), (right, left)):
                if conclusion == Formula("not", (denied,)):
                    for secondary in refs.get(asserted, ()):
                        found.append(("affirming_inclusive_disjunct", primary, secondary))
    return [{"code": code, "premise_refs": [first, second]}
            for code, first, second in sorted(set(found))]


def inspect_argument(raw):
    if not isinstance(raw, dict) or raw.keys() != {"premises", "conclusion"}:
        raise FormulaError("Argumen perlu premises dan conclusion.")
    if not isinstance(raw["premises"], list) or not 1 <= len(raw["premises"]) <= MAX_PREMISES:
        raise FormulaError("Premis wajib berupa daftar berbatas.")
    parser = _Parser()
    premises = [_parse_entry(item, parser) for item in raw["premises"]]
    conclusion, conclusion_ref = _parse_entry(raw["conclusion"], parser)
    refs = sorted(ref for _, ref in premises)
    if len(set(refs)) != len(refs) or conclusion_ref in refs:
        raise FormulaError("Rujukan formula harus terpisah.")
    atoms = sorted(parser.atoms)
    satisfying, counterexample, bad_count, pivotal = _truth_table(premises, conclusion, atoms)
    findings = []
    if not satisfying:
        status = "inconsistent_premises"
    elif counterexample is None:
        status = "entailed"
    else:
        status = "counterexample"
        findings.extend(_named_patterns(premises, conclusion))
    duplicate_refs = sorted(ref for formula, ref in premises if formula == conclusion)
    if duplicate_refs:
        findings.append({"code": "conclusion_restated_as_premise", "premise_refs": duplicate_refs})
    return {
        "schema": "ace.fallacy-detector.v1", "status": status, "candidate_atoms": atoms,
        "model_count": 2**len(atoms), "premise_satisfying_count": satisfying,
        "counterexample_count": bad_count, "first_counterexample": counterexample,
        "premise_refs": refs, "conclusion_ref": conclusion_ref, "findings": findings,
        "premise_necessity_witnesses": [
            {"omitted_ref": ref, "counterexample": model} for ref, model in sorted(pivotal.items())
        ] if status == "entailed" else [],
    }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("argument", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.argument.open("rb") as stream:
            payload = stream.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise FormulaError("Berkas argumen melampaui batas.")
        report = inspect_argument(json.loads(payload))
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(report["status"] != "entailed" or bool(report["findings"]))


if __name__ == "__main__":
    raise SystemExit(main())
