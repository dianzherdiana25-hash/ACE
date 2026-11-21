"""Audit matriks transfer antar-domain dari outcome berpasangan.

Setiap domain sumber dievaluasi pada roster target dan baseline yang sama. Domain
keluarga latih dan evaluasi tidak bertumpang tindih. Sel yang kurang
bukti tetap kosong dan tidak mengubah delta within atau cross yang
dihitung pada sel terukur.
"""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES
from .forgetting_guard import _fraction


MAX_DOMAINS = 32
MAX_ITEMS = 2000


def _plan(raw):
    object_fields(raw, ("protocol_ref", "baseline_sha256", "minimum_per_cell", "sources", "target_cases"))
    protocol = string(raw["protocol_ref"], "rujukan protokol")
    baseline = digest(raw["baseline_sha256"])
    minimum = integer(raw["minimum_per_cell"], 1, MAX_ITEMS)
    refs, artifacts = {protocol}, {baseline}
    sources = {}
    training = set()
    for row in entries(raw["sources"], MAX_DOMAINS):
        object_fields(row, ("domain", "artifact_sha256", "training_families", "training_ref"))
        key = string(row["domain"], "domain tempa")
        artifact = digest(row["artifact_sha256"])
        if key in sources or artifact in artifacts:
            raise InputError("Domain sumber atau artefak ganda.")
        artifacts.add(artifact)
        families = set()
        for family in entries(row["training_families"], MAX_ITEMS):
            reference(family, families, "keluarga train")
        if not families:
            raise InputError("Keluarga latih harus dicatat.")
        training.update(families)
        sources[key] = {"artifact_sha256": artifact, "training_ref": reference(row["training_ref"], refs, "rujukan train")}
    cases, domains = {}, defaultdict(list)
    ids = set()
    for row in entries(raw["target_cases"], MAX_ITEMS):
        object_fields(row, ("id", "domain", "family_id", "case_ref"))
        key = reference(row["id"], ids, "ID kasus")
        domain = string(row["domain"], "domain target")
        family = string(row["family_id"], "keluarga held-out")
        if family in training:
            raise InputError("Keluarga held-out bertumpang tindih dengan train.")
        pointer = reference(row["case_ref"], refs, "rujukan kasus")
        cases[key] = {"id": key, "case_ref": pointer, "family_id": family}
        domains[domain].append(key)
    if not sources or not domains or len(domains) > MAX_DOMAINS:
        raise InputError("Matriks membutuhkan daftar sumber dan target dalam batas.")
    return protocol, baseline, minimum, sources, cases, domains, refs


def _result(raw, artifact, refs):
    if raw is None:
        return None
    object_fields(raw, ("artifact_sha256", "passed", "receipt_ref"))
    if digest(raw["artifact_sha256"]) != artifact or type(raw["passed"]) is not bool:
        raise InputError("Verdict atau identitas artefak salah.")
    return {"passed": raw["passed"], "receipt_ref": reference(raw["receipt_ref"], refs, "rujukan receipt")}


def _cell(source, target, ids, cases, baseline, results, minimum):
    records = []
    counts = Counter()
    for key in sorted(ids):
        before = baseline.get(key)
        after = results.get((source, key))
        outcome = "missing"
        if before is not None and after is not None:
            outcome = {(True, True): "retained", (True, False): "regressed",
                       (False, True): "improved", (False, False): "both_failed"}[before["passed"], after["passed"]]
        counts[outcome] += 1
        records.append({**cases[key], "before": before, "after": after, "outcome": outcome})
    size = len(ids) - counts["missing"]
    covered = size == len(ids) and size >= minimum
    delta = Fraction(counts["improved"] - counts["regressed"], size) if covered else None
    return {"source_domain": source, "target_domain": target, "scope": "within" if source == target else "cross",
            "expected": len(ids), "paired": size, "status": "measured" if covered else "insufficient_evidence",
            "delta": _fraction(delta) if covered else None, "counts": dict(sorted(counts.items())), "cases": records}


def _macro(cells, scope):
    related = [cell for cell in cells if cell["scope"] == scope]
    values = [Fraction(**cell["delta"]) for cell in related if cell["delta"] is not None]
    return {"cells": len(related), "measured_cells": len(values),
            "observed_mean_delta": _fraction(sum(values) / len(values)) if values else None}


def measure(protocol, evidence, expected):
    if identity(protocol) != digest(expected):
        raise InputError("Rencana transfer berbeda dari anchor.")
    ref, baseline, min_size, sources, cases, domains, refs = _plan(protocol)
    object_fields(evidence, ("baseline", "adapted"))
    reference_results = {}
    for row in entries(evidence["baseline"], MAX_ITEMS):
        object_fields(row, ("case_id", "result"))
        key = string(row["case_id"], "ID baseline")
        if key not in cases or key in reference_results:
            raise InputError("Kasus baseline ganda atau di luar matriks.")
        reference_results[key] = _result(row["result"], baseline, refs)
    rows = {}
    for item in entries(evidence["adapted"], MAX_DOMAINS * MAX_ITEMS):
        object_fields(item, ("source_domain", "case_id", "result"))
        source = string(item["source_domain"], "domain tempa")
        key = string(item["case_id"], "ID kasus")
        if source not in sources or key not in cases or (source, key) in rows:
            raise InputError("Pasangan ganda atau di luar matriks.")
        rows[source, key] = _result(item["result"], sources[source]["artifact_sha256"], refs)
    cells = [_cell(source, target, domains[target], cases, reference_results, rows, min_size)
             for source in sorted(sources) for target in sorted(domains)]
    return {"schema": "ace.forge-transfer-matrix.v1", "protocol_ref": ref, "protocol_sha256": expected,
            "evidence_sha256": identity(evidence), "baseline_sha256": baseline, "sources": dict(sorted(sources.items())),
            "cells": cells, "within": _macro(cells, "within"), "cross": _macro(cells, "cross")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        value = measure(decode(read_bytes(args.protocol, MAX_BYTES)), decode(read_bytes(args.evidence, MAX_BYTES)),
                        args.expect_protocol_sha256)
        sys.stdout.write(canonical(value).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
