"""Rekonstruksi pembelaan lawan dari jalur bukti terkuat yang dinyatakan.

Steelman mengambil posisi yang menyerang klaim sasaran. Bobot terlemah di
jalur membatasi kontribusi keluarga sumber, dan satu keluarga menyumbang
paling banyak sekali. Keluaran memuat kutipan dan rantai asli, sehingga
penguatan tidak menambahkan klaim tanpa dasar.
"""
from collections import defaultdict, deque
from fractions import Fraction
import heapq
import json
from pathlib import Path

from .argument_graph import ArgumentGraph
from .evidence_weigher import EvidenceError, _unit


MAX_INPUT_BYTES = 5_000_000
MAX_NODES = 500
MAX_EDGES = 2_000
MAX_ALTERNATIVES = 100


class SteelmanError(ValueError):
    """Katalog graf, bukti, atau bobot belum memadai untuk pembelaan."""


def _shape(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise SteelmanError("Field steelman tidak sesuai skema.")


def _token(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 96 or "\0" in value:
        raise SteelmanError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise SteelmanError(f"{label} bukan teks UTF-8 yang sah.") from exc
    return value.strip()


def _exact(number):
    return {"numerator": number.numerator, "denominator": number.denominator}


def _weight(value):
    try:
        return _unit(value)
    except EvidenceError as exc:
        raise SteelmanError("Bobot sisi dan reliabilitas wajib desimal 0–1.") from exc


def _strengths(raw, edges):
    if not isinstance(raw, list) or len(raw) != len(edges):
        raise SteelmanError("Setiap sisi graf memerlukan satu bobot.")
    result = {}
    for row in raw:
        _shape(row, ("source", "target", "relation", "strength"))
        key = tuple(_token(row[part], part) for part in ("source", "target", "relation"))
        if key not in edges or key in result:
            raise SteelmanError("Bobot merujuk sisi asing atau ganda.")
        result[key] = _weight(row["strength"])
    return result


def _sources(raw, evidence_ids):
    if not isinstance(raw, list) or len(raw) != len(evidence_ids):
        raise SteelmanError("Setiap simpul bukti memerlukan keluarga dan reliabilitas.")
    result = {}
    for row in raw:
        _shape(row, ("id", "family", "reliability"))
        node_id = _token(row["id"], "ID bukti")
        if node_id not in evidence_ids or node_id in result:
            raise SteelmanError("Reliabilitas merujuk bukti asing atau ganda.")
        result[node_id] = (_token(row["family"], "keluarga"), _weight(row["reliability"]))
    return result


def _capacities(inbound, target):
    """Hitung kekuatan bottleneck teratas dari setiap simpul ke posisi lawan."""
    capacities = {target: Fraction(1)}
    queue = [(-Fraction(1), target)]
    while queue:
        negative, node = heapq.heappop(queue)
        capacity = -negative
        if capacity != capacities[node]:
            continue
        for source, weight, _ in inbound[node]:
            candidate = min(capacity, weight)
            if candidate > capacities.get(source, 0):
                capacities[source] = candidate
                heapq.heappush(queue, (-candidate, source))
    return capacities


def _shortest_at_strength(outbound, start, end, threshold):
    """Pilih jalur terpendek di antara semua jalur yang mencapai kekuatan itu."""
    parents = {start: None}
    queue = deque([start])
    while queue and end not in parents:
        node = queue.popleft()
        for target, weight, edge in outbound[node]:
            if weight >= threshold and target not in parents:
                parents[target] = edge
                queue.append(target)
    if end not in parents:
        raise SteelmanError("Jalur bukti yang dipilih tidak dapat diperiksa.")
    result = []
    while (edge := parents[end]) is not None:
        result.append(edge.copy())
        end = edge["source"]
    return result[::-1]


def reconstruct(raw):
    """Keluarkan posisi lawan terbaik dan dossier bukti relatif ke bobot masukan."""
    _shape(raw, ("graph", "target_claim", "strengths", "sources", "max_families"))
    source_graph = raw["graph"]
    _shape(source_graph, ("nodes", "edges"))
    if (not isinstance(source_graph["nodes"], list) or len(source_graph["nodes"]) > MAX_NODES
            or not isinstance(source_graph["edges"], list) or len(source_graph["edges"]) > MAX_EDGES):
        raise SteelmanError("Graf steelman melampaui batas.")
    graph = ArgumentGraph(source_graph).report()
    nodes = {node["id"]: node for node in graph["nodes"]}
    target = _token(raw["target_claim"], "klaim sasaran")
    if target not in nodes or nodes[target]["kind"] != "claim":
        raise SteelmanError("Sasaran harus sebuah klaim.")
    limit = raw["max_families"]
    if type(limit) is not int or not 1 <= limit <= 30:
        raise SteelmanError("max_families wajib 1–30.")

    keys = {(edge["source"], edge["target"], edge["relation"]): edge for edge in graph["edges"]}
    strengths = _strengths(raw["strengths"], keys)
    sources = _sources(raw["sources"], {key for key, node in nodes.items() if node["kind"] == "evidence"})
    inbound, outbound = defaultdict(list), defaultdict(list)
    attacks = []
    for key, edge in keys.items():
        start, end, relation = key
        weight = strengths[key]
        if relation == "supports":
            inbound[end].append((start, weight, edge))
            outbound[start].append((end, weight, edge))
        elif end == target and nodes[start]["kind"] == "claim":
            attacks.append((start, weight, edge))
    if len(attacks) > MAX_ALTERNATIVES:
        raise SteelmanError("Terlalu banyak posisi lawan.")

    ranked = []
    for claim_id, attack_weight, attack in attacks:
        capacities = _capacities(inbound, claim_id)
        by_family = {}
        for evidence_id, (family, reliability) in sorted(sources.items()):
            weight = min(reliability, capacities.get(evidence_id, 0), attack_weight)
            if weight and (family not in by_family or weight > by_family[family][0]):
                by_family[family] = (weight, evidence_id)
        ordered = [(weight, identifier, family) for family, (weight, identifier) in by_family.items()]
        ordered.sort(key=lambda item: (-item[0], item[1], item[2]))
        selected = ordered[:limit]
        score = sum((weight for weight, _, _ in selected), Fraction(0))
        ranked.append((score, claim_id, attack.copy(), selected))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    alternatives = []
    for score, claim_id, attack, selected in ranked:
        evidence = [
            {"node": nodes[identifier].copy(), "source_family": family, "strength": _exact(weight),
             "support_path": _shortest_at_strength(outbound, identifier, claim_id, weight)}
            for weight, identifier, family in selected
        ]
        alternatives.append({"position": nodes[claim_id].copy(), "attack": attack,
                             "score": _exact(score), "evidence": evidence})
    best = alternatives[0]["position"]["id"] if alternatives and alternatives[0]["evidence"] else None
    return {"schema": "ace.steelman-generator.v1", "target": nodes[target].copy(),
            "best_supported_opposition": best, "alternatives": alternatives,
            "status": "reconstructed" if best is not None else "no_supported_opposition"}


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            data = handle.read(MAX_INPUT_BYTES + 1)
        if len(data) > MAX_INPUT_BYTES:
            raise SteelmanError("Berkas steelman melebihi batas.")
        report = reconstruct(json.loads(data))
        print(json.dumps(report, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
