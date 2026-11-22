"""Tahan kandidat tempa bila kemampuan umum yang ditetapkan meregresi.

Protokol memuat kasus, keluarga, dan kasus kritis sebelum penilaian.
Setiap kasus memakai hasil baseline dan kandidat yang berpasangan.
Kenaikan satu domain tidak menutupi penurunan domain lain. Data
kurang menahan promosi dan kehilangan pada kasus kritis menahan
promosi walau akurasi domain tetap. Input berasal dari hasil offline.
"""
import argparse
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, object_fields, read_bytes, string
from .dataset_forge import MAX_BYTES


MAX_CASES = 20_000


def _fraction(value):
    return {"numerator": value.numerator, "denominator": value.denominator}


def _arm(raw, refs):
    if raw is None:
        return None
    object_fields(raw, ("passed", "assessment_ref"))
    if type(raw["passed"]) is not bool:
        raise InputError("Hasil penilaian harus boolean.")
    pointer = string(raw["assessment_ref"], "rujukan penilaian")
    if pointer in refs:
        raise InputError("Rujukan penilaian ganda.")
    refs.add(pointer)
    return {"passed": raw["passed"], "assessment_ref": pointer}


def _protocol(raw):
    object_fields(raw, ("protocol_ref", "cases"))
    protocol_ref = string(raw["protocol_ref"], "rujukan protokol")
    cases = {}
    refs = {protocol_ref}
    for row in entries(raw["cases"], MAX_CASES):
        object_fields(row, ("case_id", "domain", "case_ref", "critical"))
        key = string(row["case_id"], "ID kasus")
        ref = string(row["case_ref"], "rujukan kasus")
        if key in cases or ref in refs:
            raise InputError("ID kasus atau rujukan di protokol ganda.")
        if type(row["critical"]) is not bool:
            raise InputError("Status kritis harus boolean eksplisit.")
        cases[key] = {"case_id": key, "domain": string(row["domain"], "domain"), "case_ref": ref,
                      "critical": row["critical"]}
        refs.add(ref)
    if not cases:
        raise InputError("Protokol perlu mendaftarkan sedikitnya satu kasus umum.")
    normalized = {"protocol_ref": protocol_ref, "cases": [cases[key] for key in sorted(cases)]}
    return normalized, cases, refs


def protocol_digest(raw):
    """Komitmen yang dibagikan ke kedua penilai sebelum hasil tersedia."""
    protocol, _, _ = _protocol(raw)
    return identity(protocol)


def _domain(name, records):
    paired = [row for row in records if row["status"] != "unpaired"]
    counts = {key: sum(row["status"] == key for row in paired)
              for key in ("retained", "regressed", "improved", "both_failed")}
    critical = [row["case_id"] for row in paired if row["critical"] and row["status"] == "regressed"]
    num_paired = len(paired)
    covered = num_paired == len(records)
    baseline = counts["retained"] + counts["regressed"]
    candidate = counts["retained"] + counts["improved"]
    reasons = []
    if not covered:
        reasons.append("missing_assessments")
    if covered and candidate < baseline:
        reasons.append("domain_accuracy_dropped")
    if critical:
        reasons.append("critical_regression")
    return {
        "domain": name, "status": "hold" if reasons else "pass", "reasons": reasons,
        "expected_cases": len(records), "paired_cases": num_paired, "counts": counts,
        "baseline_accuracy": _fraction(Fraction(baseline, num_paired)) if covered else None,
        "candidate_accuracy": _fraction(Fraction(candidate, num_paired)) if covered else None,
        "accuracy_delta": _fraction(Fraction(candidate - baseline, num_paired)) if covered else None,
        "critical_regressions": critical,
        "cases": records,
    }


def screen(raw, expected_protocol_sha256):
    object_fields(raw, ("protocol", "results"))
    protocol, cases, refs = _protocol(raw["protocol"])
    protocol_sha = identity(protocol)
    if digest(expected_protocol_sha256) != protocol_sha:
        raise InputError("Protokol berbeda dari komitmen penilaian.")
    compared = {}
    for row in entries(raw["results"], MAX_CASES):
        object_fields(row, ("case_id", "baseline", "candidate"))
        key = string(row["case_id"], "ID hasil")
        if key not in cases or key in compared:
            raise InputError("Hasil ganda atau kasus di luar protokol.")
        compared[key] = (_arm(row["baseline"], refs), _arm(row["candidate"], refs))
    groups = defaultdict(list)
    classifications = {(True, True): "retained", (True, False): "regressed",
                       (False, True): "improved", (False, False): "both_failed"}
    for key, registered in sorted(cases.items()):
        baseline, candidate = compared.get(key, (None, None))
        missing = [label for label, arm in (("baseline", baseline), ("candidate", candidate)) if arm is None]
        status = "unpaired" if missing else classifications[baseline["passed"], candidate["passed"]]
        groups[registered["domain"]].append({**registered, "status": status, "missing": missing,
                                             "baseline": baseline, "candidate": candidate})
    scores = [_domain(name, records) for name, records in sorted(groups.items())]
    failed = [item["domain"] for item in scores if item["status"] != "pass"]
    return {
        "schema": "ace.forge-forgetting-guard.v1", "protocol_ref": protocol["protocol_ref"],
        "protocol_sha256": protocol_sha, "status": "hold" if failed else "pass",
        "blocked_domains": failed, "domains": scores,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = screen(decode(read_bytes(args.input, MAX_BYTES)), args.expect_protocol_sha256)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] == "hold")


if __name__ == "__main__":
    raise SystemExit(main())
