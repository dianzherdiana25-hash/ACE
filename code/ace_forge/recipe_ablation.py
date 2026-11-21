"""Bandingkan dampak satu perubahan resep terhadap baseline bersama.

Resep diurai menjadi jalur parameter yang dipatok. Setiap varian
harus mengubah tepat jalur yang dinyatakan. Skor dan token dirangkum
dari pasangan pada roster kasus yang sama. Sampel tidak lengkap
menahan delta agregat, sambil mempertahankan rujukan yang tersedia.
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


MAX_VARIANTS = 32
MAX_CASES = 2000


def _flatten(raw, path=()):
    if not isinstance(raw, dict) or not raw or len(path) > 10 or len(raw) > 1000:
        raise InputError("Objek parameter resep kosong atau terlalu dalam.")
    output = {}
    for key, value in raw.items():
        name = string(key, "parameter", preserve=True)
        if name.strip() != name:
            raise InputError("Nama parameter perlu kanonis.")
        position = (*path, name)
        if isinstance(value, dict):
            output.update(_flatten(value, position))
        else:
            output[position] = canonical(value)
    if len(output) > 1000:
        raise InputError("Jumlah parameter melampaui batas.")
    return output


def _recipes(protocol, pointers):
    first = protocol["baseline"]
    object_fields(first, ("artifact_sha256", "recipe_ref", "recipe"))
    baseline = digest(first["artifact_sha256"])
    base_ref = reference(first["recipe_ref"], pointers, "rujukan resep baseline")
    base_recipe = _flatten(first["recipe"])
    variants, artifacts = {}, {baseline}
    for row in entries(protocol["variants"], MAX_VARIANTS):
        object_fields(row, ("id", "artifact_sha256", "recipe_ref", "recipe", "parameter_path"))
        key = string(row["id"], "ID varian")
        artifact = digest(row["artifact_sha256"])
        if key in variants or artifact in artifacts:
            raise InputError("Varian atau artefak berulang.")
        changed = _flatten(row["recipe"])
        stated = tuple(string(item, "jalur parameter", preserve=True) for item in entries(row["parameter_path"], 12))
        if (base_recipe.keys() != changed.keys()
                or [part for part in sorted(base_recipe) if base_recipe[part] != changed[part]] != [stated]):
            raise InputError("Setiap varian harus mengubah persis satu jalur parameter yang didaftarkan.")
        artifacts.add(artifact)
        variants[key] = {"id": key, "artifact_sha256": artifact, "recipe_sha256": identity(row["recipe"]),
                         "recipe_ref": reference(row["recipe_ref"], pointers, "rujukan resep varian"),
                         "parameter_path": list(stated), "before_value": decode(base_recipe[stated]),
                         "after_value": decode(changed[stated])}
    if not variants:
        raise InputError("Ablasi membutuhkan setidaknya satu varian.")
    return {"artifact_sha256": baseline, "recipe_ref": base_ref, "recipe_sha256": identity(first["recipe"])}, variants


def _observation(row, artifact, refs):
    if row is None:
        return None
    object_fields(row, ("artifact_sha256", "score_bp", "tokens", "receipt_ref"))
    if digest(row["artifact_sha256"]) != artifact:
        raise InputError("Receipt memakai artefak berbeda.")
    return {"score_bp": integer(row["score_bp"], 0, 10_000), "tokens": integer(row["tokens"], 0, 10**12),
            "receipt_ref": reference(row["receipt_ref"], refs, "rujukan receipt")}


def _summary(rows, minimum):
    paired = [row for row in rows if row["delta_score_bp"] is not None]
    eligible = len(paired) == len(rows) and len(paired) >= minimum
    return {"cases": len(rows), "paired": len(paired), "status": "measured" if eligible else "insufficient_evidence",
            "mean_delta_score_bp": _fraction(Fraction(sum(row["delta_score_bp"] for row in paired), len(paired)))
            if eligible else None, "mean_delta_tokens": _fraction(Fraction(sum(row["delta_tokens"] for row in paired), len(paired)))
            if eligible else None}


def analyze(protocol, observations, expected):
    object_fields(protocol, ("protocol_ref", "baseline", "variants", "test_cases", "minimum_pairs"))
    if identity(protocol) != digest(expected):
        raise InputError("Protokol ablasi berbeda dari anchor.")
    pointer = string(protocol["protocol_ref"], "rujukan protokol")
    refs, seen = {pointer}, set()
    base, variants = _recipes(protocol, refs)
    minimum = integer(protocol["minimum_pairs"], 1, MAX_CASES)
    cases = {}
    for item in entries(protocol["test_cases"], MAX_CASES):
        object_fields(item, ("id", "domain", "case_ref"))
        key = reference(item["id"], seen, "ID kasus")
        cases[key] = {"id": key, "domain": string(item["domain"], "domain"),
                      "case_ref": reference(item["case_ref"], refs, "rujukan kasus")}
    if not cases:
        raise InputError("Roster kasus tidak boleh kosong.")
    object_fields(observations, ("baseline", "variants"))
    before, after = {}, {}
    for row in entries(observations["baseline"], MAX_CASES):
        object_fields(row, ("case_id", "observation"))
        key = string(row["case_id"], "ID baseline")
        if key in before or key not in cases:
            raise InputError("Kasus baseline ganda atau di luar roster.")
        before[key] = _observation(row["observation"], base["artifact_sha256"], refs)
    for row in entries(observations["variants"], MAX_CASES * MAX_VARIANTS):
        object_fields(row, ("case_id", "variant_id", "observation"))
        key = string(row["case_id"], "ID kasus")
        variant = string(row["variant_id"], "ID varian")
        if (variant, key) in after or key not in cases or variant not in variants:
            raise InputError("Pasangan varian ganda atau tidak terdaftar.")
        after[variant, key] = _observation(row["observation"], variants[variant]["artifact_sha256"], refs)
    reports = []
    for key, version in sorted(variants.items()):
        comparisons, grouped = [], defaultdict(list)
        for case, card in sorted(cases.items()):
            old, new = before.get(case), after.get((key, case))
            diffs = (new["score_bp"] - old["score_bp"], new["tokens"] - old["tokens"]) if old and new else (None, None)
            result = {**card, "baseline": old, "variant": new, "delta_score_bp": diffs[0], "delta_tokens": diffs[1]}
            comparisons.append(result)
            grouped[card["domain"]].append(result)
        reports.append({**version, "summary": _summary(comparisons, minimum), "cases": comparisons,
                        "domains": [{"domain": group, **_summary(cards, minimum)} for group, cards in sorted(grouped.items())]})
    return {"schema": "ace.forge-recipe-ablation.v1", "protocol_ref": pointer, "protocol_sha256": expected,
            "observations_sha256": identity(observations), "baseline": base, "variants": reports}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("observations", type=Path)
    parser.add_argument("--expect-protocol-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        product = analyze(decode(read_bytes(args.protocol, MAX_BYTES)), decode(read_bytes(args.observations, MAX_BYTES)),
                          args.expect_protocol_sha256)
        sys.stdout.write(canonical(product).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
