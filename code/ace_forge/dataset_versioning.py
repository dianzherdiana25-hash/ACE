"""Buat snapshot versi berkustodi, baca lineage, dan diff tanpa payload.

Snapshot mengikat head dataset dan inventaris event dengan hash konten.
Rujukan parent membentuk graf versi dan dapat diperiksa dari katalog.
Diff mengelompokkan perubahan split, isi, metadata, lisensi, atau bukti
supaya perubahan penting tetap terlihat ketika jumlah baris sama.
"""
import argparse
from collections import Counter
from pathlib import Path
import sys

from ._forge_io import InputError, canonical, decode, digest, entries, identity, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_custody import MAX_MANIFEST_BYTES, verify
from .dataset_forge import MAX_BYTES, MAX_ROWS, Source


SCHEMA = "ace.forge-dataset-version.v1"
MAX_VERSIONS = 2000
HASH_FIELDS = ("prompt_sha256", "target_sha256", "payload_sha256")
TEXT_FIELDS = ("event_id", "split", "language", "family_id", "task_kind", "license", "evidence_ref", "index_ref")


def _parents(raw):
    values = [digest(item) for item in entries(raw, 8)]
    if len(values) != len(set(values)):
        raise InputError("Parent versi ganda.")
    return sorted(values)


def _snapshot_row(row):
    payload = Source.read(row["payload"])
    sources = row["provenance"]
    return {"event_id": payload.event_id, "language": payload.language, "family_id": payload.family,
            "task_kind": payload.task_kind, "split": row["split"], "prompt_sha256": identity(payload.prompt),
            "target_sha256": identity(payload.target), "payload_sha256": sources["payload_sha256"],
            "license": sources["license"], "evidence_ref": sources["evidence_ref"], "index_ref": sources["index_ref"]}


def snapshot(data, manifest, expected_head, metadata, expected_metadata):
    object_fields(metadata, ("version", "source_ref", "parents"))
    if identity(metadata) != digest(expected_metadata):
        raise InputError("Metadata versi berbeda dari anchor.")
    if not verify(data, manifest, expected_head)["valid"]:
        raise InputError("Dataset tidak lolos verifikasi kustodi.")
    name = string(metadata["version"], "ID versi")
    pointer = string(metadata["source_ref"], "rujukan versi")
    parents = _parents(metadata["parents"])
    rows = [_snapshot_row(decode(line)) for line in data.splitlines()]
    ledger = {"schema": SCHEMA, "dataset_head_sha256": expected_head, "metadata_sha256": expected_metadata,
              "version": name, "source_ref": pointer, "parents": parents,
              "examples": sorted(rows, key=lambda row: row["event_id"])}
    return {"version_sha256": identity(ledger), "version": ledger}


def _index(raw, expected):
    object_fields(raw, ("version_sha256", "version"))
    if digest(raw["version_sha256"]) != digest(expected) or identity(raw["version"]) != expected:
        raise InputError("Snapshot versi berbeda dari anchor.")
    obj = raw["version"]
    object_fields(obj, ("schema", "dataset_head_sha256", "metadata_sha256", "version", "source_ref", "parents", "examples"))
    digest(obj["dataset_head_sha256"])
    digest(obj["metadata_sha256"])
    if obj["schema"] != SCHEMA or _parents(obj["parents"]) != obj["parents"] or expected in obj["parents"]:
        raise InputError("Skema versi atau parent tidak sah.")
    string(obj["version"], "ID versi")
    string(obj["source_ref"], "rujukan versi")
    known, ids, refs = {}, set(), set()
    for row in entries(obj["examples"], MAX_ROWS):
        object_fields(row, (*TEXT_FIELDS, *HASH_FIELDS))
        key = reference(row["event_id"], ids, "ID event")
        for field in TEXT_FIELDS[1:]:
            string(row[field], field)
        for field in HASH_FIELDS:
            digest(row[field])
        if row["split"] not in ("train", "held_out"):
            raise InputError("Split inventaris tidak sah.")
        if row["evidence_ref"] in refs:
            raise InputError("Bukti inventaris ganda.")
        refs.add(row["evidence_ref"])
        known[key] = row
    return obj, known


def compare(left, left_expected, right, right_expected):
    before, base = _index(left, left_expected)
    after, next_ = _index(right, right_expected)
    changes = []
    for key in sorted(base.keys() | next_.keys()):
        a, b = base.get(key), next_.get(key)
        if a == b:
            continue
        details = [] if a is None or b is None else [field for field in sorted(set(a) | set(b)) if a[field] != b[field]]
        category = "added" if a is None else "removed" if b is None else "changed"
        changes.append({"event_id": key, "status": category, "fields": details,
                        "old_evidence_ref": a["evidence_ref"] if a else None,
                        "new_evidence_ref": b["evidence_ref"] if b else None,
                        "old_payload_sha256": a["payload_sha256"] if a else None,
                        "new_payload_sha256": b["payload_sha256"] if b else None})
    counts = Counter(row["status"] for row in changes)
    fields = Counter(field for row in changes for field in row["fields"])
    return {"schema": "ace.forge-dataset-version-diff.v1", "before_sha256": left_expected, "after_sha256": right_expected,
            "before_ref": before["source_ref"], "after_ref": after["source_ref"], "before_rows": len(base),
            "after_rows": len(next_), "direct_parent": left_expected in after["parents"],
            "counts": dict(sorted(counts.items())), "changed_fields": dict(sorted(fields.items())),
            "unchanged_rows": len(base) - counts["removed"] - counts["changed"], "changes": changes}


def lineage(raw, expected):
    if identity(raw) != digest(expected):
        raise InputError("Katalog versi berbeda dari anchor.")
    versions, tags = {}, set()
    for row in entries(raw, MAX_VERSIONS):
        object_fields(row, ("version_sha256", "version"))
        sha = row["version_sha256"]
        object_, _ = _index(row, sha)
        if sha in versions:
            raise InputError("Snapshot versi ganda.")
        reference(object_["version"], tags, "ID versi")
        versions[sha] = {"version_sha256": sha, "version": object_["version"], "parents": object_["parents"],
                         "source_ref": object_["source_ref"]}
    parents = {key for node in versions.values() for key in node["parents"]}
    gaps = [{"version_sha256": key, "missing_parents": sorted(set(item["parents"]) - versions.keys())}
            for key, item in sorted(versions.items()) if set(item["parents"]) - versions.keys()]
    return {"schema": "ace.forge-dataset-lineage.v1", "catalog_sha256": expected,
            "versions": [versions[key] for key in sorted(versions)], "heads": sorted(versions.keys() - parents),
            "roots": sorted(key for key, row in versions.items() if not row["parents"]), "gaps": gaps,
            "status": "incomplete" if gaps else "complete"}


def _read(path, maximum=MAX_BYTES):
    return decode(read_bytes(path, maximum))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    make = modes.add_parser("snapshot")
    make.add_argument("dataset", type=Path)
    make.add_argument("manifest", type=Path)
    make.add_argument("metadata", type=Path)
    make.add_argument("--expect-head", required=True)
    make.add_argument("--expect-metadata-sha256", required=True)
    diff = modes.add_parser("diff")
    diff.add_argument("before", type=Path)
    diff.add_argument("after", type=Path)
    diff.add_argument("--expect-before", required=True)
    diff.add_argument("--expect-after", required=True)
    catalog = modes.add_parser("lineage")
    catalog.add_argument("catalog", type=Path)
    catalog.add_argument("--expect-catalog-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.mode == "snapshot":
            result = snapshot(read_bytes(args.dataset, MAX_BYTES), _read(args.manifest, MAX_MANIFEST_BYTES),
                              args.expect_head, _read(args.metadata), args.expect_metadata_sha256)
        elif args.mode == "diff":
            result = compare(_read(args.before), args.expect_before, _read(args.after), args.expect_after)
        else:
            result = lineage(_read(args.catalog), args.expect_catalog_sha256)
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return int(result.get("status") == "incomplete")


if __name__ == "__main__":
    raise SystemExit(main())
