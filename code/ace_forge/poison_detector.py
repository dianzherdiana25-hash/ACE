"""Cari anomali integritas dataset sebelum penggunaan data latih.

Pemeriksaan membandingkan dua snapshot berkustodi. Sinyal terdiri dari
perubahan label, irisan held-out, penggunaan bukti pada payload lain,
dan konsentrasi keluarga atau target yang melonjak. Temuan meminta
telaah sumber dan tidak menetapkan niat atau sebab perubahan.
"""
import argparse
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
import sys
import unicodedata

from ._forge_io import InputError, canonical, decode, digest, identity, integer, object_fields, read_bytes, string
from .dataset_custody import MAX_MANIFEST_BYTES, verify
from .dataset_forge import MAX_BYTES, MAX_ROWS, Source
from .forgetting_guard import _fraction


def _read(data, manifest, head):
    if not verify(data, manifest, head)["valid"]:
        raise InputError("Salah satu snapshot tidak lolos verifikasi kustodi.")
    indexed, pointers = {}, {}
    for line in data.splitlines():
        record = decode(line)
        source = Source.read(record["payload"])
        proof = record["provenance"]
        key = identity(source.prompt_identity)
        target = identity(" ".join(unicodedata.normalize("NFC", source.target).split()))
        item = {"id": source.event_id, "family_id": source.family, "split": record["split"],
                "task_kind": source.task_kind, "prompt_sha256": key, "label_sha256": target,
                "payload_sha256": proof["payload_sha256"], "evidence_ref": proof["evidence_ref"]}
        indexed[key] = item
        pointers[item["evidence_ref"]] = item
    return indexed, pointers


def _change(before, after, sources):
    findings = []
    for key, current in sorted(after.items()):
        prior = before.get(key)
        if prior is not None:
            common = {"prompt_sha256": key, "old_evidence_ref": prior["evidence_ref"],
                      "new_evidence_ref": current["evidence_ref"]}
            if prior["label_sha256"] != current["label_sha256"]:
                findings.append({**common, "type": "label_changed", "old_label_sha256": prior["label_sha256"],
                                 "new_label_sha256": current["label_sha256"]})
            if prior["split"] != current["split"]:
                signal = "held_out_entered_train" if prior["split"] == "held_out" else "train_entered_held_out"
                findings.append({**common, "type": signal})
        prior_evidence = sources.get(current["evidence_ref"])
        if prior_evidence is not None and prior_evidence["payload_sha256"] != current["payload_sha256"]:
            findings.append({"type": "evidence_changed_payload", "evidence_ref": current["evidence_ref"],
                             "old_payload_sha256": prior_evidence["payload_sha256"],
                             "new_payload_sha256": current["payload_sha256"]})
    return findings


def _family_collisions(before, after):
    historical, candidate = defaultdict(lambda: defaultdict(list)), defaultdict(lambda: defaultdict(list))
    for source, table in ((before, historical), (after, candidate)):
        for item in source.values():
            table[item["family_id"]][item["split"]].append(item["evidence_ref"])
    findings = []
    for family in sorted(historical.keys() & candidate.keys()):
        for source_split, target_split in (("train", "held_out"), ("held_out", "train")):
            old, new = historical[family][source_split], candidate[family][target_split]
            if old and new:
                findings.append({"type": "family_partition_conflict", "family_id": family,
                                 "old_split": source_split, "new_split": target_split,
                                 "old_evidence_refs": sorted(old), "new_evidence_refs": sorted(new)})
    return findings


def _counts(rows, label):
    groups = defaultdict(lambda: defaultdict(list))
    for row in rows:
        groups[row["task_kind"]][row[label]].append(row["evidence_ref"])
    return groups


def _bursts(before, after, policy):
    minimum, share_floor, increase = policy
    found = []
    for label in ("family_id", "label_sha256"):
        old, new = _counts(before, label), _counts(after, label)
        for kind, groups in sorted(new.items()):
            previous = old[kind]
            old_total = sum(map(len, previous.values()))
            new_total = sum(map(len, groups.values()))
            for value, references in sorted(groups.items()):
                count = len(references)
                old_count = len(previous.get(value, []))
                if count < minimum:
                    continue
                new_share = Fraction(count, new_total)
                old_share = Fraction(old_count, old_total) if old_total else Fraction(0)
                if new_share < share_floor or new_share - old_share < increase:
                    continue
                found.append({"type": "concentration_increase", "dimension": label, "key": value, "task_kind": kind,
                              "count": count, "old_count": old_count, "total": new_total, "old_total": old_total,
                              "share": _fraction(new_share), "old_share": _fraction(old_share) if old_total else None,
                              "evidence_refs": sorted(references)})
    return found


def audit(left, left_manifest, left_head, right, right_manifest, right_head, raw_policy, expected_policy):
    object_fields(raw_policy, ("policy_ref", "minimum_group", "minimum_share_bp", "minimum_increase_bp"))
    if identity(raw_policy) != digest(expected_policy):
        raise InputError("Kebijakan anomali berbeda dari anchor.")
    ref = string(raw_policy["policy_ref"], "rujukan kebijakan")
    floor = Fraction(integer(raw_policy["minimum_share_bp"], 1, 10_000), 10_000)
    increase = Fraction(integer(raw_policy["minimum_increase_bp"], 1, 10_000), 10_000)
    minimum = integer(raw_policy["minimum_group"], 2, MAX_ROWS)
    before, pointers = _read(left, left_manifest, left_head)
    after, _ = _read(right, right_manifest, right_head)
    changes = _change(before, after, pointers) + _family_collisions(before, after)
    old_train = [item for item in before.values() if item["split"] == "train"]
    new_train = [item for item in after.values() if item["split"] == "train"]
    findings = changes + _bursts(old_train, new_train, (minimum, floor, increase))
    return {"schema": "ace.forge-poison-signals.v1", "policy_ref": ref, "policy_sha256": expected_policy,
            "baseline_head": left_head, "candidate_head": right_head, "baseline_examples": len(before),
            "candidate_examples": len(after), "status": "review_required" if findings else "no_configured_signal",
            "findings": findings}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("baseline_manifest", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("candidate_manifest", type=Path)
    parser.add_argument("policy", type=Path)
    parser.add_argument("--expect-baseline-head", required=True)
    parser.add_argument("--expect-candidate-head", required=True)
    parser.add_argument("--expect-policy-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        value = audit(read_bytes(args.baseline, MAX_BYTES), decode(read_bytes(args.baseline_manifest, MAX_MANIFEST_BYTES)),
                      args.expect_baseline_head, read_bytes(args.candidate, MAX_BYTES),
                      decode(read_bytes(args.candidate_manifest, MAX_MANIFEST_BYTES)), args.expect_candidate_head,
                      decode(read_bytes(args.policy, MAX_BYTES)), args.expect_policy_sha256)
        sys.stdout.write(canonical(value).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(value["status"] == "review_required")


if __name__ == "__main__":
    raise SystemExit(main())
