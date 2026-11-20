"""Sintesiskan posisi dari serangan dan jejak dukungan dalam graf argumen.

Pelabelan grounded membedakan argumen diterima, ditolak, dan belum terurai.
Hanya bukti yang rujukannya diakui pemanggil ikut graf aktif. Seleksi
memerlukan jejak dukungan dalam subgraf yang diterima, dan seri tetap
menjadi alasan menunda rekomendasi.
"""
from collections import defaultdict, deque
import json
from pathlib import Path

from .argument_graph import ArgumentGraph, MAX_INPUT_BYTES


MAX_CHOICES = 150


class SynthesisError(ValueError):
    """Graf atau ketentuan sintesis tidak dapat diperiksa."""


def _shape(value, keys):
    if not isinstance(value, dict) or value.keys() != set(keys):
        raise SynthesisError("Field sintesis tidak sesuai skema.")


def _label(value, limit=512):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise SynthesisError("Rujukan sintesis tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise SynthesisError("Rujukan sintesis bukan teks UTF-8.") from exc
    return value.strip()


def _labels(raw, minimum, maximum):
    if not isinstance(raw, list) or not minimum <= len(raw) <= maximum:
        raise SynthesisError("Jumlah rujukan sintesis di luar batas.")
    labels = [_label(value) for value in raw]
    if len(set(labels)) != len(labels):
        raise SynthesisError("Rujukan sintesis ganda.")
    return set(labels)


def _grounded(active, attacks):
    attackers = {key: set() for key in active}
    targets = defaultdict(set)
    for edge in attacks:
        source, target = edge["source"], edge["target"]
        attackers[target].add(source)
        targets[source].add(target)
    labels = dict.fromkeys(active, "undecided")
    remaining = {key: len(sources) for key, sources in attackers.items()}
    layers = []
    next_in = {key for key, count in remaining.items() if not count}
    while next_in:
        accepted = sorted(key for key in next_in if labels[key] == "undecided")
        rejected = set()
        for key in accepted:
            labels[key] = "accepted"
        for key in accepted:
            for target in targets[key]:
                if labels[target] == "undecided":
                    labels[target] = "rejected"
                    rejected.add(target)
        next_in = set()
        for key in sorted(rejected):
            for target in targets[key]:
                remaining[target] -= 1
                if labels[target] == "undecided" and not remaining[target]:
                    next_in.add(target)
        layers.append({"accepted": accepted, "rejected": sorted(rejected)})
    return labels, layers, attackers


def _evidence_for(roots, key, nodes, statuses):
    found = {}
    visited = {key}
    path_to = {key: None}
    pending = deque([key])
    while pending:
        target = pending.popleft()
        for relation in roots[target]:
            start = relation["source"]
            if statuses.get(start) != "accepted" or start in visited:
                continue
            path_to[start] = relation
            visited.add(start)
            pending.append(start)
            if nodes[start]["kind"] != "evidence":
                continue
            origin = start
            chain = []
            while (edge := path_to[origin]) is not None:
                chain.append(edge.copy())
                origin = edge["target"]
            source = nodes[start]["source_ref"]
            if source not in found:
                found[source] = {"evidence_id": start, "source_ref": source, "support_path": chain}
    return [found[ref] for ref in sorted(found)]


def synthesize(raw):
    _shape(raw, ("graph", "choices", "recognized_evidence_refs", "min_support_refs"))
    graph = ArgumentGraph(raw["graph"]).report()
    nodes = {row["id"]: row for row in graph["nodes"]}
    choices = _labels(raw["choices"], 2, MAX_CHOICES)
    if any(key not in nodes or nodes[key]["kind"] != "claim" for key in choices):
        raise SynthesisError("Pilihan sintesis harus menunjuk klaim.")
    support_minimum = raw["min_support_refs"]
    if type(support_minimum) is not int or not 1 <= support_minimum <= len(nodes):
        raise SynthesisError("min_support_refs di luar batas.")
    recognized = _labels(raw["recognized_evidence_refs"], 0, len(nodes))
    actual = {row["source_ref"] for row in nodes.values() if row["kind"] == "evidence"}
    if recognized - actual:
        raise SynthesisError("Rujukan bukti terdaftar tidak ada pada graf.")
    active = {key for key, row in nodes.items()
              if row["kind"] == "claim" or row["source_ref"] in recognized}
    attacks = [edge for edge in graph["edges"] if edge["relation"] == "attacks" and edge["source"] in active]
    labels, layers, attackers = _grounded(active, attacks)
    roots = defaultdict(list)
    for edge in graph["edges"]:
        if edge["relation"] == "supports":
            roots[edge["target"]].append(edge)
    decisions = []
    renderable = []
    for key in sorted(choices):
        labels_for = labels[key]
        relevant = _evidence_for(roots, key, nodes, labels) if labels_for == "accepted" else []
        has_support = labels_for == "accepted" and len(relevant) >= support_minimum
        decisions.append({
            "claim": nodes[key].copy(), "grounded_status": labels_for,
            "accepted_support": relevant, "meets_support_threshold": has_support,
            "attackers": [{"id": source, "status": labels[source]} for source in sorted(attackers[key])],
        })
        if has_support:
            renderable.append((len(relevant), key))

    renderable.sort(key=lambda pair: (-pair[0], pair[1]))
    chosen = None
    if renderable:
        if len(renderable) == 1 or renderable[0][0] != renderable[1][0]:
            chosen = renderable[0][1]
    return {
        "schema": "ace.synthesis-engine.v1", "status": ("recommendation" if chosen else "defer"),
        "reason": ("best_supported" if chosen else "tie" if renderable else "insufficient_accepted_support"),
        "recommended_choice": chosen, "positions": decisions, "grounded_layers": layers,
        "grounded_status": dict(sorted(labels.items())), "unrecognized_evidence_refs": sorted(actual - recognized),
    }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            blob = handle.read(MAX_INPUT_BYTES + 1)
        if len(blob) > MAX_INPUT_BYTES:
            raise SynthesisError("Berkas sintesis melampaui batas.")
        print(json.dumps(synthesize(json.loads(blob)), ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
