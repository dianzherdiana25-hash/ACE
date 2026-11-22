"""Petakan aktor dan relasi yang ditunjuk bukti, dengan dukungan per dokumen."""
from collections import defaultdict, deque
import re

from ._contracts import ResearchError, anchor, cli, identifier, integer, items, obj, schema, source_bytes, text


def _contains(line, alias):
    return re.search(r"(?<!\w)" + re.escape(alias.casefold()) + r"(?!\w)", line.casefold()) is not None


def map_actors(plan, expected, root):
    anchor(plan, expected)
    schema(plan, "ace.institute.actor-plan.v1", ("actors", "documents", "relations", "reach_from"))
    actors = {}
    for row in items(plan["actors"], 200, 1):
        obj(row, ("id", "name", "role", "source_ref", "aliases"))
        key = identifier(row["id"], "Aktor")
        if key in actors:
            raise ResearchError("Aktor ganda.")
        name = text(row["name"], "Nama aktor")
        terms = {name, *(text(alias, "Alias aktor", 100) for alias in items(row["aliases"], 15))}
        actors[key] = {"name": name, "role": identifier(row["role"], "Tipe aktor"),
                       "source_ref": text(row["source_ref"], "Pointer aktor"), "aliases": terms}
    documents = {}
    byte_count = 0
    for row in items(plan["documents"], 80, 1):
        obj(row, ("id", "path", "sha256"))
        key = identifier(row["id"], "Dokumen relasi")
        if key in documents:
            raise ResearchError("ID dokumen ganda.")
        raw = source_bytes(root, row["path"], row["sha256"], 300000)
        byte_count += len(raw)
        if byte_count > 4_000_000:
            raise ResearchError("Anggaran bukti relasi terlampaui.")
        documents[key] = (row, raw.decode("utf-8").splitlines())
    edges = defaultdict(dict)
    outgoing = defaultdict(set)
    incoming = defaultdict(set)
    for row in items(plan["relations"], 2000):
        obj(row, ("from", "to", "kind", "document", "line"))
        left, right, doc = [identifier(row[key], key) for key in ("from", "to", "document")]
        kind = identifier(row["kind"], "Tipe relasi")
        if left == right or left not in actors or right not in actors or doc not in documents:
            raise ResearchError("Relasi menunjuk aktor atau dokumen tak dikenal.")
        pointer, body = documents[doc]
        line = integer(row["line"], "Baris relasi", 1, len(body))
        if not all(any(_contains(body[line - 1], alias) for alias in actors[key]["aliases"]) for key in (left, right)):
            raise ResearchError("Baris sumber relasi tidak menyebut kedua aktor.")
        edges[(left, right, kind)][(pointer["sha256"], line)] = {**pointer, "line": line}
        outgoing[left].add(right)
        incoming[right].add(left)
    focus = identifier(plan["reach_from"], "Aktor awal")
    if focus not in actors:
        raise ResearchError("Aktor awal tidak terdaftar.")
    steps = {focus: 0}
    search = deque([focus])
    while search:
        current = search.popleft()
        for destination in sorted(outgoing[current]):
            if destination not in steps:
                search.append(destination)
                steps[destination] = steps[current] + 1
    return {"schema": "ace.institute.actor-map.v1", "plan_sha256": expected, "scope": "annotated_document_relations",
            "actors": [{"id": key, **{name: actors[key][name] for name in ("name", "role", "source_ref")},
                        "incoming": len(incoming[key]), "outgoing": len(outgoing[key]), "distance_from_focus": steps.get(key)}
                       for key in sorted(actors)],
            "edges": [{"from": left, "to": right, "kind": kind, "evidence": [refs[key] for key in sorted(refs)],
                       "distinct_document_hashes": len({key[0] for key in refs})}
                      for (left, right, kind), refs in sorted(edges.items())]}


if __name__ == "__main__":
    raise SystemExit(cli(map_actors, __doc__, rooted=True))
