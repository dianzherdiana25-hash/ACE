"""Hitung bobot contoh untuk menangani distribusi train yang timpang.

Target dideklarasikan per jenis tugas dan bahasa. Setiap kelompok
memakai bobot invers frekuensi dengan batas penguatan. Laporan
memisahkan distribusi yang diinginkan, bobot efektif, dan kehilangan
karena batas. Held-out tidak mendapat bobot.
"""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string
from .dataset_custody import MAX_MANIFEST_BYTES, verify
from .dataset_forge import MAX_BYTES, MAX_ROWS
from .forgetting_guard import _fraction


def _policy(raw, expected):
    object_fields(raw, ("policy_ref", "max_weight_bp", "minimum_group", "targets"))
    if identity(raw) != digest(expected):
        raise InputError("Kebijakan bobot berbeda dari anchor.")
    ref = string(raw["policy_ref"], "rujukan kebijakan")
    cap = Fraction(integer(raw["max_weight_bp"], 10_000, 1_000_000), 10_000)
    minimum = integer(raw["minimum_group"], 1, MAX_ROWS)
    targets = {}
    for row in entries(raw["targets"], 100):
        object_fields(row, ("task_kind", "language", "share_bp"))
        group = string(row["task_kind"], "jenis tugas"), string(row["language"], "bahasa")
        if group in targets:
            raise InputError("Target kelompok ganda.")
        targets[group] = Fraction(integer(row["share_bp"], 1, 10_000), 10_000)
    if sum(targets.values()) != 1:
        raise InputError("Target bagian total harus tepat 10.000 basis points.")
    return ref, cap, minimum, targets


def _snapshot(dataset, manifest, head, targets):
    if not verify(dataset, manifest, head)["valid"]:
        raise InputError("Dataset tidak lolos verifikasi kustodi.")
    groups, excluded, pointers = defaultdict(list), Counter(), []
    for line in dataset.splitlines():
        row = decode(line)
        payload = row["payload"]
        group = payload["task_kind"], payload["language"]
        if row["split"] == "held_out" or group not in targets:
            reason = "held_out" if row["split"] == "held_out" else "out_of_policy"
            excluded[reason] += 1
            pointers.append({"example_id": row["example_id"], "reason": reason,
                             "evidence_ref": row["provenance"]["evidence_ref"]})
            continue
        groups[group].append({"example_id": row["example_id"], "evidence_ref": row["provenance"]["evidence_ref"]})
    return groups, dict(sorted(excluded.items())), sorted(pointers, key=lambda row: row["example_id"])


def rebalance(data, manifest, expected_head, raw_policy, expected_policy):
    ref, cap, minimum, targets = _policy(raw_policy, expected_policy)
    groups, excluded, pointers = _snapshot(data, manifest, expected_head, targets)
    eligible = sum(map(len, groups.values()))
    cells, weights = [], []
    enough = all(len(groups[group]) >= minimum for group in targets)
    totals = Fraction(0)
    square_sum = Fraction(0)
    for group, target in sorted(targets.items()):
        count = len(groups[group])
        proportion = Fraction(count, eligible) if eligible else None
        baseline_weight = target / proportion if proportion else None
        value = min(cap, baseline_weight) if enough else None
        clipped = value is not None and value < baseline_weight
        if value is not None:
            totals += value * count
            square_sum += value * value * count
            weights.extend({**example, "weight": _fraction(value)} for example in groups[group])
        cells.append({
            "task_kind": group[0], "language": group[1], "eligible": count, "shortfall": max(0, minimum - count),
            "desired": _fraction(target), "observed": _fraction(proportion) if proportion is not None else None,
            "weight": _fraction(value) if value is not None else None, "capped": clipped,
        })
    if enough:
        for row in cells:
            mass = Fraction(**row["weight"]) * row["eligible"] / totals
            row["weighted_share"] = _fraction(mass)
            row["weighted_minus_target"] = _fraction(mass - Fraction(**row["desired"]))
    else:
        for row in cells:
            row.update(weighted_share=None, weighted_minus_target=None)
    return {"schema": "ace.forge-data-rebalance.v1", "dataset_head_sha256": expected_head,
            "policy_ref": ref, "policy_sha256": expected_policy, "eligible_train": eligible, "excluded": excluded,
            "exclusions": pointers, "groups": cells, "assignments": sorted(weights, key=lambda item: item["example_id"]),
            "effective_sample_size": _fraction(totals**2 / square_sum) if enough else None,
            "status": "held" if not enough else "capped" if any(row["capped"] for row in cells) else "balanced"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("policy", type=Path)
    parser.add_argument("--expect-head", required=True)
    parser.add_argument("--expect-policy-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        report = rebalance(read_bytes(args.dataset, MAX_BYTES), decode(read_bytes(args.manifest, MAX_MANIFEST_BYTES)),
                           args.expect_head, decode(read_bytes(args.policy, MAX_BYTES)), args.expect_policy_sha256)
        sys.stdout.write(canonical(report).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(report["status"] != "balanced")


if __name__ == "__main__":
    raise SystemExit(main())
