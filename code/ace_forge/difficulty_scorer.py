"""Nilai kesulitan contoh dari kegagalan solver yang sudah direkam.

Prior dan ambang kebijakan eksplisit. Satu solver hanya menyumbang
satu verdict per contoh. Skor hanya dikeluarkan setelah lantai sampel
tercapai. Report juga mengukur seberapa jauh skor berubah bila satu
verdict dikeluarkan.
"""
import argparse
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES
from .forgetting_guard import _fraction


MAX_SOLVERS = 80
MAX_EXAMPLES = 3000


def _spec(raw, expected):
    object_fields(raw, ("protocol_ref", "report_ref", "minimum_observed", "prior", "bands", "examples", "solvers"))
    if identity(raw) != digest(expected):
        raise InputError("Protokol kesulitan berbeda dari anchor.")
    protocol = string(raw["protocol_ref"], "rujukan protokol")
    refs, ids = {protocol}, set()
    report = reference(raw["report_ref"], refs, "rujukan report")
    minimum = integer(raw["minimum_observed"], 1, MAX_SOLVERS)
    object_fields(raw["prior"], ("failure", "success", "ref"))
    prior = (integer(raw["prior"]["failure"], 1, 1000), integer(raw["prior"]["success"], 1, 1000),
             reference(raw["prior"]["ref"], refs, "rujukan prior"))
    bands, floor, names = [], 0, set()
    for record in entries(raw["bands"], 20):
        object_fields(record, ("id", "max_bp"))
        key = reference(record["id"], names, "ID pita")
        ceiling = integer(record["max_bp"], floor, 10_000)
        floor = ceiling + 1
        bands.append((ceiling, key))
    if floor != 10_001:
        raise InputError("Pita mesti berurutan dan mencakup seluruh 0–10.000.")
    solvers = {}
    for row in entries(raw["solvers"], MAX_SOLVERS):
        object_fields(row, ("id", "artifact_sha256", "source_ref"))
        key = reference(row["id"], ids, "ID solver")
        solvers[key] = (digest(row["artifact_sha256"]), reference(row["source_ref"], refs, "rujukan solver"))
    if len(solvers) < minimum or len({value[0] for value in solvers.values()}) != len(solvers):
        raise InputError("Solver terlalu sedikit atau artefaknya ganda.")
    examples, ids = {}, set()
    for item in entries(raw["examples"], MAX_EXAMPLES):
        object_fields(item, ("id", "source_ref", "task_kind"))
        key = reference(item["id"], ids, "ID contoh")
        if "#" in key or len(report) + len(key) + 1 > 256:
            raise InputError("Rujukan anotasi terlalu panjang atau memakai separator ganda.")
        examples[key] = {"example_id": key, "task_kind": string(item["task_kind"], "jenis tugas"),
                         "source_ref": reference(item["source_ref"], refs, "rujukan contoh")}
    if not examples:
        raise InputError("Roster kesulitan kosong.")
    return protocol, report, minimum, prior, bands, solvers, examples, refs


def _score(failure, observed, alpha, beta):
    return Fraction(failure + alpha, observed + alpha + beta)


def _card(archived, solvers, observations, prior, minimum, bands):
    rows = sorted(archived, key=lambda row: row["solver"])
    count = len(rows)
    failures = sum(not row["passed"] for row in rows)
    initial = {**observations, "observed": count, "failures": failures,
               "missing_solvers": sorted(set(solvers) - {row["solver"] for row in rows}),
               "attempts": rows}
    if count < minimum:
        return {**initial, "status": "insufficient_observations", "difficulty": None, "difficulty_bp": None,
                "band": None, "leave_one_out": None}
    alpha, beta, _ = prior
    score = _score(failures, count, alpha, beta)
    point = score * 10_000
    rounded = (2 * point.numerator + point.denominator) // (2 * point.denominator)
    leave_out = [_score(failures - int(not row["passed"]), count - 1, alpha, beta) for row in rows]
    return {**initial, "status": "scored", "difficulty": _fraction(score), "difficulty_bp": rounded,
            "band": next(label for ceiling, label in bands if rounded <= ceiling),
            "leave_one_out": {"low": _fraction(min(leave_out)), "high": _fraction(max(leave_out))}}


def score(protocol, evidence, expected):
    pointer, report, minimum, prior, bands, solvers, examples, refs = _spec(protocol, expected)
    grouped, seen = defaultdict(list), set()
    for row in entries(evidence, MAX_EXAMPLES * MAX_SOLVERS):
        object_fields(row, ("example_id", "solver", "artifact_sha256", "passed", "receipt_ref"))
        example = string(row["example_id"], "ID contoh")
        solver = string(row["solver"], "ID solver")
        if (example not in examples or solver not in solvers or (example, solver) in seen
                or digest(row["artifact_sha256"]) != solvers[solver][0] or type(row["passed"]) is not bool):
            raise InputError("Verdict tidak dikenal, ganda, atau identitas solver tidak cocok.")
        seen.add((example, solver))
        grouped[example].append({"solver": solver, "solver_ref": solvers[solver][1], "passed": row["passed"],
                                 "receipt_ref": reference(row["receipt_ref"], refs, "rujukan receipt")})
    cards = [_card(grouped[key], solvers, example, prior, minimum, bands) for key, example in sorted(examples.items())]
    annotations = [{"example_id": row["example_id"], "difficulty_bp": row["difficulty_bp"],
                    "evidence_ref": f"{report}#{row['example_id']}"} for row in cards if row["status"] == "scored"]
    return {"schema": "ace.forge-difficulty-scores.v1", "protocol_ref": pointer, "protocol_sha256": expected,
            "evidence_sha256": identity(evidence), "prior_ref": prior[2], "report_ref": report,
            "annotations": annotations, "examples": cards}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("observations", type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        value = score(decode(read_bytes(args.protocol, MAX_BYTES)), decode(read_bytes(args.observations, MAX_BYTES)),
                      args.expect_protocol_sha256)
        sys.stdout.write(canonical(value).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
