"""Pisahkan struktur argumen dari putusan agar dukungan dan serangan terlacak.

Graf menerima klaim, bukti, dan sisi berprovenance. Komponen kuat dan jalur
terpendek dicatat eksplisit, termasuk ketika penalaran berputar. Tanda sisi
menjelaskan hubungan yang dideklarasikan dan tidak menetapkan kebenaran klaim.
"""
from collections import deque
from dataclasses import dataclass
import json
from pathlib import Path


MAX_NODES = 2_000
MAX_EDGES = 12_000
MAX_INPUT_BYTES = 5_000_000
RELATIONS = frozenset({"supports", "attacks"})


class GraphError(ValueError):
    """Graf masukan tidak mendefinisikan hubungan yang sah."""


def _string(value, field, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\0" in value:
        raise GraphError(f"{field} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise GraphError(f"{field} bukan teks UTF-8 yang sah.") from exc
    return value.strip()


def _shape(raw, fields):
    if not isinstance(raw, dict) or raw.keys() != set(fields):
        raise GraphError("Field masukan tidak sesuai skema.")


@dataclass(frozen=True, slots=True)
class Node:
    id: str
    kind: str
    text: str
    source_ref: str

    @classmethod
    def from_dict(cls, raw):
        _shape(raw, ("id", "kind", "text", "source_ref"))
        if raw["kind"] not in ("claim", "evidence"):
            raise GraphError("Jenis simpul hanya claim atau evidence.")
        return cls(_string(raw["id"], "id", 96), raw["kind"],
                   _string(raw["text"], "text", 8_000),
                   _string(raw["source_ref"], "source_ref", 512))

    def as_dict(self):
        return {"id": self.id, "kind": self.kind, "text": self.text, "source_ref": self.source_ref}


@dataclass(frozen=True, slots=True, order=True)
class Edge:
    source: str
    target: str
    relation: str
    source_ref: str

    @classmethod
    def from_dict(cls, raw):
        _shape(raw, ("source", "target", "relation", "source_ref"))
        if raw["relation"] not in ("supports", "attacks"):
            raise GraphError("Jenis sisi hanya supports atau attacks.")
        return cls(_string(raw["source"], "source", 96), _string(raw["target"], "target", 96),
                   raw["relation"], _string(raw["source_ref"], "source_ref", 512))

    def as_dict(self):
        return {"source": self.source, "target": self.target, "relation": self.relation,
                "source_ref": self.source_ref}


class ArgumentGraph:
    """Simpan satu graf snapshot dan jelajahi jalurnya secara deterministik."""

    def __init__(self, raw):
        _shape(raw, ("nodes", "edges"))
        if not isinstance(raw["nodes"], list) or not 1 <= len(raw["nodes"]) <= MAX_NODES:
            raise GraphError(f"Graf memerlukan 1–{MAX_NODES} simpul.")
        if not isinstance(raw["edges"], list) or len(raw["edges"]) > MAX_EDGES:
            raise GraphError(f"Graf menerima hingga {MAX_EDGES} sisi.")
        nodes = [Node.from_dict(row) for row in raw["nodes"]]
        self._nodes = {node.id: node for node in nodes}
        if len(self._nodes) != len(nodes):
            raise GraphError("ID simpul ganda.")
        self._keys = tuple(sorted(self._nodes))
        self._edges = tuple(sorted(Edge.from_dict(row) for row in raw["edges"]))
        self._inbound = {identifier: [] for identifier in self._keys}
        self._outbound = {identifier: [] for identifier in self._keys}
        seen = set()
        for edge in self._edges:
            key = (edge.source, edge.target, edge.relation)
            if key in seen:
                raise GraphError("Sisi berjenis sama untuk pasangan ini sudah ada.")
            if edge.source not in self._nodes or edge.target not in self._nodes:
                raise GraphError("Sisi memiliki rujukan simpul yang tidak ada.")
            if edge.source == edge.target or self._nodes[edge.target].kind != "claim":
                raise GraphError("Sisi harus mengarah ke klaim lain.")
            self._inbound[edge.target].append(edge)
            self._outbound[edge.source].append(edge)
            seen.add(key)

    def _node(self, identifier):
        if not isinstance(identifier, str) or identifier not in self._nodes:
            raise GraphError("Simpul tidak ditemukan.")
        return self._nodes[identifier]

    @staticmethod
    def _relations(relations):
        if relations is None:
            return RELATIONS
        if (not isinstance(relations, (tuple, list, set, frozenset))
                or any(not isinstance(item, str) or item not in RELATIONS for item in relations)):
            raise GraphError("Filter jenis sisi tidak sah.")
        return frozenset(relations)

    def incoming(self, identifier, *, relations=None):
        self._node(identifier)
        allowed = self._relations(relations)
        return [edge.as_dict() for edge in self._inbound[identifier] if edge.relation in allowed]

    def shortest_path(self, source, target, *, relations=None):
        """Kembalikan sisi jalur terpendek berdasarkan arah deklarasi."""
        self._node(source)
        self._node(target)
        allowed = self._relations(relations)
        queue = deque([source])
        traversed = {source: None}
        while queue and target not in traversed:
            for edge in self._outbound[queue.popleft()]:
                if edge.relation in allowed and edge.target not in traversed:
                    traversed[edge.target] = edge
                    queue.append(edge.target)
        if target not in traversed:
            return None
        path = []
        while (edge := traversed[target]) is not None:
            path.append(edge.as_dict())
            target = edge.source
        path.reverse()
        return path

    def strongly_connected(self, *, relations=None):
        """Kosaraju iteratif agar panjang rantai masukan tak bergantung pada rekursi."""
        allowed = self._relations(relations)
        ending_order = []
        searched = set()
        for root in self._keys:
            if root in searched:
                continue
            searched.add(root)
            descend = [(root, iter(self._outbound[root]))]
            while descend:
                top, edges = descend[-1]
                edge = next(edges, None)
                if edge is None:
                    ending_order.append(top)
                    descend.pop()
                elif edge.relation in allowed and edge.target not in searched:
                    searched.add(edge.target)
                    descend.append((edge.target, iter(self._outbound[edge.target])))
        components = []
        searched.clear()
        for root in reversed(ending_order):
            if root in searched:
                continue
            pending = [root]
            searched.add(root)
            component = []
            while pending:
                node = pending.pop()
                component.append(node)
                for edge in self._inbound[node]:
                    if edge.relation in allowed and edge.source not in searched:
                        pending.append(edge.source)
                        searched.add(edge.source)
            components.append(sorted(component))
        return sorted(components)

    def report(self):
        return {
            "schema": "ace.argument-graph.v1",
            "nodes": [self._nodes[identifier].as_dict() for identifier in self._keys],
            "edges": [edge.as_dict() for edge in self._edges],
            "cycles": [component for component in self.strongly_connected() if len(component) > 1],
            "claims_without_evidence": [
                identifier for identifier in self._keys
                if self._nodes[identifier].kind == "claim" and not any(
                    self._nodes[edge.source].kind == "evidence"
                    and edge.relation == "supports" for edge in self._inbound[identifier]
                )
            ],
        }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    parser.add_argument("--path", nargs=2, metavar=("SOURCE", "TARGET"))
    parser.add_argument("--supports-only", action="store_true")
    args = parser.parse_args(argv)
    if args.supports_only and args.path is None:
        parser.error("--supports-only memerlukan --path.")
    try:
        with args.graph.open("rb") as stream:
            raw = stream.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise GraphError("Berkas graf melebihi batas.")
        graph = ArgumentGraph(json.loads(raw))
        if args.path is None:
            result = graph.report()
        else:
            relations = ("supports",) if args.supports_only else None
            result = {"source": args.path[0], "target": args.path[1],
                      "path": graph.shortest_path(*args.path, relations=relations)}
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
