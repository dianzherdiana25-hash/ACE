"""Bandingkan observasi runtime yang dibekukan terhadap selector dan registry.

Selector menetapkan artefak yang diharapkan, registry menetapkan
kelayakan, dan hash byte memeriksa objek lokal. Receipt yang kosong
atau terlalu lama ditandai. Pemeriksaan menerima snapshot eksplisit
supaya audit tidak perlu menghubungi proses aktif.
"""
import argparse
from collections import Counter
from datetime import timedelta
from pathlib import Path
import sys

from . import model_registry_v2
from ._artifact_io import inspect_file
from ._forge_io import InputError, canonical, decode, digest, entries, identity, integer, object_fields, read_bytes, string, utc_stamp
from .dataset_forge import MAX_BYTES
from .model_rollback import _selector


MAX_SLOTS = 256


def _observations(raw, slots, now):
    evidence = {}
    refs = set()
    for row in entries(raw, MAX_SLOTS):
        object_fields(row, ("slot", "snapshot_ref", "observed_at", "artifact_sha256", "generation"))
        slot = string(row["slot"], "slot runtime")
        pointer = string(row["snapshot_ref"], "rujukan observasi")
        stamp = utc_stamp(row["observed_at"])
        if slot not in slots or slot in evidence or pointer in refs or stamp > now:
            raise InputError("Observasi tak dikenal, ganda, atau dari masa depan.")
        refs.add(pointer)
        evidence[slot] = (stamp, {"snapshot_ref": pointer, "observed_at": stamp.isoformat(),
                                  "artifact_sha256": digest(row["artifact_sha256"]),
                                  "generation": integer(row["generation"], 1, 10**9)})
    return evidence


def _issues(selection, observed, registry, root, now, freshness):
    domain, generation, active = selection
    findings = []
    artifact = registry.get(active)
    bytes_result = None
    if artifact is None:
        findings.append("not_registered")
    else:
        if artifact["status"] != "qualified":
            findings.append("not_qualified")
        if artifact["domain"] != domain:
            findings.append("registry_domain_mismatch")
        bytes_result, failure = inspect_file(root, artifact["artifact_ref"])
        if failure:
            findings.append(failure)
        elif bytes_result["sha256"] != active:
            findings.append("artifact_sha256_mismatch")
    if observed is None:
        findings.append("observation_missing")
    else:
        stamp, row = observed
        if now - stamp > freshness:
            findings.append("observation_stale")
        if row["generation"] != generation:
            findings.append("generation_drift")
        if row["artifact_sha256"] != active:
            findings.append("runtime_artifact_drift")
    return findings, bytes_result


def assess(raw, records, root, expected):
    object_fields(raw, ("audit_ref", "as_of", "max_age_seconds", "registry_head_sha256", "selectors", "observations"))
    if identity(raw) != digest(expected):
        raise InputError("Rencana drift berbeda dari anchor.")
    source = string(raw["audit_ref"], "rujukan audit")
    now = utc_stamp(raw["as_of"])
    age = timedelta(seconds=integer(raw["max_age_seconds"], 1, 365*86400))
    report = model_registry_v2.inspect(records, raw["registry_head_sha256"])
    if any(utc_stamp(row["last_event_at"]) > now for row in report["artifacts"]):
        raise InputError("Registry memuat event setelah waktu audit.")
    registry = {row["sha256"]: row for row in report["artifacts"]}
    slots = {}
    refs = {source}
    for row in entries(raw["selectors"], MAX_SLOTS):
        object_fields(row, ("slot", "selector_sha256", "selector"))
        slot = string(row["slot"], "slot selector")
        ref, _, domain, generation, active, _ = _selector(row["selector"], row["selector_sha256"])
        if slot in slots or ref in refs:
            raise InputError("Slot atau rujukan selector ganda.")
        refs.add(ref)
        slots[slot] = (ref, row["selector_sha256"], (domain, generation, active))
    if not slots:
        raise InputError("Audit drift perlu setidaknya satu selector.")
    observations = _observations(raw["observations"], slots, now)
    counts = Counter()
    rows = []
    for slot, (ref, checksum, selection) in sorted(slots.items()):
        observed = observations.get(slot)
        findings, actual = _issues(selection, observed, registry, root, now, age)
        counts.update(findings)
        domain, generation, expected_key = selection
        registry_item = registry.get(expected_key)
        rows.append({"slot": slot, "domain": domain, "selector_ref": ref, "selector_sha256": checksum,
                     "expected_generation": generation, "expected_artifact_sha256": expected_key,
                     "observation": observed[1] if observed else None, "registry_artifact_ref": (
                         registry_item["artifact_ref"] if registry_item else None),
                     "registry_event_ref": registry_item["last_event_ref"] if registry_item else None,
                     "artifact_bytes": actual, "findings": findings})
    return {"schema": "ace.forge-active-drift.v1", "audit_ref": source, "input_sha256": expected,
            "registry_head_sha256": report["head_sha256"], "as_of": now.isoformat(),
            "status": "drift_or_incomplete" if counts else "in_sync",
            "findings_by_kind": dict(sorted(counts.items())), "slots": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("registry", type=Path)
    parser.add_argument("artifacts", type=Path)
    parser.add_argument("--expect-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        result = assess(decode(read_bytes(args.input, MAX_BYTES)), model_registry_v2._load(args.registry),
                        args.artifacts, args.expect_sha256)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, OverflowError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result["status"] != "in_sync")


if __name__ == "__main__":
    raise SystemExit(main())
