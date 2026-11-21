"""Susun contoh negatif dari taksonomi tertutup dan label berkustodi.

Label salah dipilih hanya dari anggota taksonomi yang sudah terdaftar
dan berbeda dari label gold eksklusif. Jarak edit mendahulukan label
yang mudah tertukar. Output adalah bundle contrastive dengan rujukan
gold, lawan dan aturan, terpisah dari format contoh positif.
"""
import argparse
from functools import lru_cache
from pathlib import Path
import sys
import unicodedata

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from ._numeric import operation_budget, reference
from .dataset_custody import MAX_MANIFEST_BYTES, verify
from .dataset_forge import MAX_BYTES


MAX_LABELS = 80
MAX_JOBS = 3500


def _norm(value):
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


@lru_cache(maxsize=8192)
def _distance(left, right):
    previous = list(range(len(right) + 1))
    for i, first in enumerate(left, 1):
        current = [i]
        for j, second in enumerate(right, 1):
            current.append(min(previous[j] + 1, current[-1] + 1, previous[j-1] + (first != second)))
        previous = current
    return previous[-1]


def _policy(raw, expected):
    object_fields(raw, ("policy_ref", "maximum_per_case", "taxonomies"))
    if identity(raw) != digest(expected):
        raise InputError("Taksonomi negatif berbeda dari anchor.")
    source = string(raw["policy_ref"], "rujukan kebijakan")
    maximum = integer(raw["maximum_per_case"], 1, 20)
    known, refs = {}, {source}
    for row in entries(raw["taxonomies"], 100):
        object_fields(row, ("task_kind", "rule_ref", "labels", "exclusive"))
        domain = string(row["task_kind"], "jenis tugas")
        if domain in known or row["exclusive"] is not True:
            raise InputError("Taksonomi harus unik dengan label yang eksklusif.")
        rule = reference(row["rule_ref"], refs, "rujukan taksonomi")
        mapping, values = {}, {}
        for node in entries(row["labels"], MAX_LABELS):
            object_fields(node, ("label", "label_ref", "aliases"))
            label = string(node["label"], "label", max_chars=60)
            pointer = reference(node["label_ref"], refs, "rujukan label")
            for alias in [label, *entries(node["aliases"], 16)]:
                name = _norm(string(alias, "alias", max_chars=60))
                if name in mapping:
                    raise InputError("Taksonomi memuat alias ambigu atau ganda.")
                mapping[name] = label
            values[label] = pointer
        if len(values) < 2:
            raise InputError("Taksonomi membutuhkan minimal dua label.")
        known[domain] = (rule, mapping, values)
    if not known:
        raise InputError("Taksonomi negatif kosong.")
    return source, maximum, known


def mine(dataset, manifest, head, raw_policy, expected):
    ref, maximum, taxonomies = _policy(raw_policy, expected)
    if not verify(dataset, manifest, head)["valid"]:
        raise InputError("Dataset tidak lolos verifikasi kustodi.")
    events, skipped, rankings = [], [], {}
    measured = operations = 0
    for line in dataset.splitlines():
        row = decode(line)
        key = row["example_id"]
        proof = row["provenance"]["evidence_ref"]
        payload = row["payload"]
        domain = payload["task_kind"]
        spec = taxonomies.get(domain)
        if row["split"] != "train" or spec is None:
            skipped.append({"example_id": key, "evidence_ref": proof,
                            "reason": "held_out" if row["split"] != "train" else "task_without_taxonomy"})
            continue
        rule, aliases, values = spec
        observed = _norm(payload["target"])
        gold = aliases.get(observed)
        if gold is None:
            skipped.append({"example_id": key, "evidence_ref": proof, "reason": "gold_outside_taxonomy"})
            continue
        measured += 1
        if measured > MAX_JOBS:
            raise InputError("Jumlah contoh negatif melampaui batas.")
        group = (domain, gold)
        if group not in rankings:
            target_key = _norm(gold)
            candidates = [(label, _norm(label)) for label in values if label != gold]
            operations += len(target_key) * sum(len(normalized) for _, normalized in candidates)
            operation_budget(operations)
            rankings[group] = sorted((_distance(target_key, normalized), label)
                                     for label, normalized in candidates)[:maximum]
        for distance, wrong in rankings[group]:
            events.append({"id": f"negative-{identity([key, wrong, expected])}", "example_id": key,
                           "task_kind": domain, "gold_label": gold, "negative_label": wrong,
                           "edit_distance": distance, "evidence_ref": proof, "taxonomy_ref": rule,
                           "gold_label_ref": values[gold], "negative_label_ref": values[wrong]})
    return {"schema": "ace.forge-contrastive-negatives.v1", "policy_ref": ref, "policy_sha256": expected,
            "dataset_head_sha256": head, "examples_seen": measured,
            "negative_count": len(events), "negatives": sorted(events, key=lambda row: (row["example_id"], row["edit_distance"],
                                                                                     row["negative_label"])),
            "skipped": sorted(skipped, key=lambda item: item["example_id"])}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("policy", type=Path)
    parser.add_argument("--expect-head", required=True)
    parser.add_argument("--expect-policy-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = mine(read_bytes(args.dataset, MAX_BYTES), decode(read_bytes(args.manifest, MAX_MANIFEST_BYTES)),
                      args.expect_head, decode(read_bytes(args.policy, MAX_BYTES)), args.expect_policy_sha256)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
