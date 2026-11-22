"""Bandingkan guru dan murid pada kasus held-out di luar bahan distilasi.

Audit memeriksa tabrakan ID, hash prompt, sumber, serta keluarga antara
bahan ajar dan evaluasi. Perbandingan memakai kasus yang memiliki
kedua penilaian. Retensi mengukur bagian keberhasilan guru yang juga
dicapai murid. Pertanyaan yang hanya lulus pada murid tetap terpisah.
"""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
from math import comb
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES
from .forgetting_guard import _fraction


MAX_ITEMS = 25_000


def _questions(rows, *, held_out, references, ids, prompts):
    result = {}
    for row in entries(rows, MAX_ITEMS):
        mandatory = ("id", "family_id", "prompt_sha256", "source_ref")
        object_fields(row, (*mandatory, "domain") if held_out else mandatory)
        key = reference(row["id"], ids, "ID train/held-out")
        sha = digest(row["prompt_sha256"])
        if sha in prompts:
            raise InputError("Hash prompt ganda antara atau dalam partisi.")
        prompts.add(sha)
        values = {"id": key, "family_id": string(row["family_id"], "keluarga"),
                  "prompt_sha256": sha, "source_ref": reference(row["source_ref"], references, "rujukan soal")}
        if held_out:
            values["domain"] = string(row["domain"], "domain")
        result[key] = values
    return result


def _arm(raw, expected, refs):
    if raw is None:
        return None
    object_fields(raw, ("artifact_sha256", "assessment_ref", "passed"))
    if digest(raw["artifact_sha256"]) != expected or type(raw["passed"]) is not bool:
        raise InputError("Receipt memakai artefak salah atau verdict bukan boolean.")
    return {"artifact_sha256": expected, "assessment_ref": reference(raw["assessment_ref"], refs, "rujukan penilaian"),
            "passed": raw["passed"]}


def _paired_sign_test(teacher_only, student_only):
    discordant = teacher_only + student_only
    # Bound exact integer arithmetic. Large cohorts retain raw counts.
    if discordant > 512:
        return None
    smaller = min(teacher_only, student_only)
    left_tail = sum(comb(discordant, rank) for rank in range(smaller + 1))
    return _fraction(min(Fraction(1), Fraction(2 * left_tail, 2**discordant)))


def _statistics(rows, minimum):
    counts = Counter(row["outcome"] for row in rows)
    comparable = len(rows) - counts["unpaired"]
    teacher_pass = counts["both_pass"] + counts["teacher_only"]
    student_pass = counts["both_pass"] + counts["student_only"]
    available = comparable >= minimum
    return {
        "status": "paired" if available else "insufficient_pairs",
        "expected": len(rows), "paired": comparable, "missing_pairs": counts["unpaired"],
        "both_pass": counts["both_pass"], "teacher_only": counts["teacher_only"],
        "student_only": counts["student_only"], "both_fail": counts["both_fail"],
        "teacher_accuracy": _fraction(Fraction(teacher_pass, comparable)) if available else None,
        "student_accuracy": _fraction(Fraction(student_pass, comparable)) if available else None,
        "accuracy_delta": _fraction(Fraction(student_pass - teacher_pass, comparable)) if available else None,
        "pair_sign_p_two_sided": _paired_sign_test(counts["teacher_only"], counts["student_only"]) if available else None,
        "retained_teacher_successes": _fraction(Fraction(counts["both_pass"], teacher_pass))
        if available and teacher_pass else None,
    }


def score(protocol, observations, expected):
    object_fields(protocol, ("protocol_ref", "teacher_sha256", "student_sha256", "minimum_pairs", "training", "held_out"))
    if identity(protocol) != digest(expected):
        raise InputError("Protokol distilasi berbeda dari anchor.")
    source = string(protocol["protocol_ref"], "rujukan protokol")
    teacher, student = digest(protocol["teacher_sha256"]), digest(protocol["student_sha256"])
    if teacher == student:
        raise InputError("Guru dan murid harus artefak berbeda.")
    refs, ids, prompts = {source}, set(), set()
    train = _questions(protocol["training"], held_out=False, references=refs, ids=ids, prompts=prompts)
    held_out = _questions(protocol["held_out"], held_out=True, references=refs, ids=ids, prompts=prompts)
    if not train or not held_out:
        raise InputError("Bahan distilasi dan held-out harus dicatat.")
    overlap = {row["family_id"] for row in train.values()} & {row["family_id"] for row in held_out.values()}
    if overlap:
        raise InputError("Keluarga bahan ajar overlap dengan held-out.")
    minimum = integer(protocol["minimum_pairs"], 1, MAX_ITEMS)

    by_key = {}
    for row in entries(observations, MAX_ITEMS):
        object_fields(row, ("id", "teacher", "student"))
        key = string(row["id"], "ID hasil")
        if key in by_key or key not in held_out:
            raise InputError("Hasil duplikat atau di luar held-out.")
        by_key[key] = (_arm(row["teacher"], teacher, refs), _arm(row["student"], student, refs))
    groups = defaultdict(list)
    results = []
    verdicts = {(True, True): "both_pass", (True, False): "teacher_only",
                (False, True): "student_only", (False, False): "both_fail"}
    for key, question in sorted(held_out.items()):
        source_a, source_b = by_key.get(key, (None, None))
        missing = [arm for arm, value in (("teacher", source_a), ("student", source_b)) if value is None]
        verdict = "unpaired" if missing else verdicts[source_a["passed"], source_b["passed"]]
        record = {**question, "teacher": source_a, "student": source_b, "outcome": verdict, "missing": missing}
        groups[question["domain"]].append(record)
        results.append(record)
    return {"schema": "ace.forge-distill-bench.v1", "protocol_sha256": expected, "protocol_ref": source,
            "teacher_sha256": teacher, "student_sha256": student, "training_count": len(train),
            "observations_sha256": identity(observations), "summary": _statistics(results, minimum),
            "domains": [{"domain": name, **_statistics(rows, minimum)} for name, rows in sorted(groups.items())],
            "cases": results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("observations", type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = score(decode(read_bytes(args.protocol, MAX_BYTES)), decode(read_bytes(args.observations, MAX_BYTES)),
                       args.expect_protocol_sha256)
        sys.stdout.write(canonical(report).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
