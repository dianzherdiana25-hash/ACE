"""Bangun distribusi skenario dari kondisi bercabang yang sumbernya dicatat.

Setiap simpul internal menetapkan distribusi bersyarat eksak. Mengamati
cabang berarti jalur tersebut benar-benar dilewati. Ketika tidak ada jalur
dengan massa positif yang memenuhi pengamatan, keluaran menyatakan
pengamatan mustahil dan menahan payoff bersyarat.
"""
from collections import Counter
from fractions import Fraction
import json
from pathlib import Path

from .brier_scorer import _rational


MAX_NODES = 1_024
MAX_CHILDREN = 20
MAX_DEPTH = 24
MAX_BYTES = 4_000_000


class ScenarioError(ValueError):
    """Pohon skenario, peluang, atau pengamatan tidak sah."""


def _shape(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise ScenarioError("Field skenario tidak sesuai skema.")


def _text(value, label, maximum=128):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\0" in value:
        raise ScenarioError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ScenarioError(f"{label} bukan teks UTF-8.") from exc
    return value.strip()


def _probability(raw):
    _shape(raw, ("numerator", "denominator"))
    a, b = raw["numerator"], raw["denominator"]
    if type(a) is not int or type(b) is not int or not 0 <= a <= b <= 10**9 or not b:
        raise ScenarioError("Probabilitas bersyarat harus berupa pecahan antara 0 dan 1.")
    return Fraction(a, b)


def _nodes(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_NODES:
        raise ScenarioError("Jumlah simpul di luar batas.")
    output = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("kind") not in ("branch", "leaf"):
            raise ScenarioError("Jenis simpul harus branch atau leaf.")
        kind = row["kind"]
        common = ("id", "kind", "source_ref")
        _shape(row, (*common, "condition", "outcomes") if kind == "branch" else (*common, "consequence", "utility"))
        identifier, ref = _text(row["id"], "ID simpul"), _text(row["source_ref"], "rujukan simpul", 512)
        if identifier in output:
            raise ScenarioError("ID simpul ganda.")
        item = {"id": identifier, "kind": kind, "source_ref": ref}
        if kind == "leaf":
            utility = row["utility"]
            if type(utility) is not int or not -10**6 <= utility <= 10**6:
                raise ScenarioError("Utilitas simpul akhir harus integer berbatas.")
            item.update(consequence=_text(row["consequence"], "konsekuensi", 4_000), utility=utility)
        else:
            item["condition"] = _text(row["condition"], "kondisi", 4_000)
            outcomes = row["outcomes"]
            if not isinstance(outcomes, list) or not 2 <= len(outcomes) <= MAX_CHILDREN:
                raise ScenarioError("Cabang perlu 2–20 kejadian.")
            entries = {}
            for option in outcomes:
                _shape(option, ("label", "target", "probability", "source_ref"))
                label = _text(option["label"], "label kejadian")
                if label in entries:
                    raise ScenarioError("Label kejadian ganda.")
                entries[label] = {
                    "label": label, "target": _text(option["target"], "simpul tujuan"),
                    "probability": _probability(option["probability"]),
                    "source_ref": _text(option["source_ref"], "rujukan kejadian", 512),
                }
            if sum(entry["probability"] for entry in entries.values()) != 1:
                raise ScenarioError("Peluang semua cabang pada satu kondisi harus berjumlah 1.")
            item["outcomes"] = entries
        output[identifier] = item
    return output


def _paths(root, nodes):
    if root not in nodes:
        raise ScenarioError("Simpul akar tidak ditemukan.")
    children = [item["target"] for node in nodes.values() if node["kind"] == "branch"
                for item in node["outcomes"].values()]
    count = Counter(children)
    if any(node not in nodes for node in count) or root in count:
        raise ScenarioError("Pohon menunjuk simpul asing atau kembali ke akar.")
    if any(value != 1 for value in count.values()):
        raise ScenarioError("Simpul memiliki lebih dari satu induk.")
    seen = set()
    stack = [(root, Fraction(1), ())]
    end_states = []
    while stack:
        identifier, probability, path = stack.pop()
        if identifier in seen or len(path) > MAX_DEPTH:
            raise ScenarioError("Pohon melingkar atau melampaui kedalaman.")
        seen.add(identifier)
        node = nodes[identifier]
        if node["kind"] == "leaf":
            end_states.append((node, probability, path))
            continue
        for label, outcome in sorted(node["outcomes"].items(), reverse=True):
            move = {"from": identifier, "condition": node["condition"], "condition_ref": node["source_ref"],
                    "label": label, "to": outcome["target"], "source_ref": outcome["source_ref"],
                    "conditional_at_node": _rational(outcome["probability"])}
            stack.append((outcome["target"], probability * outcome["probability"], (*path, move)))
    if set(nodes) != seen:
        raise ScenarioError("Ada simpul yang tidak dapat dicapai dari akar.")
    return end_states


def generate(raw):
    _shape(raw, ("root", "nodes", "observations"))
    nodes = _nodes(raw["nodes"])
    root = _text(raw["root"], "akar")
    observations = raw["observations"]
    if not isinstance(observations, dict) or len(observations) > MAX_DEPTH:
        raise ScenarioError("Pengamatan harus berupa peta cabang berbatas.")
    observed = {}
    for key, value in observations.items():
        index, label = _text(key, "ID pengamatan"), _text(value, "label pengamatan")
        if (index not in nodes or nodes[index]["kind"] != "branch"
                or label not in nodes[index]["outcomes"] or index in observed):
            raise ScenarioError("Pengamatan tidak menunjuk cabang unik.")
        observed[index] = label
    outcomes = []
    retained = []
    for node, probability, path in _paths(root, nodes):
        visited = {step["from"]: step["label"] for step in path}
        matches = all(visited.get(identifier) == label for identifier, label in observed.items())
        retained.append(probability if matches else Fraction(0))
        outcomes.append({"leaf": node, "path": list(path), "prior_probability": _rational(probability),
                         "consistent_with_observations": matches, "posterior_probability": None})
    mass = sum(retained, Fraction(0))
    utility = None
    distribution = {}
    if mass:
        utility = Fraction(0)
        for row, probability in zip(outcomes, retained):
            posterior = probability / mass
            row["posterior_probability"] = _rational(posterior)
            value = row["leaf"]["utility"]
            utility += posterior * value
            if posterior:
                distribution[value] = distribution.get(value, Fraction(0)) + posterior
    return {"schema": "ace.scenario-generator.v1", "root": root, "observations": dict(sorted(observed.items())),
            "status": "evaluated" if mass else "impossible_observations",
            "observation_mass": _rational(mass), "expected_utility": _rational(utility) if utility is not None else None,
            "utility_distribution": [{"utility": value, "probability": _rational(probability)}
                                     for value, probability in sorted(distribution.items())],
            "outcomes": outcomes}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ScenarioError("Berkas skenario melampaui batas.")
        result = generate(json.loads(data))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] == "impossible_observations")


if __name__ == "__main__":
    raise SystemExit(main())
