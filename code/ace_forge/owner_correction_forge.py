"""Fit kebijakan koreksi kategoris dari receipt berizin dan minim data.

Masukan hanya kode konteks, label, keluarga, dan pointer bukti.
Untuk konteks yang mencapai dukungan dari beberapa keluarga, adaptasi
hanya diusulkan apabila semua koreksi sepakat. Held-out dikunci dan
dinilai pada keluarga terpisah dengan keputusan baseline yang sama.
"""
import argparse
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from .adapter_zoo import tags
from .dataset_forge import MAX_BYTES


MAX_CASES = 2000


def _key(row, field, cap=96):
    return string(row[field], field, max_chars=cap)


def _context(row):
    return _key(row, "domain"), _key(row, "context")


def _labels(row, fields, labels):
    values = tuple(_key(row, name) for name in fields)
    if any(value not in labels for value in values):
        raise InputError("Label di luar protokol koreksi.")
    return values


def _binding(row, fields, refs, ids):
    object_fields(row, fields)
    key = _key(row, "id")
    ref = _key(row, "source_ref", 256)
    if key in ids or ref in refs:
        raise InputError("ID atau sumber koreksi ganda.")
    ids.add(key)
    refs.add(ref)
    return key, ref


def _train(raw, labels, refs, ids, allowed_domains):
    families = set()
    grouped = defaultdict(list)
    for row in entries(raw, MAX_CASES):
        key, ref = _binding(row, ("id", "source_ref", "actor_role", "family", "domain",
                                  "context", "before", "after", "consent_ref"), refs, ids)
        consent = _key(row, "consent_ref", 256)
        family = _key(row, "family")
        before, after = _labels(row, ("before", "after"), labels)
        context = _context(row)
        if row["actor_role"] != "owner_review" or before == after or consent == ref or context[0] not in allowed_domains:
            raise InputError("Koreksi tanpa penanda izin/peran, perubahan label, atau domain resmi.")
        grouped[context].append({"id": key, "source_ref": ref, "consent_ref": consent, "family": family,
                                 "before": before, "after": after})
        families.add(family)
    return grouped, families


def train(raw, corrections, expected):
    object_fields(raw, ("recipe_ref", "corrections_sha256", "minimum_families", "domains", "labels", "held_out"))
    if identity(raw) != digest(expected):
        raise InputError("Resep koreksi berbeda dari anchor.")
    if identity(corrections) != digest(raw["corrections_sha256"]):
        raise InputError("Koreksi berbeda dari komitmen resep.")
    source = _key(raw, "recipe_ref", 256)
    domains = set(tags(raw["domains"], "nama domain"))
    labels = set(tags(raw["labels"], "label keputusan"))
    minimum = integer(raw["minimum_families"], 1, MAX_CASES)
    refs, ids = {source}, set()
    groups, train_families = _train(corrections, labels, refs, ids, domains)
    rows = []
    index = {}
    for (domain, context), support in sorted(groups.items()):
        labels_seen = {item["after"] for item in support}
        count = len({item["family"] for item in support})
        status = "ready" if count >= minimum and len(labels_seen) == 1 else (
            "conflicting_labels" if len(labels_seen) > 1 else "insufficient_support")
        value = next(iter(labels_seen)) if status == "ready" else None
        rows.append({"domain": domain, "context": context, "distinct_families": count, "status": status, "label": value,
                     "sources": sorted(support, key=lambda item: item["id"])})
        if value is not None:
            index[domain, context] = value
    evaluation = []
    for row in entries(raw["held_out"], MAX_CASES):
        key, reference = _binding(row, ("id", "source_ref", "family", "domain", "context", "baseline", "expected"), refs, ids)
        domain, context = _context(row)
        family = _key(row, "family")
        if family in train_families or domain not in domains:
            raise InputError("Held-out tumpang tindih dengan train atau domain tak dikenal.")
        baseline, target = _labels(row, ("baseline", "expected"), labels)
        selected = index.get((domain, context))
        decision = selected if selected is not None else baseline
        evaluation.append({"id": key, "source_ref": reference, "family": family, "domain": domain, "context": context,
                           "correction_applied": selected is not None and selected != baseline,
                           "baseline_correct": baseline == target, "corrected_correct": decision == target})
    count = len(evaluation)
    baseline = sum(row["baseline_correct"] for row in evaluation)
    candidate = sum(row["corrected_correct"] for row in evaluation)
    delta = Fraction(candidate-baseline, count) if count else None
    summary = {"held_out": count, "baseline_correct": baseline, "corrected_correct": candidate,
               "delta": {"numerator": delta.numerator, "denominator": delta.denominator} if delta is not None else None}
    return {"schema": "ace.forge-correction-policy.v1", "recipe_ref": source, "recipe_sha256": expected,
            "corrections_sha256": raw["corrections_sha256"], "policies": rows, "summary": summary,
            "evaluation": sorted(evaluation, key=lambda item: item["id"])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recipe", type=Path)
    parser.add_argument("corrections", type=Path)
    parser.add_argument("--expect-recipe-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = train(decode(read_bytes(args.recipe, MAX_BYTES)), decode(read_bytes(args.corrections, MAX_BYTES)),
                       args.expect_recipe_sha256)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
