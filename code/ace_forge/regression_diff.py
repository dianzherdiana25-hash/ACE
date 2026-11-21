"""Bandingkan observasi kemampuan pada dua artefak melalui kontrak uji.

Hasil hanya dipasangkan bila ID pemeriksaan dan hash kontrak sama.
Perubahan kontrak, pemeriksaan yang hilang, serta observasi yang belum
dijalankan tetap terlihat. Laporan membedakan kompetensi yang kembali
lulus dari hilangnya cakupan atau perubahan rubrik.
"""
import argparse
from collections import Counter
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES


MAX_CAPABILITIES = 1000
MAX_CHECKS = 30_000


def _snapshot(report, expected):
    object_fields(report, ("artifact_sha256", "snapshot_ref", "capabilities"))
    if identity(report) != digest(expected):
        raise InputError("Snapshot hasil berbeda dari anchor.")
    artifact = digest(report["artifact_sha256"])
    source = string(report["snapshot_ref"], "sumber snapshot")
    references, labels = {source}, set()
    grouped = {}
    row_count = 0
    for group in entries(report["capabilities"], MAX_CAPABILITIES):
        object_fields(group, ("id", "spec_ref", "checks"))
        name = reference(group["id"], labels, "ID kemampuan")
        spec = reference(group["spec_ref"], references, "rujukan spesifikasi")
        checks = entries(group["checks"], MAX_CHECKS)
        row_count += len(checks)
        if row_count > MAX_CHECKS:
            raise InputError("Snapshot melebihi batas jumlah pemeriksaan.")
        parsed, seen = {}, set()
        for row in checks:
            object_fields(row, ("id", "contract_sha256", "verdict", "evidence_ref"))
            key = reference(row["id"], seen, "ID pemeriksaan")
            status = row["verdict"]
            if status not in ("pass", "fail", "not_run"):
                raise InputError("Verdict pemeriksaan tidak dikenal.")
            evidence = row["evidence_ref"]
            if status == "not_run":
                if evidence is not None:
                    raise InputError("Pemeriksaan yang belum dijalankan tidak boleh punya bukti hasil.")
            else:
                evidence = reference(evidence, references, "rujukan bukti pemeriksaan")
            parsed[key] = {"contract_sha256": digest(row["contract_sha256"]), "verdict": status, "evidence_ref": evidence}
        grouped[name] = (spec, parsed)
    return {"artifact_sha256": artifact, "snapshot_ref": source, "snapshot_sha256": expected}, grouped


def _compare(before, after):
    if before is None:
        return "check_added"
    if after is None:
        return "check_removed"
    if before["contract_sha256"] != after["contract_sha256"]:
        return "contract_changed"
    if "not_run" in (before["verdict"], after["verdict"]):
        return "unmeasured"
    if before["evidence_ref"] == after["evidence_ref"]:
        return "shared_evidence"
    return {
        ("pass", "pass"): "retained", ("pass", "fail"): "regressed",
        ("fail", "pass"): "fixed", ("fail", "fail"): "still_failing",
    }[before["verdict"], after["verdict"]]


def _capability(label, baseline, candidate):
    before_spec, before_checks = baseline if baseline is not None else (None, {})
    after_spec, after_checks = candidate if candidate is not None else (None, {})
    changes = []
    for key in sorted(before_checks.keys() | after_checks.keys()):
        before, after = before_checks.get(key), after_checks.get(key)
        changes.append({"id": key, "status": _compare(before, after), "before": before, "after": after})
    counts = Counter(row["status"] for row in changes)
    paired = sum(counts[key] for key in ("retained", "regressed", "fixed", "still_failing"))
    if baseline is None:
        status = "capability_added"
    elif candidate is None:
        status = "capability_removed"
    elif counts["regressed"]:
        status = "regression_observed"
    elif paired != len(changes) or not paired:
        status = "coverage_changed"
    elif counts["fixed"]:
        status = "improved"
    else:
        status = "no_transition"
    return {"id": label, "status": status, "before_spec_ref": before_spec, "after_spec_ref": after_spec,
            "matched_checks": paired, "counts": dict(sorted(counts.items())), "changes": changes}


def compare(before, after, expected_before, expected_after):
    baseline, old = _snapshot(before, expected_before)
    candidate, new = _snapshot(after, expected_after)
    if baseline["artifact_sha256"] == candidate["artifact_sha256"]:
        raise InputError("Artefak sebelum dan sesudah harus berbeda.")
    groups = [_capability(key, old.get(key), new.get(key)) for key in sorted(old.keys() | new.keys())]
    transitions = Counter(row["status"] for row in groups)
    regressions = [
        {"capability_id": item["id"], "check_ids": [row["id"] for row in item["changes"] if row["status"] == "regressed"]}
        for item in groups if item["status"] == "regression_observed"
    ]
    return {"schema": "ace.forge-regression-diff.v1", "before": baseline, "after": candidate,
            "capability_states": dict(sorted(transitions.items())), "regressions": regressions, "capabilities": groups}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--expect-before", required=True)
    parser.add_argument("--expect-after", required=True)
    args = parser.parse_args(argv)
    try:
        value = compare(decode(read_bytes(args.baseline, MAX_BYTES)), decode(read_bytes(args.candidate, MAX_BYTES)),
                        args.expect_before, args.expect_after)
        sys.stdout.write(canonical(value).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
