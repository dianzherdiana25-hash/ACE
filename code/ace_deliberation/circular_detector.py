"""Bedakan putaran argumen tanpa dasar dari siklus dengan bukti mandiri.

Satu aturan memerlukan seluruh premisnya. Aturan alternatif bagi klaim
yang sama memberi jalur lain. Setelah menutup semua turunan dari fondasi
eksplisit, pemeriksa mencari komponen residual yang masih berputar dan
menghasilkan satu jejak saksi serta premis luar yang belum tersedia.
"""
from collections import Counter, defaultdict, deque
import json
from pathlib import Path

from .argument_graph import ArgumentGraph


MAX_CLAIMS = 1_000
MAX_RULES = 3_000
MAX_PREMISES = 16
MAX_EDGES = 12_000
MAX_BYTES = 7_000_000


class CircularError(ValueError):
    """Catatan fondasi atau aturan tidak dapat ditelusuri."""


def _shape(raw, keys):
    if not isinstance(raw, dict) or raw.keys() != set(keys):
        raise CircularError("Field argumen berputar tidak sesuai skema.")


def _text(value, label, maximum=96):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\0" in value:
        raise CircularError(f"{label} tidak sah.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise CircularError(f"{label} bukan teks UTF-8.") from exc
    return value.strip()


def _rows(raw, lo, hi):
    if not isinstance(raw, list) or not lo <= len(raw) <= hi:
        raise CircularError("Jumlah record kedap batas.")
    return raw


def _grounded(rules, initial):
    waiting = defaultdict(list)
    counts = Counter()
    for identifier, rule in rules.items():
        counts[identifier] = len(rule["premises"])
        for premise in rule["premises"]:
            waiting[premise].append(identifier)
    seen = {key: {"kind": "foundation", "source_ref": ref} for key, ref in sorted(initial.items())}
    queue = deque(seen)
    while queue:
        premise = queue.popleft()
        for identifier in sorted(waiting[premise]):
            counts[identifier] -= 1
            rule = rules[identifier]
            key = rule["conclusion"]
            if counts[identifier] == 0 and key not in seen:
                seen[key] = {"kind": "derived", "rule": identifier, "source_ref": rule["source_ref"],
                             "premises": rule["premises"].copy()}
                queue.append(key)
    return seen


def _witness(start, adjacency, component):
    queue = deque([start])
    history = {start: []}
    while queue:
        current = queue.popleft()
        for edge in adjacency[current]:
            target = edge["target"]
            if target not in component:
                continue
            path = [*history[current], edge]
            if target == start:
                return path
            if target not in history:
                history[target] = path
                queue.append(target)
    raise CircularError("Saksi putaran tidak terbentuk.")


def detect(raw):
    _shape(raw, ("claims", "foundations", "rules"))
    claims, refs = {}, set()
    for row in _rows(raw["claims"], 1, MAX_CLAIMS):
        _shape(row, ("id", "source_ref"))
        identifier = _text(row["id"], "klaim")
        ref = _text(row["source_ref"], "sumber klaim", 512)
        if identifier in claims or ref in refs:
            raise CircularError("Klaim atau sumber ganda.")
        claims[identifier] = ref
        refs.add(ref)
    foundations = {}
    for row in _rows(raw["foundations"], 0, len(claims)):
        _shape(row, ("id", "source_ref"))
        identifier = _text(row["id"], "fondasi")
        ref = _text(row["source_ref"], "sumber fondasi", 512)
        if identifier not in claims or identifier in foundations or ref in refs:
            raise CircularError("Fondasi ganda atau merujuk klaim asing.")
        foundations[identifier] = ref
        refs.add(ref)
    rules = {}
    for row in _rows(raw["rules"], 0, MAX_RULES):
        _shape(row, ("id", "conclusion", "premises", "source_ref"))
        identifier = _text(row["id"], "aturan")
        conclusion = _text(row["conclusion"], "kesimpulan")
        premises = sorted(_text(item, "premis") for item in _rows(row["premises"], 1, MAX_PREMISES))
        ref = _text(row["source_ref"], "sumber aturan", 512)
        if (identifier in rules or conclusion not in claims or set(premises) - claims.keys()
                or len(premises) != len(set(premises)) or ref in refs):
            raise CircularError("Aturan ganda, premis ganda, atau rujukan asing.")
        refs.add(ref)
        rules[identifier] = {"conclusion": conclusion, "premises": premises, "source_ref": ref}
    grounded = _grounded(rules, foundations)
    residual = set(claims) - grounded.keys()
    edges = {}
    for identifier, rule in sorted(rules.items()):
        conclusion = rule["conclusion"]
        if conclusion not in residual:
            continue
        for premise in rule["premises"]:
            if premise in residual:
                key = conclusion, premise
                edges.setdefault(key, {"source": conclusion, "target": premise, "rule": identifier,
                                       "source_ref": rule["source_ref"]})
    if len(edges) > MAX_EDGES:
        raise CircularError("Graf ketergantungan belum terurai melampaui batas.")
    adjacency = defaultdict(list)
    for key, item in sorted(edges.items()):
        adjacency[key[0]].append(item)
    components = []
    if residual:
        components = ArgumentGraph({
            "nodes": [{"id": key, "kind": "claim", "text": key, "source_ref": claims[key]}
                      for key in residual],
            "edges": [{"source": source, "target": target, "relation": "supports", "source_ref": edge["source_ref"]}
                      for (source, target), edge in edges.items() if source != target],
        }).strongly_connected()
    cycles = []
    for component in components:
        first = component[0]
        if len(component) == 1 and (first, first) not in edges:
            continue
        members = set(component)
        external_premises = sorted({hop["target"] for name in component for hop in adjacency[name]
                                   if hop["target"] not in members})
        cycles.append({"claims": component, "witness": _witness(first, adjacency, members),
                       "external_unresolved_premises": external_premises})
    circular = {member for cycle in cycles for member in cycle["claims"]}
    return {
        "schema": "ace.circular-detector.v1",
        "grounded": [{"claim": key, "claim_ref": claims[key], **source} for key, source in sorted(grounded.items())],
        "cycles": cycles, "ungrounded_non_cyclic": sorted(residual - circular),
    }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.input.open("rb") as handle:
            blob = handle.read(MAX_BYTES + 1)
        if len(blob) > MAX_BYTES:
            raise CircularError("Masukan putaran melampaui batas.")
        result = detect(json.loads(blob))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(bool(result["cycles"]))


if __name__ == "__main__":
    raise SystemExit(main())
