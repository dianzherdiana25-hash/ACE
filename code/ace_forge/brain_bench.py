"""Ukur perubahan kualitas dan biaya dari hasil sebelum/sesudah tempa.

Kasus didaftarkan bersama rubric dan sumber. Setiap pengukuran menyimpan
hash artefak yang betul-betul dinilai. Delta kualitas dan biaya memakai
pasangan lengkap dari kasus yang sama. Laporan menyediakan selisih
agregat per domain dan pencilan dengan rujukan; tidak menjalankan organ.
"""
import argparse
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from statistics import median
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from .dataset_forge import MAX_BYTES
from .forgetting_guard import MAX_CASES, _fraction, _protocol


def _arm(raw, artifact, refs):
    if raw is None:
        return None
    object_fields(raw, ("score_bp", "elapsed_us", "peak_bytes", "assessment_ref", "measurement_ref", "artifact_sha256"))
    if digest(raw["artifact_sha256"]) != artifact:
        raise InputError("Hash artefak hasil penilaian berbeda dari lengan yang didaftarkan.")
    values = {}
    for key in ("assessment_ref", "measurement_ref"):
        ref = string(raw[key], key)
        if ref in refs:
            raise InputError("Rujukan penilaian atau waktu ganda.")
        refs.add(ref)
        values[key] = ref
    return {**values, "artifact_sha256": artifact, "score_bp": integer(raw["score_bp"], 0, 10_000),
            "elapsed_us": integer(raw["elapsed_us"], 0, 10**12),
            "peak_bytes": integer(raw["peak_bytes"], 0, 10**13)}


def _paired_summary(records, min_pairs):
    pairs = [row for row in records if row["delta"] is not None]
    count = len(pairs)
    fields = ("score_bp", "elapsed_us", "peak_bytes")
    status = "complete" if count == len(records) else "incomplete"
    if count < min_pairs or status != "complete":
        return {"compared": count, "registered": len(records),
                "status": "too_few_pairs" if count < min_pairs else status,
                "before_mean": None, "after_mean": None, "mean_delta": None, "median_delta": None,
                "lowest_quality_delta": None, "quality_signs": None}
    averages = {}
    for label in ("before", "after", "delta"):
        averages[label] = {field: _fraction(Fraction(sum(row[label][field] for row in pairs), count))
                           for field in fields}
    # Median kalkulasi Fraction agar midpoint tidak berubah menjadi float.
    medians = {field: _fraction(median([Fraction(row["delta"][field]) for row in pairs])) for field in fields}
    lowest = min(row["delta"]["score_bp"] for row in pairs)
    return {
        "compared": count, "registered": len(records), "status": status, "before_mean": averages["before"],
        "after_mean": averages["after"], "mean_delta": averages["delta"], "median_delta": medians,
        "lowest_quality_delta": {"score_bp": lowest, "case_ids": [row["case_id"] for row in pairs
                                                                  if row["delta"]["score_bp"] == lowest]},
        "quality_signs": {key: sum(sign * row["delta"]["score_bp"] > 0 if sign
                                   else row["delta"]["score_bp"] == 0 for row in pairs)
                          for key, sign in (("better", 1), ("tie", 0), ("worse", -1))},
    }


def _setup(raw, expected):
    object_fields(raw, ("protocol", "rubric_ref", "before_sha256", "after_sha256", "minimum_paired", "results"))
    protocol, cases, refs = _protocol(raw["protocol"])
    rubric = string(raw["rubric_ref"], "rujukan rubrik")
    if rubric in refs:
        raise InputError("Rubrik perlu rujukan terpisah.")
    refs.add(rubric)
    first, second = digest(raw["before_sha256"]), digest(raw["after_sha256"])
    if first == second:
        raise InputError("After dan before harus menunjuk dua artefak berbeda.")
    minimum = integer(raw["minimum_paired"], 1, MAX_CASES)
    config = {"protocol": protocol, "rubric_ref": rubric, "before_sha256": first,
              "after_sha256": second, "minimum_paired": minimum}
    computed = identity(config)
    if expected is not None and digest(expected) != computed:
        raise InputError("Hash konfigurasi berbeda dari anchor bench.")
    return config, cases, refs, computed


def bench_digest(raw):
    """Bekukan konfigurasi dan identitas dua artefak sebelum penilaian."""
    return _setup(raw, None)[3]


def report(raw, expected):
    digest(expected)
    config, cases, refs, anchored = _setup(raw, expected)
    scored = {}
    for item in entries(raw["results"], MAX_CASES):
        object_fields(item, ("case_id", "before", "after"))
        key = string(item["case_id"], "ID kasus")
        if key in scored or key not in cases:
            raise InputError("Kasus ganda atau di luar protokol.")
        first = _arm(item["before"], config["before_sha256"], refs)
        second = _arm(item["after"], config["after_sha256"], refs)
        scored[key] = (first, second)
    domains = defaultdict(list)
    all_rows = []
    for key, case in sorted(cases.items()):
        first, second = scored.get(key, (None, None))
        missing = [name for name, arm in (("before", first), ("after", second)) if arm is None]
        delta = None
        if not missing:
            delta = {metric: second[metric] - first[metric] for metric in ("score_bp", "elapsed_us", "peak_bytes")}
        row = {**case, "before": first, "after": second, "missing": missing, "delta": delta}
        all_rows.append(row)
        domains[case["domain"]].append(row)
    minimum = config["minimum_paired"]
    return {
        "schema": "ace.forge-bench.v1", "bench_sha256": anchored, "protocol_ref": config["protocol"]["protocol_ref"],
        "rubric_ref": config["rubric_ref"], "before_sha256": config["before_sha256"], "after_sha256": config["after_sha256"],
        "minimum_paired": minimum, "aggregate": _paired_summary(all_rows, minimum),
        "domains": [{"domain": name, **_paired_summary(rows, minimum), "cases": rows}
                    for name, rows in sorted(domains.items())],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--expect-bench-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        value = report(decode(read_bytes(args.input, MAX_BYTES)), args.expect_bench_sha256)
        sys.stdout.write(canonical(value).decode("utf-8") + "\n")
    except (OSError, RecursionError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
