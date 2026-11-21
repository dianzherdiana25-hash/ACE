"""Fit readout lokal untuk merangking kandidat kode dari preferensi tercatat.

Fitur diambil dari AST Python tanpa mengeksekusi kandidat. Ranker
perceptron belajar membedakan dua kandidat yang dinilai untuk satu
tugas. Pengukuran fixture per keluarga held-out menjaga pasangan uji
terpisah dari contoh yang memperbarui bobot.
"""
import argparse
import ast
from collections import Counter
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES


FEATURES = ("parseable", "required_defs", "required_calls", "has_return_value", "branches", "raise_sites", "node_count")
MAX_PAIRS = 2000
MAX_NODES = 2500


def _symbols(values):
    names = set()
    for value in entries(values, 30):
        name = reference(value, names, "simbol")
        if not name.isidentifier():
            raise InputError("Simbol kontrak Python tidak sah.")
    return names


def _describe(code, required_defs, required_calls):
    snippet = string(code, "kandidat kode", max_chars=12_000, preserve=True)
    try:
        tree = ast.parse(snippet)
    except (SyntaxError, RecursionError):
        return ((0,) * len(FEATURES), identity(snippet.replace("\r\n", "\n").strip()))
    defs, calls = set(), set()
    count = branches = raises = returns = 0
    for count, node in enumerate(ast.walk(tree), 1):
        if count > MAX_NODES:
            raise InputError("AST kandidat terlalu besar.")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs.add(node.name)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            calls.add(node.func.id)
        branches += isinstance(node, (ast.If, ast.For, ast.While, ast.Match, ast.IfExp))
        raises += isinstance(node, ast.Raise)
        returns += isinstance(node, ast.Return) and node.value is not None
    return ((1, len(defs & required_defs), len(calls & required_calls), int(bool(returns)),
             min(branches, 12), min(raises, 12), min(count // 10, 30)),
            identity(ast.dump(tree)))


def features(code, required_defs, required_calls):
    return _describe(code, required_defs, required_calls)[0]


def _candidate(row, refs, defs, calls):
    object_fields(row, ("ref", "code"))
    vector, hash_ = _describe(row["code"], defs, calls)
    return reference(row["ref"], refs, "rujukan kandidat"), vector, hash_


def _record(raw, ids, refs, paired_hashes, splits):
    object_fields(raw, ("id", "family_id", "split", "task_ref", "assessment_ref", "required_defs",
                        "required_calls", "preferred", "alternative"))
    key = reference(raw["id"], ids, "ID pasangan kode")
    family = string(raw["family_id"], "keluarga")
    split = string(raw["split"], "partisi")
    if split not in ("train", "held_out") or splits.setdefault(family, split) != split:
        raise InputError("Partisi pasangan tidak sah atau keluarga bocor.")
    task = reference(raw["task_ref"], refs, "rujukan tugas kode")
    assessment = reference(raw["assessment_ref"], refs, "rujukan penilaian")
    defs, calls = _symbols(raw["required_defs"]), _symbols(raw["required_calls"])
    a, left, sa = _candidate(raw["preferred"], refs, defs, calls)
    b, right, sb = _candidate(raw["alternative"], refs, defs, calls)
    pointer = identity([sorted(defs), sorted(calls), sorted((sa, sb))])
    if sa == sb or pointer in paired_hashes:
        raise InputError("Pasangan kode identik atau diulang.")
    paired_hashes.add(pointer)
    return {"id": key, "family_id": family, "split": split, "task_ref": task, "assessment_ref": assessment,
            "preferred_ref": a, "alternative_ref": b, "difference": [x-y for x, y in zip(left, right, strict=True)]}


def _dot(weights, delta):
    return sum(weight * value for weight, value in zip(weights, delta, strict=True))


def _rank(weights, rows):
    rated = []
    for row in rows:
        margin = _dot(weights, row["difference"])
        rated.append({**row, "margin": margin, "outcome": "preferred" if margin > 0 else "tie" if not margin else "alternative"})
    return rated


def forge(raw, expected):
    object_fields(raw, ("recipe_ref", "pairs", "epochs"))
    if identity(raw) != digest(expected):
        raise InputError("Paket ranker kode berbeda dari anchor.")
    ref = string(raw["recipe_ref"], "rujukan resep")
    epochs = integer(raw["epochs"], 1, 30)
    ids, refs, hashes, splits = set(), {ref}, set(), {}
    rows = sorted((_record(row, ids, refs, hashes, splits) for row in entries(raw["pairs"], MAX_PAIRS)),
                  key=lambda row: row["id"])
    train = [row for row in rows if row["split"] == "train"]
    held = [row for row in rows if row["split"] == "held_out"]
    if not train:
        raise InputError("Ranker kode memerlukan setidaknya satu pasangan train.")
    weights = [0] * len(FEATURES)
    updates = []
    for _ in range(epochs):
        count = 0
        for pair in train:
            delta = pair["difference"]
            if _dot(weights, delta) <= 0 and any(delta):
                weights = [weight + value for weight, value in zip(weights, delta, strict=True)]
                count += 1
        updates.append(count)
    adapter = {"schema": "ace.code-preference-ranker.v1", "features": list(FEATURES), "weights": weights}
    held_scored = _rank(weights, held)
    counts = Counter(row["outcome"] for row in held_scored)
    return {"schema": "ace.forge-code-ranker-receipt.v1", "recipe_ref": ref, "input_sha256": expected,
            "adapter": adapter, "adapter_sha256": identity(adapter), "updates_per_epoch": updates,
            "training": _rank(weights, train), "held_out": held_scored,
            "held_out_summary": {"cases": len(held), "preferred": counts["preferred"],
                                 "tie": counts["tie"], "alternative": counts["alternative"]} if held else None}


def rank_candidates(raw, expected_query, adapter, expected_adapter):
    object_fields(raw, ("task_ref", "required_defs", "required_calls", "candidates"))
    object_fields(adapter, ("schema", "features", "weights"))
    if identity(raw) != digest(expected_query) or identity(adapter) != digest(expected_adapter):
        raise InputError("Input rank berbeda dari anchor.")
    if adapter["schema"] != "ace.code-preference-ranker.v1" or adapter["features"] != list(FEATURES):
        raise InputError("Format input ranker tidak cocok.")
    weights = [integer(value, -2_000_000, 2_000_000) for value in entries(adapter["weights"], len(FEATURES))]
    if len(weights) != len(FEATURES):
        raise InputError("Jumlah bobot ranker berbeda.")
    task = string(raw["task_ref"], "rujukan tugas")
    defs, calls = _symbols(raw["required_defs"]), _symbols(raw["required_calls"])
    refs = {task}
    ranked = []
    for row in entries(raw["candidates"], 100):
        source, vector, _ = _candidate(row, refs, defs, calls)
        ranked.append({"candidate_ref": source, "score": _dot(weights, vector)})
    ranked.sort(key=lambda row: (-row["score"], row["candidate_ref"]))
    return {"schema": "ace.code-candidate-ranking.v1", "query_sha256": expected_query,
            "adapter_sha256": expected_adapter, "task_ref": task, "ranking": ranked}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--expect-input-sha256", required=True)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--expect-adapter-sha256")
    args = parser.parse_args(argv)
    if (args.adapter is None) != (args.expect_adapter_sha256 is None):
        parser.error("Mode rank memerlukan artefak adaptor dan anchor.")
    try:
        raw = decode(read_bytes(args.input, MAX_BYTES))
        if args.adapter:
            result = rank_candidates(raw, args.expect_input_sha256, decode(read_bytes(args.adapter, MAX_BYTES)),
                                     args.expect_adapter_sha256)
        else:
            result = forge(raw, args.expect_input_sha256)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
