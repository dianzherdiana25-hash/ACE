"""Segel artefak checkpoint dan verifikasi ulang terhadap head eksternal.

Rencana mendaftarkan ID receipt dan path relatif. Setiap record memuat
ukuran, SHA-256 file, serta hash record sebelumnya. Verify membandingkan
manifest kanonis dengan snapshot file yang dibaca kembali dan melaporkan
letak perubahan. Keluaran ditulis ke stdout tanpa mengubah artefak.
"""
import argparse
from pathlib import Path
import sys

from ._artifact_io import inspect_file
from ._forge_io import InputError, canonical, decode, digest, entries, identity, object_fields, read_bytes, string
from ._numeric import reference
from .dataset_forge import MAX_BYTES


SCHEMA = "ace.forge-checkpoint-manifest.v1"
MAX_CHECKPOINTS = 1000
MAX_FILES = 4000


def _plan(raw, expected):
    object_fields(raw, ("plan_ref", "run_id", "checkpoints"))
    if identity(raw) != digest(expected):
        raise InputError("Rencana checkpoint berbeda dari anchor.")
    pointer = string(raw["plan_ref"], "rujukan rencana")
    run = string(raw["run_id"], "ID run")
    ids, refs, receipts = set(), {pointer}, set()
    checkpoints = []
    total_files = 0
    for row in entries(raw["checkpoints"], MAX_CHECKPOINTS):
        object_fields(row, ("id", "receipt_sha256", "receipt_ref", "files"))
        key = reference(row["id"], ids, "ID checkpoint")
        receipt = digest(row["receipt_sha256"])
        if receipt in receipts:
            raise InputError("Receipt checksum ganda untuk beberapa checkpoint.")
        receipts.add(receipt)
        source = reference(row["receipt_ref"], refs, "rujukan receipt")
        files = set()
        for path in entries(row["files"], MAX_FILES):
            value = string(path, "path artefak", max_chars=1024, preserve=True)
            if value in files or value != value.strip():
                raise InputError("Path artefak ganda atau belum kanonis.")
            files.add(value)
        total_files += len(files)
        if not files or total_files > MAX_FILES:
            raise InputError("Checkpoint membutuhkan berkas dan totalnya harus dalam batas.")
        checkpoints.append({"id": key, "receipt_sha256": receipt, "receipt_ref": source, "files": sorted(files)})
    if not checkpoints:
        raise InputError("Tidak ada checkpoint terdaftar.")
    return {"schema": SCHEMA, "plan_ref": pointer, "run_id": run, "plan_sha256": expected}, checkpoints


def _capture(plan, expected, root):
    header, checkpoints = _plan(plan, expected)
    initial = previous = identity(header)
    records, errors = [], []
    examined = {}
    for index, item in enumerate(checkpoints, 1):
        files = []
        for path in item["files"]:
            if path not in examined:
                examined[path] = inspect_file(root, path)
            result, blocker = examined[path]
            if blocker is None:
                files.append({"path": path, **result})
            else:
                errors.append({"checkpoint": item["id"], "path": path, "reason": blocker})
        record = {**item, "files": files, "sequence": index, "previous_sha256": previous}
        previous = identity(record)
        records.append({**record, "sha256": previous})
    if errors:
        return None, errors
    return {**header, "genesis_sha256": initial, "head_sha256": previous, "checkpoints": records}, errors


def seal(plan, expected, root):
    manifest, errors = _capture(plan, expected, root)
    if errors:
        first = errors[0]
        raise InputError(f"Checkpoint {first['checkpoint']} tidak lengkap pada {first['path']} ({first['reason']}).")
    return manifest


def _differences(stored, observed):
    changes = []
    for wanted, got in zip(stored, observed):
        if not isinstance(wanted, dict) or wanted.get("id") != got["id"]:
            changes.append({"checkpoint": got["id"], "reason": "checkpoint_order_or_id_mismatch"})
            continue
        files = wanted.get("files")
        if not isinstance(files, list) or len(files) > MAX_FILES or any(
            not isinstance(row, dict) or not isinstance(row.get("path"), str) for row in files
        ):
            changes.append({"checkpoint": got["id"], "reason": "manifest_files_invalid"})
            continue
        before_count = len(changes)
        by_path = {row["path"]: row for row in files}
        found = {row["path"]: row for row in got["files"]}
        if len(by_path) != len(files):
            changes.append({"checkpoint": got["id"], "reason": "duplicate_manifest_path"})
        for path in sorted(by_path.keys() | found.keys()):
            if canonical(by_path.get(path)) != canonical(found.get(path)):
                changes.append({"checkpoint": got["id"], "path": path, "reason": "manifest_or_bytes_changed"})
        if canonical(wanted) != canonical(got) and before_count == len(changes):
            changes.append({"checkpoint": got["id"], "reason": "checkpoint_metadata_or_chain_changed"})
    if len(stored) != len(observed):
        changes.append({"checkpoint": None, "reason": "checkpoint_count_mismatch"})
    return changes


def verify(plan, expected, root, manifest, expected_head):
    digest(expected_head)
    object_fields(manifest, ("schema", "plan_ref", "run_id", "plan_sha256", "genesis_sha256", "head_sha256", "checkpoints"))
    if manifest["schema"] != SCHEMA:
        raise InputError("Skema manifest checkpoint tidak dikenal.")
    stored = entries(manifest["checkpoints"], MAX_CHECKPOINTS)
    observed, findings = _capture(plan, expected, root)
    reasons = []
    if manifest["head_sha256"] != expected_head:
        reasons.append("recorded_head_mismatch")
    if observed is None:
        reasons.append("artifact_read_failed")
    else:
        if observed["head_sha256"] != expected_head:
            reasons.append("current_head_mismatch")
        if canonical(observed) != canonical(manifest):
            reasons.append("manifest_mismatch")
            findings = _differences(stored, observed["checkpoints"])
            header_keys = ("plan_ref", "run_id", "plan_sha256", "genesis_sha256")
            if any(manifest[key] != observed[key] for key in header_keys):
                findings.insert(0, {"checkpoint": None, "reason": "manifest_header_changed"})
    return {"schema": "ace.forge-checkpoint-verification.v1", "valid": not reasons,
            "expected_head_sha256": expected_head, "observed_head_sha256": observed["head_sha256"] if observed else None,
            "reasons": reasons, "findings": findings}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("root", type=Path)
    parser.add_argument("--expect-plan-sha256", required=True)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--expect-head")
    args = parser.parse_args(argv)
    if (args.verify is None) != (args.expect_head is None):
        parser.error("Mode verify memerlukan manifest dan anchor head.")
    try:
        plan = decode(read_bytes(args.plan, MAX_BYTES))
        if args.verify is None:
            result = seal(plan, args.expect_plan_sha256, args.root)
            code = 0
        else:
            result = verify(plan, args.expect_plan_sha256, args.root, decode(read_bytes(args.verify, MAX_BYTES)),
                            args.expect_head)
            code = int(not result["valid"])
        sys.stdout.write(canonical(result).decode("utf-8") + "\n")
    except (OSError, ValueError, RecursionError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
